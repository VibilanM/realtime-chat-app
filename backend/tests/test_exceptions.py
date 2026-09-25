"""Test suite for custom exceptions and FastAPI error handlers."""

import pytest
from unittest.mock import MagicMock
from fastapi import Request

from app.exceptions.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.exceptions.error_handlers import (
    conflict_handler,
    forbidden_handler,
    not_found_handler,
    validation_error_handler,
)


def test_app_error():
    """Test base AppError exception string and detail attribute."""
    err = AppError("Custom error message")
    assert err.detail == "Custom error message"
    assert str(err) == "Custom error message"

    default_err = AppError()
    assert default_err.detail == "An error occurred"


def test_not_found_error():
    """Test NotFoundError formatting with and without identifier."""
    err_without_id = NotFoundError("Conversation")
    assert err_without_id.detail == "Conversation not found"

    err_with_id = NotFoundError("Message", "msg-123")
    assert err_with_id.detail == "Message 'msg-123' not found"


def test_forbidden_error():
    """Test ForbiddenError default and custom message."""
    default_err = ForbiddenError()
    assert default_err.detail == "You do not have permission to perform this action"

    custom_err = ForbiddenError("Admins only")
    assert custom_err.detail == "Admins only"


def test_conflict_error():
    """Test ConflictError default and custom message."""
    default_err = ConflictError()
    assert default_err.detail == "Conflict with existing resource"

    custom_err = ConflictError("User already in room")
    assert custom_err.detail == "User already in room"


def test_validation_error():
    """Test ValidationError default and custom message."""
    default_err = ValidationError()
    assert default_err.detail == "Validation error"

    custom_err = ValidationError("Message content cannot be blank")
    assert custom_err.detail == "Message content cannot be blank"


@pytest.mark.asyncio
async def test_error_handlers():
    """Test mapping application exceptions to FastAPI JSONResponses."""
    req = MagicMock(spec=Request)

    nf_resp = await not_found_handler(req, NotFoundError("User", "u-1"))
    assert nf_resp.status_code == 404
    assert nf_resp.body == b'{"detail":"User \'u-1\' not found"}'

    fb_resp = await forbidden_handler(req, ForbiddenError("Forbidden"))
    assert fb_resp.status_code == 403
    assert fb_resp.body == b'{"detail":"Forbidden"}'

    cf_resp = await conflict_handler(req, ConflictError("Conflict"))
    assert cf_resp.status_code == 409
    assert cf_resp.body == b'{"detail":"Conflict"}'

    val_resp = await validation_error_handler(req, ValidationError("Invalid"))
    assert val_resp.status_code == 422
    assert val_resp.body == b'{"detail":"Invalid"}'
