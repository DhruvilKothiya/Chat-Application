import json
import asyncio
import uuid
import logging
import redis.asyncio as redis
from fastapi import WebSocket
from typing import List, Dict
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INSTANCE_ID = uuid.uuid4().hex

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.channel = "chat_events"

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        # Global online presence via connection counting
        await self.redis.incr(f"user_connections:{user_id}")
        await self.refresh_user_presence(user_id)

    async def refresh_user_presence(self, user_id: int):
        """Refreshes the TTL of the user connection key to prevent leaks"""
        await self.redis.expire(f"user_connections:{user_id}", 120)

    async def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                # Decrease global connection count
                count = await self.redis.decr(f"user_connections:{user_id}")
                if count is not None:
                    if count <= 0:
                        await self.redis.delete(f"user_connections:{user_id}")
                    if count < 0:
                        logger.warning(f"Negative connection count for user {user_id}, resetting.")
                        await self.redis.set(f"user_connections:{user_id}", 0)
                    
            if len(self.active_connections[user_id]) == 0:
                del self.active_connections[user_id]

    async def is_user_online(self, user_id: int) -> bool:
        count = await self.redis.get(f"user_connections:{user_id}")
        return int(count or 0) > 0

    async def send_personal_event(self, event: str, data: dict, user_id: int):
        payload = {
            "type": "personal",
            "instance_id": INSTANCE_ID,
            "user_id": user_id,
            "event": event,
            "data": data
        }
        await self.redis.publish(self.channel, json.dumps(payload))

    async def broadcast_event(self, event: str, data: dict, exclude_user: int = None):
        payload = {
            "type": "broadcast",
            "instance_id": INSTANCE_ID,
            "exclude_user": exclude_user,
            "event": event,
            "data": data
        }
        await self.redis.publish(self.channel, json.dumps(payload))

    async def _send_to_local_user(self, event: str, data: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json({"event": event, "data": data, "instance_id": INSTANCE_ID})
                except Exception as e:
                    logger.error(f"WebSocket send error: {e}", exc_info=True)
                    await self.disconnect(connection, user_id)

    async def _broadcast_to_local_users(self, event: str, data: dict, exclude_user: int = None):
        for user_id, connections in list(self.active_connections.items()):
            if exclude_user and user_id == exclude_user:
                continue
            for connection in list(connections):
                try:
                    await connection.send_json({"event": event, "data": data, "instance_id": INSTANCE_ID})
                except Exception as e:
                    logger.error(f"WebSocket broadcast error: {e}", exc_info=True)
                    await self.disconnect(connection, user_id)

    async def pubsub_reader(self):
        await self.pubsub.subscribe(self.channel)
        logger.info(f"[{INSTANCE_ID}] Subscribed to Redis channel: {self.channel}")
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                payload = json.loads(message["data"])
                
                # We must process events from our own instance because 
                # send_personal_event only publishes to Redis and doesn't send locally!
                
                msg_type = payload.get("type")
                event = payload.get("event")
                data = payload.get("data")
                
                if msg_type == "personal":
                    user_id = payload.get("user_id")
                    await self._send_to_local_user(event, data, user_id)
                elif msg_type == "broadcast":
                    exclude_user = payload.get("exclude_user")
                    await self._broadcast_to_local_users(event, data, exclude_user)

    async def start_pubsub_loop(self):
        """Robust listener loop with reconnection"""
        while True:
            try:
                await self.pubsub_reader()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{INSTANCE_ID}] Redis Pub/Sub error: {e}, reconnecting in 5s...", exc_info=True)
                await asyncio.sleep(5)

    async def close(self):
        """Graceful shutdown cleanup"""
        try:
            await self.pubsub.unsubscribe(self.channel)
            await self.pubsub.close()
            await self.redis.close()
            logger.info(f"[{INSTANCE_ID}] Redis connection closed cleanly.")
        except Exception as e:
            logger.error(f"Error closing redis: {e}", exc_info=True)

manager = ConnectionManager()
