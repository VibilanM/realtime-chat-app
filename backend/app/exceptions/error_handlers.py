"""Map application exceptions to HTTP responses."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.exceptions.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.detail})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.detail})


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.detail})
