## Conversation Endpoints

### POST /conversation

Create a conversation.

**INPUT:**

- `name`
- `description`
- `user IDs`

**LOGIC:**

1. Authenticate requesting user.
2. Validate request.
3. Create conversation.
4. Add creator as owner/admin.
5. Add initial members.
6. Return conversation metadata.

---

### GET /conversations

Return conversations accessible to the current user.

**LOGIC:**

1. Authenticate user.
2. Query `conversation_members`.
3. Fetch and return every conversation current user is part of.

---

### GET /conversations/{conversation_id}

Return conversation metadata.

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Fetch conversation.
4. Return metadata.

---

### PUT /conversations/{conversation_id}

Update conversation metadata.

**LOGIC:**

1. Authenticate user.
2. Validate membership and verify admin permission.
3. Validate changes.
4. Update conversation.
5. Publish a `conversation.updated` realtime event.
6. Return updated conversation.

---

### DELETE /conversations/{conversation_id}

Deactivate a conversation.

**LOGIC:**

1. Authenticate user.
2. Validate membership and verify admin permission.
3. Soft-delete the conversation.
4. Publish a `conversation.deleted` realtime event.

---

## Member Endpoints

### GET /conversations/{conversation_id}/members

Return conversation members.

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Query active members.
4. Return users and their conversation roles.

---

### POST /conversations/{conversation_id}/members

Add one or more members.

**LOGIC:**

1. Authenticate user.
2. Validate membership and verify admin permission.
3. Validate target users.
4. Verify they are not already active members.
5. Insert membership records.
6. Publish `member.added`.
7. Return updated membership information.

---

### DELETE /conversations/{conversation_id}/members/{user_id}

Remove a member.

**LOGIC:**

1. Authenticate user.
2. Validate membership and verify admin permission.
3. Validate target member.
4. Prevent invalid owner removal if the conversation requires an owner.
5. Deactivate/remove membership.
6. Publish `member.removed`.

---

### PUT /conversations/{conversation_id}/members/{user_id}

Change a member's role.

**LOGIC:**

1. Authenticate user.
2. Validate membership and verify admin permission.
3. Validate requested role.
4. Apply role change.
5. Publish `member.role_updated`.

---

## Message Endpoints

### GET /conversations/{conversation_id}/messages

Fetch message history.

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Validate pagination cursor.
4. Query messages belonging to the conversation.
5. Order chronologically for client display.
6. Include necessary attachment metadata.
7. Return messages plus pagination information.

---

### GET /conversations/{conversation_id}/messages/{message_id}

Fetch a specific message (search).

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Validate message ID.
4. Query message.
5. Verify it belongs to the conversation.
6. Return message.

---

### PUT /conversations/{conversation_id}/messages/{message_id}

Edit a message.

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Fetch message.
4. Verify sender is allowed to edit.
5. Reject deleted messages.
6. Validate new content.
7. Update content and `edited_at`.
8. Commit transaction.
9. Publish `message.updated`.
10. Return updated message.

---

### DELETE /conversations/{conversation_id}/messages/{message_id}

Delete a message.

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Fetch message.
4. Verify sender/admin permission.
5. Set `deleted_at`.
6. Replace exposed content with a deleted-message representation at serialization time.
7. Publish `message.deleted`.

---

### GET /conversations/{conversation_id}/messages/search

Search for a message.

**LOGIC:**

1. Authenticate user.
2. Validate membership.
3. Validate search query.
4. Search only messages belonging to that conversation.
5. Apply cursor pagination.
6. Return matching messages.
7. Return next cursor.

---

## Realtime Endpoint

### WS /ws/conversations/{conversation_id}

Primary realtime endpoint.

**CONNECTION FLOW:**

1. Client opens WebSocket.
2. Authenticate user from the connection credentials.
3. Verify conversation membership.
4. Register socket with local connection manager.
5. Subscribe local server to the relevant Redis channel.
6. Send connection acknowledgement.
7. Begin receiving client events.
8. Handle disconnect/reconnect cleanup.

---

## Media Endpoints

### POST /media/upload

Authorize a client to upload a media/file object to Azure Blob Storage.

**INPUT:**

- `filename`
- `content type`
- `file size`
- `optional media category`

