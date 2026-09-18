Your stack:

* **FastAPI** — HTTP API + WebSocket endpoints
* **SQLAlchemy Async** — DB access
* **TimescaleDB** — PostgreSQL-compatible database
* **Redis** — Pub/Sub + potentially presence later
* **Azure Blob Storage** — images/videos/files/tasks
* **WebSockets** — realtime delivery

And importantly: **we'll keep the architecture integration-friendly**, so you aren't painting yourself into a corner when this gets shoved into the larger project.

---

# Overall Architecture

Very roughly:

```text
                    ┌──────────────────┐
                    │     Client       │
                    └────────┬─────────┘
                             │
                     HTTP / WebSocket
                             │
                 ┌───────────▼───────────┐
                 │     FastAPI Server     │
                 │                       │
                 │ REST API   WebSocket  │
                 └──────┬─────────┬──────┘
                        │         │
              ┌─────────▼───┐   ┌▼────────────┐
              │ TimescaleDB │   │    Redis    │
              │             │   │   Pub/Sub   │
              │ users       │   └──────┬──────┘
              │ groups      │          │
              │ messages    │    ┌─────▼──────┐
              │ receipts    │    │ Other API  │
              └─────────────┘    │  Servers   │
                                  └────────────┘

                        Azure Blob Storage
                               ▲
                               │
                     images / videos / files
```

The **core idea** we'll eventually implement is:

```text
Client A
   │
   │ WebSocket
   ▼
Server 1
   │
   │ Redis Pub/Sub
   ▼
Server 2
   │
   │ WebSocket
   ▼
Client B
```

That's the important bit for the "multiple servers" requirement.

---

# The Build Plan

I'm going to split this into **12 phases**. Each phase should leave you with something actually working.

## Phase 0 — Project Skeleton

### Build

Set up:

```text
chat-service/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │
│   │   └── websocket/
│   │
│   ├── models/
│   │
│   ├── schemas/
│   │
│   ├── services/
│   │
│   ├── repositories/
│   │
│   ├── db/
│   │
│   ├── redis/
│   │
│   └── core/
│
├── migrations/
├── tests/
├── requirements.txt
└── .env
```

Set up:

* FastAPI
* SQLAlchemy async
* PostgreSQL/TimescaleDB connection
* Alembic
* Redis connection
* basic health endpoint

### End goal

```http
GET /health

{
    "status": "ok"
}
```

And the server successfully connects to DB + Redis.

---

# Phase 1 — Database Design

Before touching WebSockets, **get the data model right**.

We need the minimum viable entities.

### Users

```text
users
-----
id
name
email
...
```

We're assuming authentication may eventually come from the larger application, so don't over-engineer user auth here.

---

### Conversations

Everything is a group.

A DM is simply:

```text
conversation
    members = [Alice, Bob]
```

So:

```text
conversations
-------------
id
name
created_at
created_by
```

---

### Conversation Members

```text
conversation_members
--------------------
conversation_id
user_id
role
joined_at
```

Potential roles:

```text
member
admin
```

Later:

```text
moderator
owner
...
```

---

### Messages

This is the big one.

```text
messages
--------
id
conversation_id
sender_id

message_type
content

reply_to_message_id

created_at
updated_at
deleted_at
```

`message_type` could be:

```text
text
image
video
file
task
```

---

### Message Attachments

Don't shove Azure URLs directly into `messages`.

Instead:

```text
message_attachments
-------------------
id
message_id
blob_url
blob_name
content_type
file_size
```

This makes media extensible.

---

### Message Reactions/Tags

We'll eventually need tagging, but **don't build it yet**.

---

### Read Receipts

Something like:

```text
message_reads
-------------
message_id
user_id
read_at
```

This gives us:

> Alice, Bob and Charlie have seen message #123.

---

### End goal

You should be able to create:

```text
User
 ↓
Conversation
 ↓
Members
 ↓
Messages
```

with proper foreign keys and indexes.

### Important indexes

At minimum:

```text
messages(conversation_id, created_at)
messages(conversation_id, id)
conversation_members(conversation_id, user_id)
message_reads(message_id, user_id)
```

This will matter **a lot** once pagination/search enters the picture.

---

# Phase 2 — Basic REST API

Before realtime, make the boring shit work.

### Implement

```http
POST /conversations
GET  /conversations
GET  /conversations/{id}
```

Members:

```http
POST /conversations/{id}/members
DELETE /conversations/{id}/members/{user_id}
GET /conversations/{id}/members
```

Messages:

```http
GET /conversations/{id}/messages
```

For now, you can even have a temporary development endpoint:

```http
POST /conversations/{id}/messages
```

### End goal

