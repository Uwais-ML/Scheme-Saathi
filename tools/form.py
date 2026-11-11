"""Form planning, filling, and preview tools for welfare scheme applications."""

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from config.settings import settings
from state.models import UserProfile, mask_sensitive_id
from tools.registry import register_tool


class FormArgs(BaseModel):
    """Arguments for form tools."""

    scheme_id: str = Field(description="Scheme identifier (e.g. 'pm_kisan')")


def load_form_template(scheme_id: str) -> dict[str, Any] | None:
    """Load JSON form template for scheme."""
    path = settings.TEMPLATES_DIR / f"{scheme_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def resolve_source_value(source_path: str, profile: UserProfile) -> Any | None:
    """Resolve a source path (e.g. 'profile.name' or 'documents.aadhaar.id_number')."""
    parts = source_path.split(".")
    if not parts:
        return None

    root = parts[0]
    if root == "profile" and len(parts) >= 2:
        attr = parts[1]
        val = getattr(profile, attr, None)
        return val if val is not None else profile.form_draft.get(attr)

    elif root == "documents" and len(parts) >= 3:
        doc_id = parts[1]
        field_name = parts[2]
        doc = profile.get_document(doc_id)
        if doc and doc.status == "verified":
            return doc.extracted_fields.get(field_name)

    return None


@register_tool(
    name="form_plan",
    description="Analyze the form requirements, list what info we already have, and what is still needed.",
)
def form_plan(
    scheme_id: str | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Produce form filling plan comparing required fields with available profile data."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    template = load_form_template(sid)
    if not template:
        return {"ok": False, "data": None, "error": f"Form template for '{sid}' not found."}

    if profile is None:
        return {"ok": False, "data": None, "error": "UserProfile context is missing."}

    fields = template.get("fields", [])
    needed_fields = []
    have_fields = []
    missing_fields = []

    for f in fields:
        key = f.get("key")
        label = f.get("label", key)
        src = f.get("source", "")
        required = f.get("required", True)

        val = resolve_source_value(src, profile) or profile.form_draft.get(key)
        needed_fields.append({"key": key, "label": label, "required": required})

        if val is not None and str(val).strip() != "":
            have_fields.append({"key": key, "label": label, "value": val})
        else:
            if required:
                missing_fields.append({"key": key, "label": label})

    # Plain language explanation for low-literacy users
    if not missing_fields:
        summary_msg = f"फॉर्म के लिए सभी आवश्यक {len(have_fields)} जानकारियां हमारे पास मौजूद हैं। क्या हम फॉर्म भरना शुरू करें?"
    else:
        summary_msg = (
            f"फॉर्म में कुल {len(needed_fields)} चीजें चाहिए। {len(have_fields)} चीजें हमारे पास हैं, "
            f"और केवल {len(missing_fields)} जानकारी अभी चाहिए: {missing_fields[0]['label']}।"
        )

    return {
        "ok": True,
        "data": {
            "scheme_id": sid,
            "needed_fields": needed_fields,
            "have_fields": have_fields,
            "missing_fields": missing_fields,
            "can_fill": len(missing_fields) == 0,
            "summary_message": summary_msg,
        },
    }


@register_tool(
    name="fill_form",
    description="Populate the scheme application form draft from profile and verified documents.",
)
def fill_form(
    scheme_id: str | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Fill form draft for the user."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    template = load_form_template(sid)
    if not template:
        return {"ok": False, "data": None, "error": f"Form template for '{sid}' not found."}

    if profile is None:
        return {"ok": False, "data": None, "error": "UserProfile context is missing."}

    profile.active_scheme = sid
    fields = template.get("fields", [])

    for f in fields:
        key = f.get("key")
        src = f.get("source", "")
        val = resolve_source_value(src, profile)
        if val is not None:
            profile.form_draft[key] = val

    return {
        "ok": True,
        "data": {
            "scheme_id": sid,
            "form_draft": profile.form_draft,
            "message": "फॉर्म ड्राफ्ट सफलतापूर्वक तैयार कर लिया गया है।",
        },
    }


@register_tool(
    name="form_preview",
    description="Generate a readable, masked summary of the filled application form for user confirmation.",
)
def form_preview(
    scheme_id: str | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Generate masked preview of filled form and verification prompt."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    template = load_form_template(sid)
    if not template:
        return {"ok": False, "data": None, "error": f"Form template for '{sid}' not found."}

    if profile is None:
        return {"ok": False, "data": None, "error": "UserProfile context is missing."}

    scheme_title = template.get("scheme_name", sid)
    preview_items = []
    spoken_summary_parts = []

    for f in template.get("fields", []):
        key = f.get("key")
        label = f.get("label", key)
        val = profile.form_draft.get(key)
        if val is None:
            val = resolve_source_value(f.get("source", ""), profile)

        display_val = str(val) if val is not None else "उपलब्ध नहीं"

        # Mask sensitive account / Aadhaar numbers
        if any(w in key.lower() for w in ("aadhaar", "bank", "account", "card")):
            display_val = mask_sensitive_id(display_val)

        preview_items.append({"key": key, "label": label, "value": display_val})
        if val:
            spoken_summary_parts.append(f"{label}: {display_val}")

    spoken_message = (
        f"मैंने {scheme_title} का आपका आवेदन तैयार कर लिया है। "
        f"{', '.join(spoken_summary_parts[:3])}। क्या ये सभी विवरण सही हैं?"
    )

    return {
        "ok": True,
        "data": {
            "scheme_id": sid,
            "scheme_name": scheme_title,
            "preview_items": preview_items,
            "spoken_confirmation_prompt": spoken_message,
        },
    }
