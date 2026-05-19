from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.database import models, connection
from app.schemas import user as user_schema
from app.core import security
from app.core.config import settings
from datetime import timedelta

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/register", response_model=user_schema.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: user_schema.UserCreate, db: Session = Depends(connection.get_db)):
    # Check if user already exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_username = db.query(models.User).filter(models.User.username == user.username).first()
    if db_username:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create new user
    hashed_password = security.get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@router.post("/login", response_model=user_schema.Token)
def login(user_credentials: user_schema.UserLogin, db: Session = Depends(connection.get_db)):
    # Find user by email
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    
    # Verify credentials
    if not user or not security.verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Generate JWTs
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "id": user.id}, expires_delta=access_token_expires
    )
    
    refresh_token = security.create_refresh_token(
        data={"sub": user.email, "id": user.id}
    )
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=user_schema.Token)
def refresh_token(token_request: user_schema.RefreshTokenRequest, db: Session = Depends(connection.get_db)):
    try:
        payload = jwt.decode(token_request.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
            
        user_email = payload.get("sub")
        user_id = payload.get("id")
        
        if user_email is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
            
        # Verify user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            
        # Generate new tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = security.create_access_token(
            data={"sub": user.email, "id": user.id}, expires_delta=access_token_expires
        )
        
        new_refresh_token = security.create_refresh_token(
            data={"sub": user.email, "id": user.id}
        )
        
        return {"access_token": new_access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
