from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status, WebSocketException, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List
from app.database.connection import get_db
from app.websocket.manager import manager
from app.database import models
from app.schemas import message as message_schema
from jose import JWTError, jwt
from app.core.config import settings
from pydantic import ValidationError

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Standard HTTP Dependency to authenticate a REST request.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@router.get("/history/{contact_id}", response_model=List[message_schema.MessageResponse])
def get_chat_history(
    contact_id: int, 
    limit: int = 50,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chat history between the current user and a contact.
    """
    messages = db.query(models.Message).filter(
        or_(
            and_(models.Message.sender_id == user.id, models.Message.receiver_id == contact_id),
            and_(models.Message.sender_id == contact_id, models.Message.receiver_id == user.id)
        )
    ).order_by(models.Message.timestamp.desc()).limit(limit).all()
    
    # Reverse to return messages in chronological order (oldest first)
    return list(reversed(messages))

async def get_ws_current_user(
    websocket: WebSocket,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Dependency to authenticate a WebSocket connection using a JWT token from query parameters.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
        
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
        
        return user
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    user: models.User = Depends(get_ws_current_user),
    db: Session = Depends(get_db)
):
    """
    The main WebSocket endpoint for real-time messaging.
    """
    await manager.connect(websocket, user.id)
    try:
        while True:
            try:
                # Wait for JSON payload from the client directly
                parsed_data = await websocket.receive_json()
                
                # Validate using Pydantic schema
                message_data = message_schema.MessageCreate(**parsed_data)
                
                # Validate receiver exists
                receiver = db.query(models.User).filter(models.User.id == message_data.receiver_id).first()
                if not receiver:
                    await manager.send_personal_message({
                        "sender_id": 0,
                        "sender_name": "System",
                        "message": "Receiver not found."
                    }, user.id)
                    continue
                
                # Save message to database with Rollback strategy
                try:
                    new_message = models.Message(
                        sender_id=user.id,
                        receiver_id=message_data.receiver_id,
                        content=message_data.message
                    )
                    db.add(new_message)
                    db.commit()
                    db.refresh(new_message)
                except Exception as db_err:
                    db.rollback()
                    print(f"Database save error: {db_err}")
                    await manager.send_personal_message({
                        "sender_id": 0,
                        "sender_name": "System",
                        "message": "Failed to save message."
                    }, user.id)
                    continue
                
                message_payload = {
                    "id": new_message.id,
                    "sender_id": user.id,
                    "sender_name": user.username,
                    "message": message_data.message,
                    "timestamp": str(new_message.timestamp)
                }
                
                # Send the message to the target user
                await manager.send_personal_message(message_payload, message_data.receiver_id)
                
                # Send the message back to the sender for UI synchronization
                await manager.send_personal_message(message_payload, user.id)
                
            except ValidationError:
                # Inform sender if it wasn't valid structure
                await manager.send_personal_message({
                    "sender_id": 0,
                    "sender_name": "System",
                    "message": "Message format requires valid 'receiver_id' and 'message'."
                }, user.id)
            except ValueError:
                # Catch JSONDecodeError
                await manager.send_personal_message({
                    "sender_id": 0,
                    "sender_name": "System",
                    "message": "Please send message as JSON."
                }, user.id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
