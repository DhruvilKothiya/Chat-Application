import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(password_bytes, hashed_password_bytes)
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes")
        
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({
        "exp": expire,
        "iat": now
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh"
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
