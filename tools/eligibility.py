"""Eligibility checking tool comparing UserProfile against scheme criteria."""

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from config.settings import settings
from state.models import SchemeEligibility, UserProfile
from tools.registry import register_tool


class EligibilityArgs(BaseModel):
    """Arguments for eligibility checking tool."""

    scheme_id: str = Field(description="The unique identifier of the scheme (e.g. 'pm_kisan')")


def load_scheme_data(scheme_id: str) -> dict[str, Any] | None:
    """Load scheme definition JSON from data directory."""
    path = settings.DATA_DIR / f"{scheme_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@register_tool(
    name="check_eligibility",
    description="Compare the user's profile against a scheme's rules to determine eligibility.",
)
def check_eligibility(
    scheme_id: str | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Check user eligibility for a specific scheme."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    scheme = load_scheme_data(sid)
    if not scheme:
        return {"ok": False, "data": None, "error": f"Scheme '{sid}' not found in database."}

    rules = scheme.get("eligibility_rules", {})
    if profile is None:
        return {"ok": False, "data": None, "error": "UserProfile context is missing."}

    # Record that this scheme is being discussed
    if sid not in profile.schemes_discussed:
        profile.schemes_discussed.append(sid)

    missing_fields = []

    # Check 1: Farmer status
    if "is_farmer" in rules:
        if profile.is_farmer is None:
            missing_fields.append("is_farmer")
        elif rules["is_farmer"] and not profile.is_farmer:
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": "यह योजना केवल किसान परिवारों के लिए है।",
                },
            }

    # Check 2: Gender
    if "gender" in rules:
        if profile.gender is None:
            missing_fields.append("gender")
        elif profile.gender.lower() != rules["gender"].lower():
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": f"यह योजना केवल {rules['gender']} वर्ग के लिए है।",
                },
            }

    # Check 3: State residency
    if "state" in rules:
        if profile.state is None:
            missing_fields.append("state")
        elif rules["state"].lower() not in profile.state.lower():
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": f"यह योजना केवल {rules['state']} के निवासियों के लिए है।",
                },
            }

    # Check 4: Age
    if "min_age" in rules:
        if profile.age is None:
            missing_fields.append("age")
        elif profile.age < rules["min_age"]:
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": f"न्यूनतम आयु {rules['min_age']} वर्ष होनी चाहिए।",
                },
            }

    if "max_age" in rules:
        if profile.age is None and "age" not in missing_fields:
            missing_fields.append("age")
        elif profile.age and profile.age > rules["max_age"]:
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": f"अधिकतम आयु {rules['max_age']} वर्ष से कम होनी चाहिए।",
                },
            }

    # Check 5: Annual Income
    if "max_annual_income" in rules:
        if profile.annual_income is None:
            missing_fields.append("annual_income")
        elif profile.annual_income > rules["max_annual_income"]:
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": f"वार्षिक आय {rules['max_annual_income']} रुपये से अधिक नहीं होनी चाहिए।",
                },
            }

    # Check 6: Land holding
    if "max_land_holding" in rules and rules["max_land_holding"] is not None:
        if profile.land_holding is None:
            missing_fields.append("land_holding")
        elif profile.land_holding > rules["max_land_holding"]:
            return {
                "ok": True,
                "data": {
                    "status": "not_eligible",
                    "reason": f"कृषि भूमि {rules['max_land_holding']} एकड़ से कम होनी चाहिए।",
                },
            }

    # If any info is missing, prompt user for the first missing piece
    if missing_fields:
        return {
            "ok": True,
            "data": {
                "status": "missing_info",
                "missing_fields": missing_fields,
                "next_question_field": missing_fields[0],
                "message": f"पात्रता की पुष्टि के लिए हमें '{missing_fields[0]}' की जानकारी चाहिए।",
            },
        }

    # All criteria met
    success_reason = f"आप {scheme.get('name')} की सभी शर्तों के अनुसार पात्र हैं।"
    # Record eligibility in profile
    if not any(e.scheme_id == sid for e in profile.schemes_eligible):
        profile.schemes_eligible.append(SchemeEligibility(scheme_id=sid, reason=success_reason))

    return {
        "ok": True,
        "data": {
            "status": "eligible",
            "reason": success_reason,
            "scheme_id": sid,
        },
    }
