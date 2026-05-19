import json
import asyncio
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
from app.core.config import settings

class ConnectionManager:
    def __init__(self):
        # Maps user_id to a list of active WebSockets on THIS backend instance
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.online_users = set()  # Local tracking, could be moved to Redis later
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.channel = "chat_events"

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
            if len(self.active_connections[user_id]) == 0:
                del self.active_connections[user_id]
                if user_id in self.online_users:
                    self.online_users.remove(user_id)

    # Publish events to Redis instead of sending locally
    async def send_personal_event(self, event: str, data: dict, user_id: int):
        payload = {
            "type": "personal",
            "user_id": user_id,
            "event": event,
            "data": data
        }
        await self.redis.publish(self.channel, json.dumps(payload))

    async def broadcast_event(self, event: str, data: dict, exclude_user: int = None):
        payload = {
            "type": "broadcast",
            "exclude_user": exclude_user,
            "event": event,
            "data": data
        }
        await self.redis.publish(self.channel, json.dumps(payload))

    # Actual sending mechanism (called by Redis listener)
    async def _send_to_local_user(self, event: str, data: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json({"event": event, "data": data})
                except Exception as e:
                    print(f"WebSocket send error: {e}")
                    self.disconnect(connection, user_id)

    async def _broadcast_to_local_users(self, event: str, data: dict, exclude_user: int = None):
        for user_id, connections in list(self.active_connections.items()):
            if exclude_user and user_id == exclude_user:
                continue
            for connection in list(connections):
                try:
                    await connection.send_json({"event": event, "data": data})
                except Exception as e:
                    print(f"WebSocket send error: {e}")
                    self.disconnect(connection, user_id)

    # Redis Pub/Sub Listener Task
    async def pubsub_reader(self):
        await self.pubsub.subscribe(self.channel)
        print("Subscribed to Redis channel: ", self.channel)
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    payload = json.loads(message["data"])
                    msg_type = payload.get("type")
                    event = payload.get("event")
                    data = payload.get("data")
                    
                    if msg_type == "personal":
                        user_id = payload.get("user_id")
                        await self._send_to_local_user(event, data, user_id)
                    elif msg_type == "broadcast":
                        exclude_user = payload.get("exclude_user")
                        await self._broadcast_to_local_users(event, data, exclude_user)
        except Exception as e:
            print(f"Redis Pub/Sub error: {e}")

manager = ConnectionManager()
