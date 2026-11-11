"""Tools for updating UserProfile and setting active scheme."""

from typing import Any
from pydantic import BaseModel, Field

from state.models import UserProfile
from tools.registry import register_tool


class UpdateProfileArgs(BaseModel):
    """Arguments for updating user profile."""

    fields: dict[str, Any] = Field(description="Dictionary of profile field names and their values")


@register_tool(
    name="update_user_profile",
    description="Save new demographic or socio-economic facts told by the user (e.g. age, is_farmer, state).",
)
def update_user_profile(
    fields: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Update profile with newly learned facts."""
    update_data = fields or (args.get("fields") if args else {})
    if profile is None:
        return {"ok": False, "data": None, "error": "Profile context missing."}

    current = profile.model_dump()
    applied = {}
    for k, v in update_data.items():
        if hasattr(profile, k) and v is not None:
            setattr(profile, k, v)
            applied[k] = v

    return {
        "ok": True,
        "data": {"updated_fields": applied, "message": "प्रोफ़ाइल सफलतापूर्वक अपडेट की गई।"},
    }


class SetActiveSchemeArgs(BaseModel):
    """Arguments for setting active scheme."""

    scheme_id: str = Field(description="Scheme ID to set as currently active")


@register_tool(
    name="set_active_scheme",
    description="Set the scheme currently being applied for or explored.",
)
def set_active_scheme(
    scheme_id: str | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Set the active scheme on user profile."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    if profile is not None:
        profile.active_scheme = sid
        if sid not in profile.schemes_discussed:
            profile.schemes_discussed.append(sid)

    return {"ok": True, "data": {"active_scheme": sid}}