You can use Postman/curl and do:

```text
create conversation
        ↓
add users
        ↓
send message
        ↓
retrieve messages
```

No WebSocket yet.

---

# Phase 3 — WebSocket Connection

NOW the fun begins.

Create something like:

```http
WS /ws/conversations/{conversation_id}
```

Client connects:

```text
Client
  │
  │ WebSocket handshake
  ▼
FastAPI
  │
  └── ConnectionManager
```

Create a connection manager responsible for:

```text
connect()
disconnect()
send_to_user()
send_to_conversation()
```

Initially, this can just be an in-memory dictionary.

Something conceptually like:

```text
conversation_id
      ↓
connected users
      ↓
WebSocket connections
```

### End goal

Open two clients.

```text
Alice ───── WebSocket ───── Server
Bob   ───── WebSocket ───── Server
```

If Alice sends:

```text
Hello Bob
```

Bob receives it **without polling**.

🎉 You officially have realtime chat.

---

# Phase 4 — Actual Messaging Protocol

Now define what travels over the WebSocket.

Don't randomly throw JSON around forever. Establish a protocol.

For example:

### Client → Server

```json
{
    "type": "message.send",
    "conversation_id": "...",
    "payload": {
        "content": "Hello!"
    }
}
```

Server → Client:

```json
{
    "type": "message.created",
    "data": {
        "id": "...",
        "conversation_id": "...",
        "sender_id": "...",
        "content": "Hello!",
        "created_at": "..."
    }
}
```

Eventually:

```text
message.send
message.created

message.edit
message.updated

message.delete
message.deleted

message.read
message.read

message.typing
message.typing
```

etc.

### End goal

You have a **defined realtime protocol** rather than spaghetti JSON.

---

# Phase 5 — Authentication + Authorization

Now stop random strangers from joining Alice's secret group chat.

We need to distinguish:

### Authentication

> Who are you?

### Authorization

> Are you allowed to do this?

For example:

```text
User → WebSocket connection
        ↓
Authenticate
        ↓
Identify user_id
        ↓
Check conversation membership
        ↓
Allow / reject connection
```

And for every message:

```text
Can user X send to conversation Y?
```

Check:

```text
conversation_members
```

This also applies to:

* sending messages
* editing
* deleting
* adding members
* removing members
* reading
* tagging

---

# Phase 6 — Redis Pub/Sub + Multiple Servers

This is where your project stops being:

> "FastAPI WebSocket demo"

and becomes an actual realtime backend.

Imagine:

```text
Alice
  │
  ▼
Server A
```

while Bob happens to be connected to:

```text
Server B
  │
  ▼
Bob
```

Server A cannot directly access Server B's WebSocket connection.

So:

```text
Alice
  │
  ▼
Server A
  │
  │ Redis PUBLISH
  ▼
Redis
  │
  │ SUBSCRIBE
  ▼
Server B
  │
  ▼
Bob
```

### Redis channels

Something like:

```text
conversation:{conversation_id}
```

Server subscribes to conversations where it has active connections.

### End goal

Run:

```text
FastAPI Server 1
FastAPI Server 2
Redis
TimescaleDB
```

and verify:

```text
Client A → Server 1
             ↓
           Redis
             ↓
Client B ← Server 2
```

**This is a major MVP milestone.**

---

# Phase 7 — Message Persistence + Pagination

Now combine:

```text
WebSocket
+
Postgres
+
Redis
```

When Alice sends:

```text
Hello
```

the flow becomes:

```text
Alice
 │
 │ WebSocket
 ▼
FastAPI
 │
 ├── Validate
 │
 ├── Authorize
 │
 ├── INSERT message → DB
 │
 └── Publish event → Redis
                     │
                     ▼
                  Servers
                     │
                     ▼
                   Users
```

### Important principle

**Database is the source of truth.**

Redis Pub/Sub is for **delivery**, not permanent storage.

If Bob is offline:

```text
Redis event
     ↓
Bob doesn't receive it
```

That's fine.

The message is already in:

```text
TimescaleDB
```

Bob fetches it when he comes back.

---

# Phase 8 — Message History + Smart Pagination

Now implement:

```http
GET /conversations/{id}/messages
```

Don't return 50,000 messages because someone opened a group chat from 2019.

Start with something like:

```text
20–50 messages
```

Use cursor pagination rather than offset pagination.

Conceptually:

```http
GET /messages?before=<message_id>&limit=30
```

Initial load:

```text
latest 30
```

Scroll upward:

```text
30 older
```

Again:

```text
30 older
```

etc.

### Why cursor pagination?

Because:

```text
OFFSET 100000
```

gets increasingly stupid on large tables.

