# Demo Walkthrough — How It Works in the Code

A brief guide explaining the three core flows: **create a conversation**, **send a message**, and **retrieve messages**. Use this to walk someone through the codebase.

---

## Architecture at a Glance

```
Frontend (index.html)
    │
    │  HTTP REST (JSON)
    │  X-User-Id header for auth
    ▼
FastAPI Backend
    │
    ├── Controller  →  route handler, request/response shaping
    ├── Service     →  business logic, validation, authorization
    ├── Repository  →  raw database queries (SQLAlchemy async)
    │
    ▼
PostgreSQL (TimescaleDB)     Redis (Pub/Sub — future realtime)
```

Every request follows the same **Controller → Service → Repository** pattern.

---

## 1. Authentication (Every Request)

**How it works:**

Every API call includes an `X-User-Id` header (e.g. `alice`, `bob`, `mark`).

**Code flow:**

1. **`app/auth/auth.py` → `get_current_user()`**
   - Reads the `X-User-Id` header
   - Validates it against `VALID_USERNAMES = {"alice", "bob", "mark"}`
   - Calls `_ensure_dev_users_exist()` to seed users into the database if they don't exist yet
   - Looks up the user by email (`{username}@example.com`) in the `users` table
   - Returns the `User` ORM object — this is injected into every route via FastAPI's `Depends(get_current_user)`

**Key point for demo:** This is dev-mode auth. In production, this would be replaced with JWT/OAuth. The important thing is that *every endpoint knows who is calling it*.

---

## 2. Create a Conversation

**Endpoint:** `POST /api/v1/conversations`

**Request body:**
```json
{
    "name": "Project Alpha",
    "description": "Discussion about the project",
    "member_ids": ["<bob-uuid>", "<mark-uuid>"]
}
```

**Code flow:**

```
Frontend                    Backend
────────                    ───────
User clicks "Create"
        │
        ▼
POST /conversations    →    conversation_controller.py
  with X-User-Id            │
  = "alice"                 ▼
                        get_current_user()          ← auth/auth.py
                        Resolves alice's User object
                            │
                            ▼
                        ConversationService         ← service/conversation_service.py
                        .create_conversation()
                            │
                            ├── ConversationRepository.create()
                            │   INSERT INTO conversations (name, description, created_by)
                            │
                            ├── MemberRepository.add_member(alice, role=OWNER)
                            │   INSERT INTO conversation_members
                            │
                            └── For each member_id:
                                ├── UserRepository.get_by_ids() → validate they exist
                                └── MemberRepository.add_member(bob/mark, role=MEMBER)
                                    INSERT INTO conversation_members
                            │
                            ▼
                        Return Conversation object
                            │
                            ▼
                        Controller returns JSON response
```

**Database tables touched:**
- `conversations` — new row created
- `conversation_members` — one row per member (creator = `owner`, others = `member`)

**Key files:**
- `app/controller/conversation_controller.py` — route handler (line 28)
- `app/service/conversation_service.py` — business logic (line 25)
- `app/repositories/conversation_repository.py` — DB insert (line 18)
- `app/repositories/member_repository.py` — member inserts (line 19)
- `app/schemas/conversation.py` — request/response shapes

---

## 3. Send a Message

**Endpoint:** `POST /api/v1/conversations/{conversation_id}/messages`

**Request body:**
```json
{
    "content": "Hello everyone!",
    "message_type": "text"
}
```

**Code flow:**

```
Frontend                    Backend
────────                    ───────
User types message,
clicks Send
        │
        ▼
POST /conversations/       message_controller.py
  {id}/messages        →        │
  with X-User-Id               ▼
  = "alice"                get_current_user()
                               │
                               ▼
                           MessageService              ← service/message_service.py
                           .send_message()
                               │
                               ├── _validate_membership()
                               │       │
                               │       ├── ConversationRepository.get_by_id()
                               │       │   Does this conversation exist?
                               │       │
                               │       └── MemberRepository.is_member()
                               │           Is alice in this conversation?
                               │           SELECT FROM conversation_members
                               │
                               ├── (If reply_to_message_id provided)
                               │   Validate the reply target exists in this conversation
                               │
                               └── MessageRepository.create()
                                   INSERT INTO messages
                                   (conversation_id, sender_id, content, message_type)
                               │
                               ▼
                           _message_to_response()       ← controller helper
                           If deleted_at is set → mask content as
                           "This message was deleted"
                               │
                               ▼
                           Return JSON with message data + sender_name
```

