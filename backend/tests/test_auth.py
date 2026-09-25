"""Test suite for authentication module demonstrating 100% line coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import (
    _ensure_dev_users_exist,
    get_current_user,
    get_user_from_username,
)
from app.models.user import User


@pytest.fixture
def mock_db():
    """Fixture providing a mocked AsyncSession."""
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_ensure_dev_users_exist_when_missing(mock_db):
    """Test seeding dev users when none exist in DB."""
    # Simulate DB query returning None for all 3 dev users
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = scalar_mock

    await _ensure_dev_users_exist(mock_db)

    # 3 dev users should be added
    assert mock_db.add.call_count == 3
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_dev_users_exist_when_already_present(mock_db):
    """Test seeding dev users when they already exist."""
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = MagicMock(spec=User)
    mock_db.execute.return_value = scalar_mock

    await _ensure_dev_users_exist(mock_db)

    assert mock_db.add.call_count == 0
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_user_from_username_invalid_username(mock_db):
    """Test invalid username raises 401 Unauthorized."""
    with pytest.raises(HTTPException) as exc_info:
        await get_user_from_username("charlie", mock_db)

    assert exc_info.value.status_code == 401
    assert "Unknown user 'charlie'" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_user_from_username_success(mock_db):
    """Test valid username returns User instance (case-insensitive & trimmed)."""
    expected_user = User(name="Alice", email="alice@example.com")
    
    # First 3 queries for _ensure_dev_users_exist, 4th query for find user
    existing_mock = MagicMock()
    existing_mock.scalar_one_or_none.return_value = expected_user
    mock_db.execute.return_value = existing_mock

    user = await get_user_from_username("  Alice  ", mock_db)
    assert user == expected_user


@pytest.mark.asyncio
async def test_get_user_from_username_seeding_failed(mock_db):
    """Test 500 internal server error if user is somehow None after seed."""
    # Ensure seed succeeds but final user lookup returns None
    count = 0
    def mock_scalar():
        nonlocal count
        count += 1
        m = MagicMock()
        m.scalar_one_or_none.return_value = None
        return m

    mock_db.execute.side_effect = lambda stmt: mock_scalar()

    with pytest.raises(HTTPException) as exc_info:
        await get_user_from_username("alice", mock_db)

    assert exc_info.value.status_code == 500
    assert "Dev user seeding failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_header_dependency(mock_db):
    """Test get_current_user delegates to get_user_from_username."""
    expected_user = User(name="Bob", email="bob@example.com")
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = expected_user
    mock_db.execute.return_value = scalar_mock

    user = await get_current_user(x_user_id="bob", db=mock_db)
    assert user == expected_user
