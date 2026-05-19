from pydantic import BaseModel
from datetime import datetime

class MessageCreate(BaseModel):
    receiver_id: int
    message: str

class MessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    timestamp: datetime
    is_delivered: bool
    is_seen: bool

    class Config:
        from_attributes = True
