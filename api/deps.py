"""Dependency helpers for FastAPI routes."""

import time
from typing import Any
from fastapi import HTTPException
from state.models import UserProfile
from state.store import load_profile, save_profile

# In-memory session tracking and rate limiting
_SESSION_ACCESS: dict[str, list[float]] = {}
RATE_LIMIT_PER_MINUTE = 60


def check_rate_limit(session_id: str) -> None:
    """Enforce a simple per-session rate limit."""
    now = time.time()
    accesses = _SESSION_ACCESS.setdefault(session_id, [])
    # Clean accesses older than 60s
    _SESSION_ACCESS[session_id] = [t for t in accesses if now - t < 60.0]

    if len(_SESSION_ACCESS[session_id]) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Too many requests in a short period. Please slow down.",
        )
    _SESSION_ACCESS[session_id].append(now)


def get_user_profile(user_id: str) -> UserProfile:
    """Retrieve profile from SQLite store."""
    return load_profile(user_id)
