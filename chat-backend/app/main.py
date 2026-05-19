import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import auth, chat
from app.database.connection import engine, Base
from app.database import models
from app.websocket.manager import manager

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create a background task for Redis Pub/Sub
    pubsub_task = asyncio.create_task(manager.pubsub_reader())
    yield
    # Shutdown: Cancel the task
    pubsub_task.cancel()

app = FastAPI(title="Chat API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {"message": "Welcome to Chat API"}