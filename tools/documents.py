"""Document checklist and VLM verification tools."""

from typing import Any
from pydantic import BaseModel, Field

from state.models import DocumentRecord, UserProfile
from tools.registry import register_tool
from tools.eligibility import load_scheme_data
from vlm.verifier import get_vlm_verifier


class ChecklistArgs(BaseModel):
    """Arguments for building document checklist."""

    scheme_id: str = Field(description="Scheme ID to retrieve document requirements for")


@register_tool(
    name="build_document_checklist",
    description="Get the list of required documents for a scheme, explained in simple language.",
)
def build_document_checklist(
    scheme_id: str | None = None,
    args: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Retrieve required documents for a scheme."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    scheme = load_scheme_data(sid)
    if not scheme:
        return {"ok": False, "data": None, "error": f"Scheme '{sid}' not found."}

    docs = scheme.get("required_documents", [])
    checklist = [
        {
            "doc_id": d.get("doc_id"),
            "name": d.get("name"),
            "description": d.get("description", d.get("name")),
            "validity_rules": d.get("validity_rules", []),
        }
        for d in docs
    ]

    return {
        "ok": True,
        "data": {
            "scheme_id": sid,
            "total_documents": len(checklist),
            "documents": checklist,
        },
    }


class VerifyDocsArgs(BaseModel):
    """Arguments for verifying documents via VLM."""

    scheme_id: str = Field(description="Scheme ID for which documents are submitted")
    image_refs: list[str] = Field(description="List of image file paths or references")


@register_tool(
    name="verify_documents",
    description="Verify uploaded document photos using the Vision Language Model (VLM).",
)
def verify_documents(
    scheme_id: str | None = None,
    image_refs: list[str] | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Verify documents via VLM and update user state."""
    sid = scheme_id or (args.get("scheme_id") if args else None)
    imgs = image_refs or (args.get("image_refs") if args else [])

    if not sid:
        return {"ok": False, "data": None, "error": "scheme_id is required."}

    scheme = load_scheme_data(sid)
    if not scheme:
        return {"ok": False, "data": None, "error": f"Scheme '{sid}' not found."}

    expected_docs = scheme.get("required_documents", [])
    verifier = get_vlm_verifier()
    result = verifier.verify(
        scheme_id=sid,
        expected_documents=expected_docs,
        image_refs=imgs,
    )

    # Update profile state
    if profile is not None:
        status_map = {
            "verified": "verified",
            "rejected": "rejected",
            "unreadable": "rejected",
            "not_provided": "missing",
            "submitted": "submitted",
            "missing": "missing",
        }
        for check in result.checks:
            rec_status = status_map.get(check.status, "missing")
            doc_rec = DocumentRecord(
                doc_id=check.doc_id,
                status=rec_status,
                reason=check.reason,
                extracted_fields=check.extracted_fields,
            )
            profile.upsert_document(doc_rec)

            # High confidence extraction auto-fill into profile
            if check.status == "verified" and check.confidence >= 0.8:
                if "name" in check.extracted_fields and not profile.name:
                    profile.name = check.extracted_fields["name"]

    return {
        "ok": True,
        "data": result.model_dump(),
    }
