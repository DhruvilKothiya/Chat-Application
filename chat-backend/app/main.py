from fastapi import FastAPI
from app.routers import auth, chat
from app.database.connection import engine, Base
from app.database import models  # Ensure models are imported so Base metadata knows about them

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chat API", version="1.0.0")

app.include_router(auth.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {"message": "Welcome to Chat API"}