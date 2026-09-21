"""WebSocket endpoint for real-time conversation updates."""

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_user_from_username
from app.config.database import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.member_repository import MemberRepository
from app.websocket.connection_manager import manager

router = APIRouter()
logger = logging.getLogger("chat.websocket")


@router.websocket("/ws/conversations/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    user: str = Query(..., description="Username (alice, bob, or mark)"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time conversation events.
    
    URL Pattern:
      ws://<host>/ws/conversations/<conversation_id>?user=alice
    """
    # 1. Validate conversation_id format
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        logger.warning("Rejected WebSocket connection: Invalid UUID '%s'", conversation_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid conversation ID format")
        return

    # 2. Authenticate User
    try:
        authenticated_user = await get_user_from_username(user, db)
    except Exception as err:
        logger.warning("Rejected WebSocket connection for user '%s': %s", user, err)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return

    # 3. Authorize Membership
    conv_repo = ConversationRepository(db)
    member_repo = MemberRepository(db)

    conversation = await conv_repo.get_by_id(conv_uuid)
    if conversation is None:
        logger.warning("Rejected WebSocket: Conversation %s not found", conversation_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Conversation not found")
        return

    is_member = await member_repo.is_member(conv_uuid, authenticated_user.id)
    if not is_member:
        logger.warning(
            "Rejected WebSocket: User '%s' is not a member of conversation %s",
            user,
            conversation_id,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not a member of this conversation")
        return

    # 4. Accept connection and register with ConnectionManager
    # manager.connect accepts the websocket and tracks it
    await manager.connect(str(conv_uuid), websocket)
    logger.info("WebSocket connected: user '%s' on conversation %s", user, conversation_id)

    # Send connection acknowledgment frame
    await websocket.send_json({
        "type": "connected",
        "event": "connected",
        "data": {
            "conversation_id": str(conv_uuid),
            "user": user,
            "user_id": str(authenticated_user.id),
        },
    })

    # 5. Keep connection alive and wait for disconnect
    try:
        while True:
            # We listen for client frames (ping/pong or text)
            # In this architecture, actual messages are posted via HTTP POST
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user '%s' on conversation %s", user, conversation_id)
        manager.disconnect(str(conv_uuid), websocket)
    except Exception as err:
        logger.error("Unexpected WebSocket error on conversation %s: %s", conversation_id, err)
        manager.disconnect(str(conv_uuid), websocket)