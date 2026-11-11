"""SQLite-based persistence for UserProfile."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from config.settings import settings
from state.models import UserProfile, Household, Member, HouseholdShared


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return an open SQLite connection with WAL enabled."""
    path = Path(db_path) if db_path else settings.SQLITE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize database tables if they do not exist."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS households (
                household_id TEXT PRIMARY KEY,
                household_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def load_profile(user_id: str, db_path: Path | str | None = None) -> UserProfile:
    """Load UserProfile from SQLite, or create a new empty profile if not found."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT profile_json FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            return UserProfile.model_validate(data)
        # Default new profile
        new_profile = UserProfile(user_id=user_id, preferred_language=settings.DEFAULT_LANGUAGE)
        save_profile(new_profile, db_path)
        return new_profile


def save_profile(profile: UserProfile, db_path: Path | str | None = None) -> None:
    """Save or update UserProfile in SQLite."""
    init_db(db_path)
    data_json = profile.model_dump_json()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_profiles (user_id, profile_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                profile_json = excluded.profile_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (profile.user_id, data_json),
        )
        conn.commit()


def update_profile_fields(
    user_id: str,
    fields: dict[str, Any],
    db_path: Path | str | None = None,
) -> UserProfile:
    """Update specific attributes on a user profile and save."""
    profile = load_profile(user_id, db_path)
    current_data = profile.model_dump()
    for k, v in fields.items():
        if k in current_data and v is not None:
            current_data[k] = v
    updated_profile = UserProfile.model_validate(current_data)
    save_profile(updated_profile, db_path)
    return updated_profile


def load_household(household_id: str, db_path: Path | str | None = None) -> Household:
    """Load Household from SQLite, or create a default household with one self member."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT household_json FROM households WHERE household_id = ?", (household_id,))
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            return Household.model_validate(data)

        # Create new household linked to the existing user profile if available
        self_profile = load_profile(household_id, db_path=db_path)
        self_member = Member(
            member_id=f"{household_id}_self",
            display_name=self_profile.name or "Self",
            relation="self",
            profile=self_profile,
        )
        new_hh = Household(
            household_id=household_id,
            members=[self_member],
            active_member_id=self_member.member_id,
        )
        save_household(new_hh, db_path)
        return new_hh


def save_household(household: Household, db_path: Path | str | None = None) -> None:
    """Save or update Household in SQLite."""
    init_db(db_path)
    data_json = household.model_dump_json()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO households (household_id, household_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(household_id) DO UPDATE SET
                household_json = excluded.household_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (household.household_id, data_json),
        )
        conn.commit()


def get_active_member(household: Household) -> Member:
    """Return the currently selected active member."""
    member = household.get_active_member()
    if not member:
        # Fallback if somehow empty
        dummy_profile = UserProfile(user_id=f"{household.household_id}_self")
        member = Member(
            member_id=f"{household.household_id}_self",
            display_name="Self",
            relation="self",
            profile=dummy_profile,
        )
        household.members.append(member)
        household.active_member_id = member.member_id
    return member

