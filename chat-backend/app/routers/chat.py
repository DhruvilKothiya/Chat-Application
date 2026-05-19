from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status, WebSocketException, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List
from datetime import datetime, timezone
from app.database.connection import get_db
from app.websocket.manager import manager
from app.database import models
from app.schemas import message as message_schema
from app.core.auth import get_current_user, get_ws_current_user
from pydantic import ValidationError

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

@router.get("/history/{contact_id}", response_model=List[message_schema.MessageResponse])
def get_chat_history(
    contact_id: int, 
    limit: int = 50,
    offset: int = 0,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chat history between the current user and a contact, with offset pagination.
    """
    messages = db.query(models.Message).filter(
        or_(
            and_(models.Message.sender_id == user.id, models.Message.receiver_id == contact_id),
            and_(models.Message.sender_id == contact_id, models.Message.receiver_id == user.id)
        )
    ).order_by(models.Message.timestamp.desc()).offset(offset).limit(limit).all()
    
    # Reverse to return messages in chronological order (oldest first)
    return list(reversed(messages))

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    user: models.User = Depends(get_ws_current_user),
    db: Session = Depends(get_db)
):
    """
    The main WebSocket endpoint for real-time messaging using Event Architecture.
    """
    await manager.connect(websocket, user.id)
    # Broadcast online status
    await manager.broadcast_event("user_online", {"user_id": user.id}, exclude_user=user.id)
    
    # When user connects, mark pending messages as delivered
    undelivered = db.query(models.Message).filter(
        models.Message.receiver_id == user.id,
        models.Message.is_delivered == False
    ).all()
    for msg in undelivered:
        msg.is_delivered = True
        await manager.send_personal_event("message_delivered", {"message_id": msg.id}, msg.sender_id)
    if undelivered:
        db.commit()
    
    try:
        while True:
            try:
                parsed_payload = await websocket.receive_json()
                event = parsed_payload.get("event")
                data = parsed_payload.get("data", {})
                
                if event == "send_message":
                    try:
                        message_data = message_schema.MessageCreate(**data)
                        receiver = db.query(models.User).filter(models.User.id == message_data.receiver_id).first()
                        if not receiver:
                            await manager.send_personal_event("error", {"message": "Receiver not found."}, user.id)
                            continue
                            
                        # Save message
                        is_receiver_online = await manager.is_user_online(message_data.receiver_id)
                        new_message = models.Message(
                            sender_id=user.id,
                            receiver_id=message_data.receiver_id,
                            content=message_data.message,
                            is_delivered=True if is_receiver_online else False
                        )
                        db.add(new_message)
                        db.commit()
                        db.refresh(new_message)
                        
                        msg_payload = {
                            "id": new_message.id,
                            "sender_id": user.id,
                            "receiver_id": new_message.receiver_id,
                            "message": message_data.message,
                            "timestamp": str(new_message.timestamp),
                            "is_delivered": new_message.is_delivered,
                            "is_seen": new_message.is_seen
                        }
                        
                        # Send to receiver
                        await manager.send_personal_event("receive_message", msg_payload, message_data.receiver_id)
                        # Sync back to sender
                        await manager.send_personal_event("message_sent", msg_payload, user.id)
                        
                        # Trigger delivery event if immediately delivered
                        if new_message.is_delivered:
                            await manager.send_personal_event("message_delivered", {"message_id": new_message.id}, user.id)
                            
                    except ValidationError:
                        await manager.send_personal_event("error", {"message": "Invalid message data."}, user.id)
                        
                elif event == "typing":
                    receiver_id = data.get("receiver_id")
                    if receiver_id:
                        await manager.send_personal_event("typing", {"sender_id": user.id}, receiver_id)
                        
                elif event == "seen":
                    message_id = data.get("message_id")
                    if message_id:
                        msg = db.query(models.Message).filter(models.Message.id == message_id).first()
                        if msg and msg.receiver_id == user.id:
                            msg.is_seen = True
                            db.commit()
                            await manager.send_personal_event("message_seen", {"message_id": message_id}, msg.sender_id)
                            
                elif event == "ping":
                    await manager.refresh_user_presence(user.id)
                    await manager.send_personal_event("pong", {}, user.id)
                    
                elif event == "ack":
                    message_id = data.get("message_id")
                    if message_id:
                        msg = db.query(models.Message).filter(models.Message.id == message_id).first()
                        if msg and msg.receiver_id == user.id and not msg.is_delivered:
                            msg.is_delivered = True
                            db.commit()
                            await manager.send_personal_event("message_delivered", {"message_id": message_id}, msg.sender_id)
                    
            except ValueError:
                await manager.send_personal_event("error", {"message": "Invalid JSON format."}, user.id)
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket, user.id)
        
        # Update last seen timestamp
        user.last_seen = func.now()
        db.commit()
        
        # Broadcast offline status
        await manager.broadcast_event("user_offline", {"user_id": user.id})
