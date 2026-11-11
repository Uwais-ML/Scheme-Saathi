"""Unit tests for Phase 20: Welfare Scheme Benefit Ranking."""

from state.models import UserProfile, DocumentRecord
from state.store import save_profile
from tools.ranking_tools import rank_schemes


def test_rank_schemes_deterministic(tmp_path):
    db_file = tmp_path / "rank_test.db"
    prof = UserProfile(
        user_id="rank_user_1",
        age=32,
        is_farmer=True,
        land_holding=2.5,
        bank_account_exists=True,
        bpl_card=True,
    )
    save_profile(prof, db_path=db_file)

    run1 = rank_schemes(member_id="rank_user_1", preference="balanced", db_path=db_file)
    run2 = rank_schemes(member_id="rank_user_1", preference="balanced", db_path=db_file)

    assert run1["ok"] is True
    assert run2["ok"] is True
    scores1 = [s["final_score"] for s in run1["ranked_schemes"]]
    scores2 = [s["final_score"] for s in run2["ranked_schemes"]]
    assert scores1 == scores2


def test_rank_schemes_preference_changes_order(tmp_path):
    db_file = tmp_path / "rank_test.db"
    # Farmer eligible for both PM-KISAN (6k) and PMJAY (25k value, but needs BPL ration card)
    prof = UserProfile(
        user_id="rank_user_2",
        age=40,
        is_farmer=True,
        land_holding=2.0,
        bank_account_exists=True,
        annual_income=120000,
        bpl_card=True,
        documents=[
            DocumentRecord(doc_id="aadhaar", status="verified"),
            DocumentRecord(doc_id="land_records", status="verified"),
            DocumentRecord(doc_id="bank_passbook", status="verified"),
        ],
    )
    save_profile(prof, db_path=db_file)

    high_val = rank_schemes(member_id="rank_user_2", preference="highest_value", db_path=db_file)
    easiest = rank_schemes(member_id="rank_user_2", preference="easiest", db_path=db_file)

    assert high_val["ok"] is True
    assert easiest["ok"] is True

    # Under easiest, PM-KISAN (0 missing docs) should rank higher
    easiest_top = easiest["ranked_schemes"][0]
    assert easiest_top["missing_docs_count"] == 0

    # Under highest_value, the top schemes must have high benefit values
    high_top = high_val["ranked_schemes"][0]
    assert high_top["estimated_value_inr"] >= 15000


def test_rank_schemes_explanation_has_score_components(tmp_path):
    db_file = tmp_path / "rank_test.db"
    prof = UserProfile(
        user_id="rank_user_3",
        age=35,
        is_farmer=True,
        land_holding=1.5,
        bank_account_exists=True,
    )
    save_profile(prof, db_path=db_file)

    res = rank_schemes(member_id="rank_user_3", preference="balanced", db_path=db_file)
    assert res["ok"] is True
    assert res["top_pick"] is not None
    assert "₹" in res["explanation"]
    assert str(res["top_pick"]["estimated_value_inr"]) in res["explanation"].replace(",", "")
