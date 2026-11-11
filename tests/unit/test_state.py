"""Unit tests for UserProfile and SQLite state store."""

import tempfile
from pathlib import Path
from state.models import DocumentRecord, UserProfile, mask_sensitive_id
from state.store import load_profile, save_profile, update_profile_fields


def test_mask_sensitive_id():
    """Verify Aadhaar and ID numbers are masked."""
    assert mask_sensitive_id("123456789012") == "XXXX XXXX 9012"
    assert mask_sensitive_id("1234 5678 9012") == "XXXX XXXX 9012"
    assert mask_sensitive_id("987654321") == "XXXXX4321"


def test_profile_to_safe_dict_masks_sensitive_data():
    """Verify to_safe_dict masks document extracted fields."""
    profile = UserProfile(
        user_id="u_01",
        name="Ramesh Kumar",
        documents=[
            DocumentRecord(
                doc_id="aadhaar",
                status="verified",
                extracted_fields={"aadhaar_number": "123456789012", "name": "Ramesh Kumar"},
            )
        ],
    )
    safe = profile.to_safe_dict()
    doc_fields = safe["documents"][0]["extracted_fields"]
    assert doc_fields["aadhaar_number"] == "XXXX XXXX 9012"
    assert doc_fields["name"] == "Ramesh Kumar"


def test_sqlite_save_load_roundtrip():
    """Verify saving a profile and reloading it returns identical data."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"

        profile = UserProfile(
            user_id="user_123",
            name="Sita Devi",
            preferred_language="hi",
            age=42,
            is_farmer=True,
            annual_income=120000.0,
            active_scheme="pm_kisan",
            form_draft={"beneficiary_name": "Sita Devi"},
        )
        save_profile(profile, db_path=db_path)

        loaded = load_profile("user_123", db_path=db_path)
        assert loaded.user_id == "user_123"
        assert loaded.name == "Sita Devi"
        assert loaded.preferred_language == "hi"
        assert loaded.age == 42
        assert loaded.is_farmer is True
        assert loaded.annual_income == 120000.0
        assert loaded.active_scheme == "pm_kisan"
        assert loaded.form_draft == {"beneficiary_name": "Sita Devi"}


def test_sqlite_update_profile_fields():
    """Verify partial updates update target fields and persist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"

        # Initially create user
        init_profile = UserProfile(user_id="user_456", name="Vikram")
        save_profile(init_profile, db_path=db_path)

        # Update occupation and state
        updated = update_profile_fields(
            "user_456",
            {"occupation": "small_farmer", "state": "Uttar Pradesh"},
            db_path=db_path,
        )
        assert updated.name == "Vikram"
        assert updated.occupation == "small_farmer"
        assert updated.state == "Uttar Pradesh"

        # Reload to confirm persistence
        reloaded = load_profile("user_456", db_path=db_path)
        assert reloaded.occupation == "small_farmer"
        assert reloaded.state == "Uttar Pradesh"