**LOGIC:**

1. Authenticate user.
2. Validate file type.
3. Validate file size.
4. Generate a unique blob name.
5. Generate Azure upload authorization/SAS information.
6. Return upload information to client.
7. Client uploads directly to Azure.

---

## Services / Functions

### AuthService

| Function | Description |
|---|---|
| `authenticate_user(token)` | Validate credentials/token and return the current user |
| `authorize_membership(user_id, conversation_id)` | Verify the user is an active member of the conversation |
| `authorize_admin(user_id, conversation_id)` | Verify the user has admin/owner role in the conversation |

---

### ConversationService

| Function | Description |
|---|---|
| `create_conversation(name, description, creator_id, member_ids)` | Create a conversation, add creator as owner, add initial members |
| `get_conversations(user_id)` | Return all conversations the user belongs to |
| `get_conversation(conversation_id)` | Return a single conversation's metadata |
| `update_conversation(conversation_id, updates)` | Update name/description, publish `conversation.updated` event |
| `delete_conversation(conversation_id)` | Soft-delete the conversation, publish `conversation.deleted` event |

---

### MemberService

| Function | Description |
|---|---|
| `get_members(conversation_id)` | Return active members and their roles |
| `add_members(conversation_id, user_ids)` | Add users, prevent duplicates, publish `member.added` |
| `remove_member(conversation_id, user_id)` | Deactivate membership (prevent owner removal), publish `member.removed` |
| `update_role(conversation_id, user_id, role)` | Change a member's role, publish `member.role_updated` |

---

### MessageService

| Function | Description |
|---|---|
| `send_message(conversation_id, sender_id, content, message_type, reply_to_id?, attachment?)` | Validate, persist message to DB, publish via Redis |
| `get_messages(conversation_id, cursor?, limit?)` | Cursor-paginated message history (chronological order) |
| `get_message(conversation_id, message_id)` | Fetch a single message by ID |
| `edit_message(message_id, sender_id, new_content)` | Verify ownership, update content + `edited_at`, publish `message.updated` |
| `delete_message(message_id, user_id)` | Soft-delete (`deleted_at`), publish `message.deleted` |
| `search_messages(conversation_id, query, cursor?, limit?)` | Search messages via ILIKE / full-text, return cursor-paginated results |

---

### MediaService

| Function | Description |
|---|---|
| `request_upload(user_id, filename, content_type, file_size, category?)` | Validate file type/size, generate unique blob name, return Azure SAS upload URL |
| `create_attachment(message_id, blob_name, content_type, file_size)` | Persist attachment metadata in `message_attachments` |

---

### ConnectionManager (WebSocket)

| Function | Description |
|---|---|
| `connect(conversation_id, user_id, websocket)` | Register socket, subscribe to Redis channel, send ack |
| `disconnect(conversation_id, user_id, websocket)` | Unregister socket, unsubscribe if no connections remain |
| `send_to_user(user_id, event)` | Send a realtime event to a specific user's connections |
| `broadcast_to_conversation(conversation_id, event)` | Fan-out an event to all connected members in a conversation |
| `handle_client_event(user_id, raw_event)` | Parse incoming WebSocket JSON and dispatch to the appropriate service |

---

### RedisPubSubService

| Function | Description |
|---|---|
| `publish(channel, event)` | Publish a serialized event to `conversation:{id}` channel |
| `subscribe(channel, callback)` | Subscribe local server to a conversation channel |
| `unsubscribe(channel)` | Unsubscribe when no local connections remain for that channel |

---

### ReadReceiptService

| Function | Description |
|---|---|
| `mark_read(message_id, user_id)` | Record read timestamp in `message_reads`, publish `message.read` |
| `get_read_info(message_id)` | Return list of users who read the message and when |

---

### SearchService

| Function | Description |
|---|---|
| `search(conversation_id, query, cursor?, limit?)` | ILIKE / full-text search within a conversation, cursor-paginated |

---

### TagService *(future)*

| Function | Description |
|---|---|
| `add_tag(message_id, tag, user_id)` | Attach a label (e.g. `#important`) to a message |
| `remove_tag(message_id, tag)` | Remove a tag from a message |
| `get_tags(message_id)` | List tags on a message |