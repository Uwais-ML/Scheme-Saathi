"""Tools for document acquisition help, alternative documents, and dependency-ordered plans."""

import json
from pathlib import Path
from typing import Any
from config.settings import settings
from tools.registry import register_tool

DOC_HELP_DIR = Path(settings.BASE_DIR) / "data" / "documents_help"


def _load_doc_help(doc_id: str) -> dict[str, Any] | None:
    # Normalize ID
    norm_id = doc_id.lower().replace(" ", "_").replace("-", "_")
    path = DOC_HELP_DIR / f"{norm_id}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Try looking by prefix or suffix
    for p in DOC_HELP_DIR.glob("*.json"):
        if p.stem in norm_id or norm_id in p.stem:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


@register_tool(
    "get_document_help",
    "Get detailed information on how to obtain a specific document, issuing authority, and requirements.",
)
def get_document_help(doc_id: str, state: str | None = None) -> dict[str, Any]:
    """Return document acquisition details, with state variations and unverified field flags."""
    record = _load_doc_help(doc_id)
    if not record:
        return {
            "ok": False,
            "error": f"No document help record found for '{doc_id}'. Please check local government office or search online.",
            "unverified_fields": ["issued_by", "typical_cost_inr", "typical_days"],
        }

    unverified = []
    # Identify TODO_VERIFY fields
    for k, v in record.items():
        if v == "TODO_VERIFY" or (isinstance(v, str) and "TODO_VERIFY" in v):
            unverified.append(k)

    # Check state variation if available
    state_code = (state or "").upper()
    state_info = record.get("state_variations", {}).get(state_code, {})

    return {
        "ok": True,
        "doc_id": record["doc_id"],
        "name": record["name"],
        "what_it_is": record["what_it_is"],
        "issued_by": record["issued_by"] if record["issued_by"] != "TODO_VERIFY" else "संबंधित सरकारी कार्यालय",
        "how_to_get": record["how_to_get"],
        "documents_needed": record.get("documents_needed_to_get_it", []),
        "typical_cost": record.get("typical_cost_inr") if record.get("typical_cost_inr") != "TODO_VERIFY" else "न्यूनतम सरकारी शुल्क (कार्यालय पर पुष्टि करें)",
        "typical_days": record.get("typical_days") if record.get("typical_days") != "TODO_VERIFY" else "सरकारी समयानुसार",
        "accepted_alternatives": record.get("accepted_alternatives", []),
        "common_problems": record.get("common_problems", []),
        "state_variation": state_info,
        "unverified_fields": unverified,
    }


@register_tool(
    "find_accepted_alternatives",
    "Find substitute or alternative documents that are accepted in place of a missing document.",
)
def find_accepted_alternatives(doc_id: str, scheme_id: str | None = None) -> dict[str, Any]:
    """Find valid alternative documents accepted for a missing document."""
    record = _load_doc_help(doc_id)
    alternatives = record.get("accepted_alternatives", []) if record else []

    return {
        "ok": True,
        "doc_id": doc_id,
        "scheme_id": scheme_id,
        "has_alternatives": len(alternatives) > 0,
        "alternatives": alternatives,
        "advice": (
            f"यदि आपके पास '{doc_id}' नहीं है, तो आप इनके स्थान पर इनमें से कोई दस्तावेज उपयोग कर सकते हैं: {', '.join(alternatives)}।"
            if alternatives
            else f"'{doc_id}' के लिए कोई सीधा वैकल्पिक दस्तावेज उपलब्ध नहीं है, इसे प्राप्त करने की प्रक्रिया शुरू करनी होगी।"
        ),
    }


@register_tool(
    "get_acquisition_plan",
    "Order missing documents by dependency so precursor documents are acquired first.",
)
def get_acquisition_plan(missing_doc_ids: list[str]) -> dict[str, Any]:
    """Compute dependency-ordered acquisition steps for missing documents.

    If doc B requires doc A, doc A is scheduled before doc B.
    """
    # Normalize IDs
    missing = [d.lower().replace(" ", "_").replace("-", "_") for d in missing_doc_ids]

    # Build dependency graph
    deps: dict[str, list[str]] = {}
    doc_records: dict[str, dict] = {}
    for d in missing:
        rec = _load_doc_help(d)
        doc_records[d] = rec or {}
        needed = rec.get("documents_needed_to_get_it", []) if rec else []
        # Keep dependencies that are also in the missing list
        deps[d] = [dep for dep in needed if dep in missing]

    # Topological sort (Kahn's algorithm)
    in_degree = {d: 0 for d in missing}
    for d, d_deps in deps.items():
        in_degree[d] = len(d_deps)

    queue = [d for d in missing if in_degree[d] == 0]
    ordered: list[str] = []

    # Simple topological sort
    visited = set()
    while queue:
        curr = queue.pop(0)
        ordered.append(curr)
        visited.add(curr)
        for other, other_deps in deps.items():
            if other not in visited and curr in other_deps:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    # Any remaining (circular or unreached) append at end
    for d in missing:
        if d not in visited:
            ordered.append(d)

    steps = []
    for step_num, d in enumerate(ordered, 1):
        rec = doc_records.get(d, {})
        name = rec.get("name", {}).get("hi", d) if rec else d
        how = rec.get("how_to_get", [{}])
        where = how[0].get("where", "स्थानीय सेवा केंद्र / तहसील") if how else "स्थानीय कार्यालय"
        steps.append({
            "step": step_num,
            "doc_id": d,
            "name": name,
            "where": where,
            "prerequisites": deps.get(d, []),
        })

    return {
        "ok": True,
        "total_documents": len(missing),
        "ordered_plan": ordered,
        "steps": steps,
        "summary": f"आपको कुल {len(missing)} दस्तावेज बनवाने होंगे। सबसे पहले '{ordered[0]}' से शुरुआत करें।",
    }