**Database tables touched:**
- `messages` — new row with the message content

**Key files:**
- `app/controller/message_controller.py` — route handler (line 52), `_message_to_response()` helper (line 25)
- `app/service/message_service.py` — validation + creation (line 36)
- `app/repositories/message_repository.py` — DB insert (line 19)
- `app/schemas/message.py` — `MessageCreate` and `MessageResponse` schemas

---

## 4. Retrieve Messages (with Cursor Pagination)

**Endpoint:** `GET /api/v1/conversations/{conversation_id}/messages?limit=30&cursor={msg_id}`

**Code flow:**

```
Frontend                    Backend
────────                    ───────
User selects a
conversation (or
scrolls up for older)
        │
        ▼
GET /conversations/        message_controller.py
  {id}/messages       →        │
  ?limit=30                    ▼
  &cursor=...              get_current_user()
                               │
                               ▼
                           MessageService
                           .list_messages()
                               │
                               ├── _validate_membership()
                               │   (same as above)
                               │
                               └── MessageRepository.list_by_conversation()
                                       │
                                       ├── SELECT * FROM messages
                                       │   WHERE conversation_id = ...
                                       │   AND deleted_at IS NULL
                                       │   ORDER BY created_at DESC
                                       │
                                       ├── If cursor provided:
                                       │   Look up cursor message's created_at
                                       │   Add WHERE created_at < cursor_created_at
                                       │
                                       ├── LIMIT 31 (limit + 1)
                                       │   If 31 rows come back → has_more = true
                                       │   Return only first 30
                                       │
                                       └── next_cursor = last message's ID
                               │
                               ▼
                           Each message → _message_to_response()
                               │
                               ▼
                           Return PaginatedMessages {
                               messages: [...],
                               next_cursor: "uuid-or-null",
                               has_more: true/false
                           }
```

**Why cursor pagination instead of OFFSET?**

`OFFSET 100000` scans and discards 100k rows. Cursor-based pagination uses an indexed `WHERE created_at < X` which is O(log n) regardless of how deep you are in the history.

**Key files:**
- `app/controller/message_controller.py` — route handler (line 92)
- `app/service/message_service.py` — orchestration (line 80)
- `app/repositories/message_repository.py` — cursor query (line 46)

---

## Frontend ↔ Backend Interaction

The frontend (`frontend/index.html`) is a single-file vanilla HTML/CSS/JS app. No React, no build step.

**How it ties together:**

| User Action | API Call | Auth Header |
|---|---|---|
| Switch user (Alice/Bob/Mark) | `GET /api/v1/users` | `X-User-Id: {selected}` |
| Page load | `GET /api/v1/conversations` | `X-User-Id: {current}` |
| Click a conversation | `GET /api/v1/conversations/{id}/messages` | `X-User-Id: {current}` |
| Type + Send | `POST /api/v1/conversations/{id}/messages` | `X-User-Id: {current}` |
| Create conversation | `POST /api/v1/conversations` | `X-User-Id: {current}` |
| Scroll up (older msgs) | `GET .../messages?cursor={last_id}` | `X-User-Id: {current}` |

**User switching** just changes the `X-User-Id` header. The backend sees a different user. No tokens, no cookies — just a header swap for dev purposes.

---

## Running the Demo

```bash
# 1. Start infrastructure (from backend/)
docker compose up -d

# 2. Start the FastAPI server (from backend/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Open the frontend
# Just open frontend/index.html in your browser
```

**Demo script:**

1. Open the app → you're logged in as **Alice**
2. Click **"+ New Conversation"** → name it, check Bob and Mark → **Create**
3. Type a few messages as Alice → they appear instantly
4. Switch to **Bob** (click the Bob button in the sidebar)
5. Bob sees the same conversation → click it → **Alice's messages are there**
6. Bob sends a message → it appears
7. Switch back to **Alice** → click the conversation → **Bob's message is there too**

This proves: create, send, persist, and retrieve all work across users.
