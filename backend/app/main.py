"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.redis import close_redis
from app.config.settings import get_settings
from app.controller.conversation_controller import router as conversation_router
from app.controller.member_controller import router as member_router
from app.controller.message_controller import router as message_router
from app.controller.user_controller import router as user_router
from app.exceptions.error_handlers import (
    conflict_handler,
    forbidden_handler,
    not_found_handler,
    validation_error_handler,
)
from app.exceptions.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.websocket.redis_listener import listen_to_redis
from app.websocket.websocket_routes import router as websocket_router

logger = logging.getLogger("chat.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Startup:
    - Spawns the Redis subscriber listener as a background asyncio task.
    
    Shutdown:
    - Cancels the Redis listener task cleanly.
    - Closes Redis connection pools.
    """
    # ── STARTUP ──
    logger.info("Application starting up: launching Redis Pub/Sub listener...")
    listener_task = asyncio.create_task(listen_to_redis())

    yield  # Application runs and handles HTTP/WebSocket requests here

    # ── SHUTDOWN ──
    logger.info("Application shutting down: cancelling Redis listener...")
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        logger.info("Redis listener task cancelled successfully.")
    except Exception as err:
        logger.error("Error during Redis listener task cancellation: %s", err)

    logger.info("Closing Redis connection pool...")
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(ForbiddenError, forbidden_handler)
app.add_exception_handler(ConflictError, conflict_handler)
app.add_exception_handler(ValidationError, validation_error_handler)

# REST API routers
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(member_router, prefix="/api/v1")
app.include_router(message_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")

# WebSocket router
app.include_router(websocket_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}