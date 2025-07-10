"""
WebSocket endpoint and broadcast manager for real-time event updates and notifications.

Triggers: 
- New event creation
- Event modification
- Event deletion
- New invite/participant status change

This module provides:
- FastAPI APIRouter ("/ws/events" endpoint) supporting authenticated real-time client connections.
- Broadcast to all clients on event DB changes.
- Helper for emitting server-side event updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi import Query
from typing import List, Dict
import asyncio
import logging

router = APIRouter(tags=["websockets"])

class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages/event notifications."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_map: Dict[int, WebSocket] = {}

    # PUBLIC_INTERFACE
    async def connect(self, websocket: WebSocket, user_id: int):
        """
        Accepts a client WebSocket and adds to active list, mapped by user_id.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_map[user_id] = websocket

    # PUBLIC_INTERFACE
    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Removes disconnected WebSocket from list. Cleans up user mapping.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if user_id in self.user_map and self.user_map[user_id] == websocket:
            del self.user_map[user_id]

    # PUBLIC_INTERFACE
    async def send_personal_message(self, message: dict, user_id: int):
        """
        Sends a message to a specific user if their connection exists.
        """
        websocket = self.user_map.get(user_id)
        if websocket:
            await websocket.send_json(message)

    # PUBLIC_INTERFACE
    async def broadcast(self, message: dict):
        """
        Broadcasts a message to all connected clients.
        """
        for connection in list(self.active_connections):  # make a copy in case of disconnects
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.warning(f"Error broadcasting to client: {e}")

manager = ConnectionManager()

# PUBLIC_INTERFACE
@router.websocket("/ws/events")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., alias="token"),
):
    """
    WebSocket endpoint for real-time event updates and notifications.

    - Connect using ?token=JWT in the query string (same as REST Bearer token).
    - Receives JSON notifications of event create/modify/delete/invite in real time.
    - Broadcasts are sent via emit_event_update.
    """
    # Token-based authentication (stateless, just like REST endpoints)
    from jose import jwt, JWTError
    import os

    SECRET_KEY = os.getenv("JWT_SECRET", "dev_secret_key")
    ALGORITHM = "HS256"
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id)
    try:
        # Main receive loop: no-op, can be extended for client requests
        while True:
            try:
                _ = await asyncio.wait_for(websocket.receive_text(), timeout=600)
                # We don't process client messages (only notifications sent by backend)
                # Could extend this for "ping"/"typing", etc.
            except asyncio.TimeoutError:
                # Send a ping message to keep alive
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id)

# PUBLIC_INTERFACE
async def emit_event_update(event_type: str, payload: dict):
    """
    Emits a real-time notification to all connected clients.
    Used by event CRUD operations.

    Args:
        event_type (str): One of "created", "updated", "deleted", "invited", "participation".
        payload (dict): Event data relevant to the update.
    """
    message = {"type": event_type, "payload": payload}
    await manager.broadcast(message)
