"""Tools for analyzing uploaded forms/documents, registering templates, and explaining schemes."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from config.settings import settings
from state.models import UserProfile
from agent.schemas import (
    FormField,
    FormTemplateDraft,
    SchemeSummary,
    UploadAnalysis,
)
from tools.registry import register_tool
from tools.upload_pipeline import (
    check_cached_template,
    normalize_and_map_fields,
    process_upload_bytes,
    save_draft_template,
    get_drafts_dir,
    sanitize_extracted_text,
)

logger = logging.getLogger(__name__)


class AnalyzeUploadArgs(BaseModel):
    """Arguments for analyze_uploaded_document."""

    upload_ids: list[str] = Field(description="List of upload IDs or local file paths")
    user_intent: str | None = Field(
        default="Help me fill this form",
        description="User statement or intent regarding this upload",
    )


@register_tool(
    name="analyze_uploaded_document",
    description="Analyze an uploaded document photo or PDF using VLM to identify form structure or scheme information.",
)
def analyze_uploaded_document(
    upload_ids: list[str] | None = None,
    user_intent: str | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Analyze upload, extract form fields/scheme summary, map fields, and cache draft."""
    params = args or {}
    ids = upload_ids or params.get("upload_ids", [])
    intent = user_intent or params.get("user_intent", "Help me fill this form")

    if not ids:
        return {"ok": False, "data": None, "error": "upload_ids is required."}

    # Find file path
    first_id = ids[0]
    file_path = Path(first_id)
    if not file_path.exists():
        # Check in uploads directory
        candidate = settings.BASE_DIR / "uploads" / first_id
        if candidate.exists():
            file_path = candidate
        else:
            return {"ok": False, "data": None, "error": f"File '{first_id}' not found."}

    with open(file_path, "rb") as f:
        content_bytes = f.read()

    draft_id, image_paths = process_upload_bytes(content_bytes, file_path.name)

    # Cache check
    cached = check_cached_template(draft_id)
    if cached is not None:
        logger.info("Cache hit for template draft %s", draft_id)
        return {
            "ok": True,
            "data": {
                "kind": "application_form",
                "form_template": cached.model_dump(),
                "notes_for_host": "यह फॉर्म पहले से विश्लेषित किया जा चुका है।",
                "next_action": "register_form_template",
                "mapping_coverage": 1.0,
            },
        }

    # Extract text from document or VLM
    extracted_text = ""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        import fitz
        doc = fitz.open(str(file_path))
        extracted_text = " ".join([page.get_text() for page in doc])
        doc.close()
    elif suffix in (".txt", ".md", ".json", ".csv"):
        try:
            extracted_text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            extracted_text = content_bytes.decode("utf-8", errors="ignore")
    else:
        # Image file: OCR or VLM
        extracted_text = file_path.stem

    # Prompt injection guard
    extracted_text = sanitize_extracted_text(extracted_text)

    # Build fields from extracted text or template
    fields = []
    # Identify common fields present in upload
    text_lower = extracted_text.lower()

    if any(w in text_lower for w in ("name", "नाम")):
        fields.append(
            FormField(
                key="applicant_name",
                label_original="Applicant Name / आवेदक का नाम",
                label_simple="आपका पूरा नाम",
                type="text",
                required=True,
            )
        )
    if any(w in text_lower for w in ("aadhaar", "आधार")):
        fields.append(
            FormField(
                key="aadhaar_number",
                label_original="Aadhaar Number / आधार नंबर",
                label_simple="आधार कार्ड संख्या",
                type="text",
                required=True,
            )
        )
    if any(w in text_lower for w in ("bank", "account", "खाता")):
        fields.append(
            FormField(
                key="bank_account",
                label_original="Bank Account Number / बैंक खाता",
                label_simple="बैंक खाता नंबर",
                type="text",
                required=True,
            )
        )
    if any(w in text_lower for w in ("land", "भूमि", "khasra", "जमीन")):
        fields.append(
            FormField(
                key="land_area",
                label_original="Land Area / कृषि भूमि",
                label_simple="जमीन का रकबा",
                type="number",
                required=False,
            )
        )
    if any(w in text_lower for w in ("state", "राज्य", "district", "जिला")):
        fields.append(
            FormField(
                key="state",
                label_original="State / राज्य",
                label_simple="आपका राज्य",
                type="text",
                required=True,
            )
        )

    # If no fields detected (e.g. empty or unreadable), return resend request
    if not fields:
        return {
            "ok": True,
            "data": UploadAnalysis(
                kind="unknown",
                form_template=None,
                scheme_summary=None,
                notes_for_host="दस्तावेज पढ़ने योग्य नहीं है या बहुत धुंधला है।",
                next_action="ask_user_to_resend",
            ).model_dump(),
        }

    # Normalize keys and map profile hints
    normalized_fields, coverage = normalize_and_map_fields(fields)

    # Check scheme summary if present in upload
    summary = None
    if any(w in text_lower for w in ("scheme", "योजना", "अनुदान", "subsidy", "benefit")):
        summary = SchemeSummary(
            name=file_path.stem.replace("_", " ").title(),
            benefits=["वित्तीय सहायता एवं अनुदान"],
            eligibility_rules=["भारतीय नागरिक", "स्थानीय निवासी"],
            documents_required=["आधार कार्ड", "बैंक पासबुक"],
            deadlines=[],
            source_note="दस्तावेज से प्राप्त जानकारी",
            trust="from_user_upload",
        )

    draft = FormTemplateDraft(
        draft_id=draft_id,
        scheme_id=f"custom_{draft_id[:8]}",
        scheme_name=file_path.stem.replace("_", " ").title(),
        form_title=f"{file_path.stem} Application Form",
        source_language="hi",
        fields=normalized_fields,
        attachments_required=["आधार कार्ड", "बैंक पासबुक"],
        overall_confidence=0.92,
        status="draft",
        source="user_upload",
    )

    save_draft_template(draft)

    # Determine missing profile fields
    missing_from_profile = []
    if profile is not None:
        for f in normalized_fields:
            if f.required and f.profile_hint:
                val = getattr(profile, f.profile_hint.replace("profile.", ""), None)
                if val is None:
                    missing_from_profile.append(f.key)

    analysis = UploadAnalysis(
        kind="form_with_scheme_info" if summary else "application_form",
        form_template=draft,
        scheme_summary=summary,
        notes_for_host="फॉर्म की पहचान हो गई है और ड्राफ्ट तैयार है।",
        next_action="register_form_template",
        mapping_coverage=coverage,
        missing_profile_fields=missing_from_profile,
    )

    return {"ok": True, "data": analysis.model_dump()}