Cursor-based querying is much more appropriate for chat.

---

# Phase 9 — Message Operations

Now add the rest of the basic message lifecycle.

## Editing

```text
message.edit
```

Authorization:

```text
Is sender allowed to edit?
```

Then:

```text
UPDATE messages
SET content = ...
updated_at = ...
```

Broadcast:

```text
message.updated
```

---

## Deleting

Prefer **soft deletion** for chat.

Instead of:

```sql
DELETE FROM messages;
```

do:

```text
deleted_at = NOW()
```

Then clients see:

```text
"This message was deleted"
```

rather than the message completely disappearing from your database.

---

## Replying

We already prepared for this:

```text
reply_to_message_id
```

So:

```text
Alice:
    "Where are you?"

Bob:
    "At home."
```

can reference Alice's message.

---

# Phase 10 — Read Receipts + Message Info

Now:

```text
Alice sends message
        ↓
Bob receives it
        ↓
Bob opens/sees it
        ↓
Bob sends "read"
        ↓
Server records it
```

For example:

```json
{
    "type": "message.read",
    "message_id": "123"
}
```

Database:

```text
message_reads

message_id | user_id | read_at
-----------+---------+---------
123        | Bob     | ...
123        | Charlie | ...
```

Then:

```http
GET /messages/{id}/info
```

could return:

```json
{
    "message_id": "123",
    "read_by": [
        {
            "user_id": "bob",
            "read_at": "..."
        },
        {
            "user_id": "charlie",
            "read_at": "..."
        }
    ]
}
```

### End goal

WhatsApp-ish:

```text
✓ Sent
✓✓ Delivered
✓✓ Read
```

plus:

> Seen by Bob, Charlie, David.

---

# Phase 11 — Media + Tasks

Now we touch Azure Blob Storage.

**Important:** the chat service should NOT receive giant videos and then shove them through your WebSocket.

Absolutely not. 😂

Instead:

```text
Client
  │
  │ Request upload
  ▼
Chat API
  │
  │ Generate upload URL / SAS
  ▼
Azure Blob Storage
  ▲
  │
  │ Direct upload
Client
```

Then:

```text
Client
  │
  │ message.send
  │ attachment metadata
  ▼
Chat API
  │
  ▼
DB
```

Example:

```json
{
    "type": "message.send",
    "payload": {
        "message_type": "image",
        "content": "Look at this",
        "attachment": {
            "blob_name": "...",
            "content_type": "image/jpeg"
        }
    }
}
```

---

### Tasks

You said tasks are objects created somewhere else.

Perfect.

**Don't recreate the task system inside chat.**

The chat message simply references the task:

```text
message
   │
   └── task_id
```

Something like:

```json
{
    "message_type": "task",
    "task_id": "abc123"
}
```

The larger project owns:

```text
task creation
task state
task assignment
task metadata
```

Chat owns:

```text
"Task X was shared in this conversation."
```

This keeps our boundaries sane.

---

# Phase 12 — Search

Now we build chat search.

Basic:

```http
GET /conversations/{id}/messages/search?q=hello
```

We can initially use PostgreSQL search.

Potentially:

```text
ILIKE
```

for the MVP.

If the dataset/search requirements become serious, move toward PostgreSQL full-text search / indexes later.

Search results need pagination too.

For example:

```text
Search: "meeting"

       ↓

[message 827]
[message 654]
[message 492]
[message 301]
```

Then when scrolling:

```text
older search results
        ↓
next page
```

Unlike normal chat history:

```text
normal chat:
scroll UP → older messages
```

Search:

```text
search results
scroll DOWN → more results
```

Exactly as you described.

---

# Phase 13 — Tags

Now add message tagging.

First decide what **"tagging"** means in this application.

If you mean users can tag messages with arbitrary labels:

```text
message_tags
------------
message_id
tag
created_by
created_at
```

Then:

```text
#important
#todo
#meeting
```

could be attached to messages.

If you mean **@mentions**, that's a different feature:

```text
@alice
@bob
```

and deserves a separate model/notification mechanism.

We can support both later without mixing them.

---

# Phase 14 — Hardening

Only after the MVP works.

Add:

### Connection handling

```text
connect
disconnect
reconnect
timeout
heartbeat
```

### WebSocket heartbeat

```text
ping
pong
```

### Redis failure handling

What happens if:

```text
Redis dies
```

### DB failure handling

What happens if:

```text
DB query fails
```

### Duplicate messages

Important because clients can retry.

Potentially introduce:

```text
client_message_id
```

so:

```text
Client retries message
        ↓
Server sees same client_message_id
        ↓
Doesn't create duplicate
```

That's an extremely useful addition.

---