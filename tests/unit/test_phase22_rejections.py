"""Unit tests for Phase 22: Rejection and Grievance Help."""

import pytest
from tools.rejection_tools import analyze_rejection_text, explain_rejection, draft_grievance
from state.models import UserProfile
from state.store import save_profile

TEST_LETTERS = [
    (
        "Application rejected due to Name Spelling Mismatch between Aadhaar and Bank account. Ref: PMK-2024-99881",
        "name_mismatch",
    ),
    (
        "DBT payment failed: Bank account is not seeded with Aadhaar / NPCI mapping inactive.",
        "aadhaar_bank_link",
    ),
    (
        "Incomplete documents uploaded: Khatauni copy was blurred and missing survey stamp.",
        "incomplete_documents",
    ),
    (
        "Application disqualified: Annual household income exceeds the eligible ceiling limit of 2.5 Lakh.",
        "ineligible_income",
    ),
    (
        "Rejection: Duplicate application found for this Aadhaar card in our central records.",
        "duplicate",
    ),
    (
        "Application period closed: Deadline for submission in current cycle has expired.",
        "deadline_missed",
    ),
    (
        "Rejected: Wrong account number or IFSC code provided in the bank details section.",
        "wrong_details",
    ),
]


@pytest.mark.parametrize("letter_text,expected_category", TEST_LETTERS)
def test_analyze_rejection_text_categories(letter_text, expected_category):
    analysis = analyze_rejection_text(letter_text)
    assert analysis.reason_category == expected_category


def test_explain_rejection_plan():
    res = explain_rejection(category="name_mismatch")
    assert res["ok"] is True
    assert "वर्तनी" in res["title"] or "नाम" in res["title"]
    assert len(res["how_to_fix"]) > 0
    assert "reapply" in res["recommended_route"]


def test_explain_rejection_unknown_triggers_handoff():
    res = explain_rejection(rejection_text="Some random unstructured text without clear reason")
    assert res["ok"] is True
    assert res["category"] == "unknown"
    assert res.get("needs_human_handoff") is True


def test_draft_grievance_contains_user_facts(tmp_path):
    db_file = tmp_path / "grievance_test.db"
    prof = UserProfile(
        user_id="grievance_user_1",
        name="Sunita Sharma",
        district="Ujjain",
        state="Madhya Pradesh",
        active_scheme="pm_ujjwala",
    )
    save_profile(prof, db_path=db_file)

    res = draft_grievance(
        member_id="grievance_user_1",
        category="aadhaar_bank_link",
        reference_number="UJJ-88371-LPG",
        issue_details="मैंने 10 नवंबर को बैंक में जाकर आधार सीडिंग करवा ली है।",
        db_path=db_file,
    )
    assert res["ok"] is True
    letter = res["grievance_letter"]

    # Verify only user facts are present
    assert "Sunita Sharma" in letter
    assert "Ujjain" in letter
    assert "pm_ujjwala" in letter
    assert "UJJ-88371-LPG" in letter
    assert "10 नवंबर को बैंक में जाकर आधार सीडिंग करवा ली है" in letter
