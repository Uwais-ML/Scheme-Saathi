"""Unit tests for Phase 5 tools: web_search, search_schemes, and check_eligibility."""

from state.models import UserProfile
from tools.web_search import web_search
from tools.scheme_search import search_schemes
from tools.eligibility import check_eligibility
from tools.profile_tools import update_user_profile, set_active_scheme


def test_web_search_fallback_when_keys_invalid(monkeypatch):
    """Verify web_search tool gracefully handles failed keys and returns fallback."""
    from config.settings import settings
    monkeypatch.setattr(settings, "TAVILY_API_KEYS", ["bad_key_1", "bad_key_2"])
    res = web_search(query="PM Kisan updates")
    # With bad keys, rotation should exhaust and return search_unavailable
    assert res["ok"] is False
    assert res["error"] == "search_unavailable"


def test_search_schemes_local_rag_returns_results():
    """Verify search_schemes returns PM-Kisan for farmer query."""
    res = search_schemes(query="किसान सम्मान निधि")
    assert res["ok"] is True
    assert res["data"]["relevant"] is True
    assert len(res["data"]["schemes"]) > 0


def test_check_eligibility_pm_kisan_missing_info():
    """Verify missing is_farmer returns missing_info."""
    profile = UserProfile(user_id="u1", age=30)
    res = check_eligibility(scheme_id="pm_kisan", profile=profile)
    assert res["ok"] is True
    assert res["data"]["status"] == "missing_info"
    assert "is_farmer" in res["data"]["missing_fields"]


def test_check_eligibility_pm_kisan_not_eligible():
    """Verify non-farmer is rejected with reason."""
    profile = UserProfile(user_id="u2", age=30, is_farmer=False)
    res = check_eligibility(scheme_id="pm_kisan", profile=profile)
    assert res["ok"] is True
    assert res["data"]["status"] == "not_eligible"
    assert "किसान" in res["data"]["reason"]


def test_check_eligibility_pm_kisan_eligible():
    """Verify farmer with all criteria is marked eligible."""
    profile = UserProfile(user_id="u3", age=35, is_farmer=True)
    res = check_eligibility(scheme_id="pm_kisan", profile=profile)
    assert res["ok"] is True
    assert res["data"]["status"] == "eligible"
    assert any(e.scheme_id == "pm_kisan" for e in profile.schemes_eligible)


def test_check_eligibility_ladli_behna_state_and_gender():
    """Verify state-specific and gender-specific rules for Ladli Behna."""
    # Male resident of MP
    p_male = UserProfile(user_id="u4", state="Madhya Pradesh", gender="male", age=30)
    res1 = check_eligibility(scheme_id="ladli_behna", profile=p_male)
    assert res1["data"]["status"] == "not_eligible"

    # Female resident of UP (wrong state)
    p_up = UserProfile(user_id="u5", state="Uttar Pradesh", gender="female", age=30)
    res2 = check_eligibility(scheme_id="ladli_behna", profile=p_up)
    assert res2["data"]["status"] == "not_eligible"

    # Female resident of MP with valid age and income
    p_mp = UserProfile(
        user_id="u6",
        state="Madhya Pradesh",
        gender="female",
        age=30,
        annual_income=150000.0,
        land_holding=2.0,
    )
    res3 = check_eligibility(scheme_id="ladli_behna", profile=p_mp)
    assert res3["data"]["status"] == "eligible"


def test_profile_tools_update_and_active_scheme():
    """Verify update_user_profile and set_active_scheme tools."""
    profile = UserProfile(user_id="u7")
    update_res = update_user_profile(
        fields={"name": "Anita", "preferred_language": "hi", "is_farmer": True},
        profile=profile,
    )
    assert update_res["ok"] is True
    assert profile.name == "Anita"
    assert profile.is_farmer is True

    set_res = set_active_scheme(scheme_id="pm_kisan", profile=profile)
    assert set_res["ok"] is True
    assert profile.active_scheme == "pm_kisan"
    assert "pm_kisan" in profile.schemes_discussed
