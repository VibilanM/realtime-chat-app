"""In-memory WebSocket connection manager.

Tracks which WebSocket clients are connected to which conversations
so we can broadcast new messages to the right clients.
"""

import json
import uuid

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections grouped by conversation ID."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, conversation_id: str, websocket: WebSocket):
        """Accept a WebSocket and register it under a conversation."""
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)

    def disconnect(self, conversation_id: str, websocket: WebSocket):
        """Remove a WebSocket from a conversation's connection list."""
        connections = self.active_connections.get(conversation_id, [])
        if websocket in connections:
            connections.remove(websocket)
        # Clean up empty lists
        if not connections and conversation_id in self.active_connections:
            del self.active_connections[conversation_id]

    async def broadcast_to_conversation(self, conversation_id: str, data: dict):
        """Send a JSON message to all clients connected to a conversation."""
        connections = self.active_connections.get(conversation_id, [])
        # Send to each connected client; remove any that have disconnected
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.append(websocket)
        # Clean up broken connections
        for ws in disconnected:
            self.disconnect(conversation_id, ws)


# Single global instance used by the whole application
manager = ConnectionManager()
