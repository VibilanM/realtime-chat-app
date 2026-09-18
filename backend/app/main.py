"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.redis.connection import close_redis, init_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle events."""
    # Startup
    await init_redis()
    yield
    # Shutdown
    await close_redis()


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

# Routers
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(member_router, prefix="/api/v1")
app.include_router(message_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
