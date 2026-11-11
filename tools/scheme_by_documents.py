"""Tool to find alternative schemes matching verified documents and eligibility."""

import json
from typing import Any
from pydantic import BaseModel, Field

from config.settings import settings
from state.models import UserProfile
from tools.registry import register_tool
from tools.eligibility import check_eligibility


class SchemesByDocsArgs(BaseModel):
    """Arguments for finding schemes by documents."""

    doc_ids: list[str] = Field(
        default_factory=list,
        description="List of document IDs the user already possesses or has verified",
    )


@register_tool(
    name="find_schemes_by_documents",
    description="Find other welfare schemes the user qualifies for using only the documents they currently have.",
)
def find_schemes_by_documents(
    doc_ids: list[str] | None = None,
    args: dict[str, Any] | None = None,
    profile: UserProfile | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Find schemes requiring only a subset of available documents."""
    available_docs = doc_ids or (args.get("doc_ids") if args else [])

    # If no doc_ids explicitly passed, gather verified docs from profile
    if not available_docs and profile is not None:
        available_docs = [
            doc.doc_id for doc in profile.documents if doc.status == "verified"
        ]

    available_set = set(available_docs)
    data_dir = settings.DATA_DIR
    matching_schemes = []

    for filepath in data_dir.glob("*.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            scheme = json.load(f)

        sid = scheme.get("scheme_id")
        req_docs = scheme.get("required_documents", [])
        req_doc_ids = {d.get("doc_id") for d in req_docs if d.get("doc_id")}
        missing_docs = req_doc_ids - available_set

        # If zero missing or up to 2 missing documents, consider it
        if len(missing_docs) <= 2:
            if profile is not None:
                elig = check_eligibility(scheme_id=sid, profile=profile)
                if elig.get("ok") and elig["data"].get("status") == "not_eligible":
                    continue

            effort_score = len(missing_docs)
            matching_schemes.append(
                {
                    "scheme_id": sid,
                    "name": scheme.get("name"),
                    "required_documents": list(req_doc_ids),
                    "missing_documents": list(missing_docs),
                    "effort_score": effort_score,
                    "summary": scheme.get("content", "")[:150] + "...",
                }
            )

    # Order by effort_score ascending (easiest / fewest missing docs first)
    matching_schemes.sort(key=lambda s: s["effort_score"])

    return {
        "ok": True,
        "data": {
            "available_documents": list(available_set),
            "matching_schemes": matching_schemes,
        },
    }
