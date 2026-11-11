"""Unit tests for Phase 7: Form planning, filling, and preview."""

from state.models import DocumentRecord, UserProfile
from tools.form import form_plan, fill_form, form_preview


def test_form_plan_detects_have_and_missing_fields():
    """Verify form_plan categorizes known and missing fields."""
    profile = UserProfile(
        user_id="u_form_1",
        name="Sunil Sharma",
        state="Uttar Pradesh",
        district="Varanasi",
        # Land area and documents are still missing
    )

    plan = form_plan(scheme_id="pm_kisan", profile=profile)
    assert plan["ok"] is True
    data = plan["data"]

    have_keys = [f["key"] for f in data["have_fields"]]
    missing_keys = [f["key"] for f in data["missing_fields"]]

    assert "full_name" in have_keys
    assert "state" in have_keys
    assert "district" in have_keys
    assert "aadhaar_number" in missing_keys
    assert "land_area" in missing_keys
    assert data["can_fill"] is False


def test_form_plan_fill_preview_end_to_end():
    """Verify complete plan -> fill -> preview flow."""
    profile = UserProfile(
        user_id="u_form_2",
        name="Geeta Patel",
        state="Gujarat",
        district="Anand",
        land_holding=3.5,
        documents=[
            DocumentRecord(
                doc_id="aadhaar",
                status="verified",
                extracted_fields={"id_number": "123456789012"},
            ),
            DocumentRecord(
                doc_id="bank_passbook",
                status="verified",
                extracted_fields={"id_number": "987654321012"},
            ),
        ],
    )

    # 1. Plan
    plan_res = form_plan(scheme_id="pm_kisan", profile=profile)
    assert plan_res["ok"] is True
    assert plan_res["data"]["can_fill"] is True
    assert len(plan_res["data"]["missing_fields"]) == 0

    # 2. Fill
    fill_res = fill_form(scheme_id="pm_kisan", profile=profile)
    assert fill_res["ok"] is True
    draft = profile.form_draft
    assert draft["full_name"] == "Geeta Patel"
    assert draft["aadhaar_number"] == "123456789012"
    assert draft["bank_account"] == "987654321012"
    assert draft["land_area"] == 3.5

    # 3. Preview
    preview_res = form_preview(scheme_id="pm_kisan", profile=profile)
    assert preview_res["ok"] is True
    items = {it["key"]: it["value"] for it in preview_res["data"]["preview_items"]}

    # Sensitive fields masked
    assert items["aadhaar_number"] == "XXXX XXXX 9012"
    assert "XXXX" in items["bank_account"]
    assert items["full_name"] == "Geeta Patel"

    spoken_prompt = preview_res["data"]["spoken_confirmation_prompt"]
    assert "क्या ये सभी विवरण सही हैं?" in spoken_prompt
