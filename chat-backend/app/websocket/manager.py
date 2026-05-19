from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict

class ConnectionManager:
    def __init__(self):
        # Maps user_id to a list of active WebSockets (allows multiple devices per user)
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.online_users = set()

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.online_users.add(user_id)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            # Clean up the key if user has no more active connections
            if len(self.active_connections[user_id]) == 0:
                del self.active_connections[user_id]
                if user_id in self.online_users:
                    self.online_users.remove(user_id)

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"WebSocket send error, cleaning up dead socket: {e}")
                    self.disconnect(connection, user_id)

    async def send_personal_event(self, event: str, data: dict, user_id: int):
        await self.send_personal_message({"event": event, "data": data}, user_id)

    async def broadcast(self, message: dict):
        for user_id, connections in list(self.active_connections.items()):
            for connection in list(connections):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"WebSocket send error, cleaning up dead socket: {e}")
                    self.disconnect(connection, user_id)

    async def broadcast_event(self, event: str, data: dict, exclude_user: int = None):
        payload = {"event": event, "data": data}
        for user_id, connections in list(self.active_connections.items()):
            if exclude_user and user_id == exclude_user:
                continue
            for connection in list(connections):
                try:
                    await connection.send_json(payload)
                except Exception as e:
                    print(f"WebSocket broadcast error, cleaning up dead socket: {e}")
                    self.disconnect(connection, user_id)

manager = ConnectionManager()
