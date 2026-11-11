"""Tools for managing multi-member households, consent, and per-member eligibility."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from state.models import Household, Member, UserProfile, ConsentRecord
from state.store import load_household, save_household, get_active_member
from tools.registry import register_tool
from tools.eligibility import check_eligibility


@register_tool(
    "add_member",
    "Add a new family member (e.g. spouse, mother, child) to the household and set as active.",
)
def add_member(
    household_id: str,
    display_name: str,
    relation: str = "other",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Create a new member and request consent to record their information."""
    household = load_household(household_id, db_path=db_path)
    new_id = f"mem_{uuid.uuid4().hex[:6]}"

    new_profile = UserProfile(
        user_id=new_id,
        name=display_name,
        preferred_language=household.get_active_member().profile.preferred_language if household.members else "hi",
    )

    # Inherit shared location from household if present
    if household.shared.state:
        new_profile.state = household.shared.state
    if household.shared.district:
        new_profile.district = household.shared.district

    new_member = Member(
        member_id=new_id,
        display_name=display_name,
        relation=relation,
        profile=new_profile,
    )
    household.members.append(new_member)
    household.active_member_id = new_id

    # Record consent placeholder
    consent = ConsentRecord(
        member_id=new_id,
        consented_by=household.members[0].member_id if household.members else "self",
        timestamp=datetime.utcnow().isoformat(),
        purpose=f"Assist with welfare scheme applications for {display_name} ({relation})",
    )
    household.consent_log.append(consent)
    save_household(household, db_path=db_path)

    consent_prompt = (
        f"मैंने {display_name} ({relation}) को परिवार में जोड़ लिया है और अब हम उनकी जानकारी देख रहे हैं। "
        f"क्या मुझे उनकी सहायता के लिए आवश्यक जानकारी दर्ज करने की आपकी अनुमति है?"
    )

    return {
        "ok": True,
        "member_id": new_id,
        "display_name": display_name,
        "relation": relation,
        "consent_prompt": consent_prompt,
    }


@register_tool(
    "switch_member",
    "Switch active household member by member_id.",
)
def switch_member(
    household_id: str,
    member_id: str,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Change the currently active member who the agent is assisting."""
    household = load_household(household_id, db_path=db_path)
    target = household.get_member(member_id)
    if not target:
        return {
            "ok": False,
            "error": f"Member with id '{member_id}' not found in household.",
        }

    household.active_member_id = member_id
    save_household(household, db_path=db_path)

    return {
        "ok": True,
        "active_member_id": member_id,
        "display_name": target.display_name,
        "relation": target.relation,
        "message": f"अब हम {target.display_name} ({target.relation}) के विवरण पर काम कर रहे हैं।",
    }


@register_tool(
    "list_members",
    "List all members in the household with their status and active indicator.",
)
def list_members(
    household_id: str,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return all household members, their relations, and document counts."""
    household = load_household(household_id, db_path=db_path)
    results = []
    for m in household.members:
        results.append({
            "member_id": m.member_id,
            "display_name": m.display_name,
            "relation": m.relation,
            "is_active": m.member_id == household.active_member_id,
            "document_count": len(m.documents),
            "verified_docs": sum(1 for d in m.documents if d.status == "verified"),
            "eligible_schemes": len(m.schemes_eligible),
        })

    return {
        "ok": True,
        "household_id": household_id,
        "active_member_id": household.active_member_id,
        "members": results,
    }


@register_tool(
    "check_household_eligibility",
    "Evaluate scheme eligibility across all household members.",
)
def check_household_eligibility(
    household_id: str,
    scheme_id: str,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Run eligibility rules for each member of the household."""
    household = load_household(household_id, db_path=db_path)
    evaluations = []

    for m in household.members:
        raw_res = check_eligibility(scheme_id=scheme_id, profile=m.profile)
        res = raw_res.get("data", raw_res) if isinstance(raw_res, dict) else {}
        is_eligible = res.get("status") == "eligible" or res.get("eligible") is True
        evaluations.append({
            "member_id": m.member_id,
            "display_name": m.display_name,
            "relation": m.relation,
            "eligible": is_eligible,
            "reason": res.get("reason", res.get("message", "")),
            "missing_fields": res.get("missing_fields", []),
        })

    return {
        "ok": True,
        "scheme_id": scheme_id,
        "household_id": household_id,
        "members_evaluated": evaluations,
    }
