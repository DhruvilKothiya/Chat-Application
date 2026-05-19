from pydantic import BaseModel
from datetime import datetime

class MessageBase(BaseModel):
    receiver_id: int
    message: str

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    sender_id: int
    timestamp: datetime
    is_delivered: bool
    is_seen: bool

    class Config:
        from_attributes = True