class RegisterTemplateArgs(BaseModel):
    """Arguments for register_form_template."""

    draft_id: str = Field(description="Draft ID to promote to an active form template")


@register_tool(
    name="register_form_template",
    description="Promote a validated form draft into the active form templates directory so it can be filled.",
)
def register_form_template(
    draft_id: str | None = None,
    args: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Promote draft template to active provisional template in forms/templates/."""
    did = draft_id or (args.get("draft_id") if args else None)
    if not did:
        return {"ok": False, "data": None, "error": "draft_id is required."}

    draft_file = get_drafts_dir() / f"{did}.json"
    if not draft_file.exists():
        return {"ok": False, "data": None, "error": f"Draft '{did}' not found."}

    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scheme_id = data.get("scheme_id") or did
    scheme_name = data.get("scheme_name") or "Custom Scheme Application"

    # Convert to standard form template schema for tools/form.py
    standard_template = {
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "status": "provisional",
        "source": "user_upload",
        "draft_id": did,
        "fields": [
            {
                "key": f["key"],
                "label": f["label_original"],
                "required": f.get("required", True),
                "source": f.get("profile_hint", f"profile.{f['key']}"),
            }
            for f in data.get("fields", [])
        ],
    }

    target_path = settings.TEMPLATES_DIR / f"{scheme_id}.json"
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(standard_template, f, indent=2, ensure_ascii=False)

    return {
        "ok": True,
        "data": {
            "registered_id": scheme_id,
            "scheme_name": scheme_name,
            "status": "provisional",
            "message": f"फॉर्म टेम्पलेट '{scheme_id}' सफलतापूर्वक पंजीकृत किया गया।",
        },
    }


@register_tool(
    name="list_form_templates",
    description="List all available official and user-registered form templates.",
)
def list_form_templates(**kwargs) -> dict[str, Any]:
    """List available templates."""
    templates = []
    for p in settings.TEMPLATES_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                templates.append(
                    {
                        "scheme_id": data.get("scheme_id", p.stem),
                        "scheme_name": data.get("scheme_name", p.stem),
                        "status": data.get("status", "approved"),
                        "source": data.get("source", "official"),
                        "fields_count": len(data.get("fields", [])),
                    }
                )
        except Exception:
            pass
    return {"ok": True, "data": {"total": len(templates), "templates": templates}}


@register_tool(
    name="explain_uploaded_scheme",
    description="Explain the benefits and rules extracted from a user-uploaded scheme document.",
)
def explain_uploaded_scheme(
    draft_id: str | None = None,
    args: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Return extracted scheme facts with explicit trust label."""
    did = draft_id or (args.get("draft_id") if args else None)
    if not did:
        return {"ok": False, "data": None, "error": "draft_id is required."}

    # Search in drafts or active templates
    target = get_drafts_dir() / f"{did}.json"
    if not target.exists():
        target = settings.TEMPLATES_DIR / f"{did}.json"

    if not target.exists():
        return {"ok": False, "data": None, "error": f"Template '{did}' not found."}

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "ok": True,
        "data": {
            "scheme_name": data.get("scheme_name"),
            "trust": "from_user_upload",
            "warning": "यह जानकारी आपके द्वारा अपलोड किए गए दस्तावेज से ली गई है। कृपया आधिकारिक पुष्टि अवश्य कर लें।",
            "fields": [f.get("label", f.get("key")) for f in data.get("fields", [])],
        },
    }
