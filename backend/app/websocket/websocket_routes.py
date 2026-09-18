"""WebSocket endpoint for real-time conversation updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.websocket.connection_manager import manager

router = APIRouter()


@router.websocket("/ws/conversations/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    user: str = Query(..., description="Username (alice, bob, or mark)"),
):
    """
    WebSocket connection for a conversation.

    Client connects with: ws://host/ws/conversations/{id}?user=alice
    Server sends message events as JSON: { "event": "message.created", "data": {...} }
    """
    # Register this client for the conversation
    await manager.connect(conversation_id, websocket)

    # Send acknowledgement so the client knows the connection is ready
    await websocket.send_json({
        "event": "connected",
        "data": {"conversation_id": conversation_id, "user": user},
    })

    try:
        # Keep the connection alive — listen for incoming messages
        # (We don't process client-sent messages; messages are sent via HTTP POST)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)
