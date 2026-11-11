"""Unit tests for Phase 17: Household Profiles and Isolation."""

from state.models import Household, Member, UserProfile, DocumentRecord, HouseholdShared
from state.store import load_household, save_household, get_active_member, save_profile
from tools.household_tools import add_member, switch_member, list_members, check_household_eligibility
from scripts.migrate_to_household import migrate_to_household


def test_add_member_creates_separate_profile(tmp_path):
    db_file = tmp_path / "hh_test.db"
    hh_id = "test_hh_001"
    hh = load_household(hh_id, db_path=db_file)
    assert len(hh.members) == 1
    assert hh.members[0].relation == "self"

    # Add mother
    res = add_member(household_id=hh_id, display_name="Sita Devi", relation="mother", db_path=db_file)
    assert res["ok"] is True
    mom_id = res["member_id"]

    hh_loaded = load_household(hh_id, db_path=db_file)
    assert len(hh_loaded.members) == 2
    assert hh_loaded.active_member_id == mom_id
    assert hh_loaded.get_active_member().display_name == "Sita Devi"


def test_switch_member_changes_active(tmp_path):
    db_file = tmp_path / "hh_test.db"
    hh_id = "test_hh_002"
    load_household(hh_id, db_path=db_file)

    res1 = add_member(household_id=hh_id, display_name="Ramesh", relation="spouse", db_path=db_file)
    spouse_id = res1["member_id"]
    res2 = add_member(household_id=hh_id, display_name="Aarav", relation="son", db_path=db_file)
    son_id = res2["member_id"]

    # Active should currently be son
    hh = load_household(hh_id, db_path=db_file)
    assert hh.active_member_id == son_id

    # Switch to spouse
    sw_res = switch_member(household_id=hh_id, member_id=spouse_id, db_path=db_file)
    assert sw_res["ok"] is True
    assert "Ramesh" in sw_res["message"]

    hh_switched = load_household(hh_id, db_path=db_file)
    assert hh_switched.active_member_id == spouse_id
    assert hh_switched.get_active_member().display_name == "Ramesh"


def test_list_members_shows_all(tmp_path):
    db_file = tmp_path / "hh_test.db"
    hh_id = "test_hh_003"
    load_household(hh_id, db_path=db_file)
    add_member(household_id=hh_id, display_name="Pooja", relation="daughter", db_path=db_file)
    add_member(household_id=hh_id, display_name="Mohan", relation="father", db_path=db_file)

    listed = list_members(household_id=hh_id, db_path=db_file)
    assert listed["ok"] is True
    assert len(listed["members"]) == 3
    names = [m["display_name"] for m in listed["members"]]
    assert "Pooja" in names
    assert "Mohan" in names


def test_data_isolation_between_members(tmp_path):
    db_file = tmp_path / "hh_test.db"
    hh_id = "test_hh_004"
    hh = load_household(hh_id, db_path=db_file)
    self_member = hh.members[0]

    # Add a document to self
    self_member.documents.append(
        DocumentRecord(doc_id="aadhaar_card", status="verified", extracted_fields={"name": "Self User"})
    )
    save_household(hh, db_path=db_file)

    # Add brother
    res = add_member(household_id=hh_id, display_name="Suresh", relation="brother", db_path=db_file)
    bro_id = res["member_id"]

    hh_reloaded = load_household(hh_id, db_path=db_file)
    bro_member = hh_reloaded.get_member(bro_id)
    self_reloaded = hh_reloaded.get_member(self_member.member_id)

    # Self has document, brother has none
    assert len(self_reloaded.documents) == 1
    assert len(bro_member.documents) == 0

    # Add document to brother
    bro_member.documents.append(
        DocumentRecord(doc_id="pan_card", status="verified", extracted_fields={"name": "Suresh"})
    )
    save_household(hh_reloaded, db_path=db_file)

    # Reload from SQLite and verify completely separate docs
    final_hh = load_household(hh_id, db_path=db_file)
    final_self = final_hh.get_member(self_member.member_id)
    final_bro = final_hh.get_member(bro_id)

    assert len(final_self.documents) == 1
    assert final_self.documents[0].doc_id == "aadhaar_card"
    assert len(final_bro.documents) == 1
    assert final_bro.documents[0].doc_id == "pan_card"


def test_household_eligibility_per_member(tmp_path):
    db_file = tmp_path / "hh_test.db"
    hh_id = "test_hh_005"
    hh = load_household(hh_id, db_path=db_file)

    # Member 1 (Self) is a farmer with 2 acres land -> eligible for pm_kisan
    self_m = hh.members[0]
    self_m.profile.age = 35
    self_m.profile.is_farmer = True
    self_m.profile.land_holding = 2.0
    self_m.profile.bank_account_exists = True
    save_household(hh, db_path=db_file)

    # Member 2 (Spouse) is not a farmer
    res = add_member(household_id=hh_id, display_name="Kavita", relation="spouse", db_path=db_file)
    spouse_id = res["member_id"]

    hh_reloaded = load_household(hh_id, db_path=db_file)
    spouse_m = hh_reloaded.get_member(spouse_id)
    if spouse_m:
        spouse_m.profile.is_farmer = False
        spouse_m.profile.land_holding = 0.0
    save_household(hh_reloaded, db_path=db_file)

    elig = check_household_eligibility(household_id=hh_id, scheme_id="pm_kisan", db_path=db_file)
    assert elig["ok"] is True
    evals = elig["members_evaluated"]
    assert len(evals) == 2

    self_eval = next(e for e in evals if e["member_id"] == self_m.member_id)
    spouse_eval = next(e for e in evals if e["member_id"] == spouse_id)

    assert self_eval["eligible"] is True
    assert spouse_eval["eligible"] is False


def test_migrate_to_household_idempotent(tmp_path):
    db_file = tmp_path / "mig_test.db"
    # Seed old profiles
    p1 = UserProfile(user_id="user_old_1", name="Ramlal", is_farmer=True)
    p2 = UserProfile(user_id="user_old_2", name="Geeta", gender="female")
    save_profile(p1, db_path=db_file)
    save_profile(p2, db_path=db_file)

    # Run migration first time
    count1 = migrate_to_household(db_path=db_file)
    assert count1 == 2

    # Verify households created
    hh1 = load_household("user_old_1", db_path=db_file)
    assert len(hh1.members) == 1
    assert hh1.members[0].display_name == "Ramlal"

    # Run migration second time (idempotent, safe)
    count2 = migrate_to_household(db_path=db_file)
    assert count2 == 0
