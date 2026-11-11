"""Deterministic welfare scheme benefit ranking tool."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from config.settings import settings
from state.store import load_household, load_profile
from tools.registry import register_tool
from tools.eligibility import check_eligibility


def _load_all_schemes() -> list[dict[str, Any]]:
    schemes = []
    data_dir = settings.DATA_DIR
    for p in data_dir.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                schemes.append(json.load(f))
        except Exception:
            pass
    return schemes


@register_tool(
    "rank_schemes",
    "Rank eligible schemes for a household member based on annual benefit, eligibility confidence, and required effort.",
)
def rank_schemes(
    member_id: str | None = None,
    preference: str = "balanced",
    household_id: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Rank welfare schemes deterministically using benefit, confidence, and effort scores.

    Formula: score = (benefit_score^w_b) * (confidence^w_c) / (effort_score^w_e)
    """
    # 1. Resolve target member profile
    target_profile = None
    if household_id:
        hh = load_household(household_id, db_path=db_path)
        if member_id:
            m = hh.get_member(member_id)
            if m:
                target_profile = m.profile
        if not target_profile:
            target_profile = hh.get_active_member().profile
    elif member_id:
        # Check if member_id is a profile
        target_profile = load_profile(member_id, db_path=db_path)

    if not target_profile:
        return {"ok": False, "error": "No profile found to evaluate ranking."}

    # 2. Get weights from settings
    weights = settings.RANKING_PREFERENCE_WEIGHTS.get(
        preference,
        settings.RANKING_PREFERENCE_WEIGHTS["balanced"],
    )

    all_schemes = _load_all_schemes()
    available_doc_ids = {d.doc_id for d in target_profile.documents if d.status == "verified"}

    ranked_items = []
    unranked_items = []
    now_iso = datetime.utcnow().date().isoformat()

    for scheme in all_schemes:
        sid = scheme.get("scheme_id")
        status_info = scheme.get("status", {})

        # Exclude closed schemes
        if status_info.get("open") is False:
            continue
        deadline = status_info.get("deadline")
        if deadline and deadline < now_iso:
            continue

        # Check eligibility
        raw_elig = check_eligibility(scheme_id=sid, profile=target_profile)
        elig_data = raw_elig.get("data", raw_elig) if isinstance(raw_elig, dict) else {}
        elig_status = elig_data.get("status", "unknown")

        if elig_status == "not_eligible":
            continue

        # Confidence: 1.0 if fully eligible, 0.6 if missing info
        confidence = 1.0 if elig_status == "eligible" else 0.6

        # Benefit value
        benefit = scheme.get("benefit", {})
        est_val = benefit.get("estimated_value_inr_per_year")

        if est_val is None or est_val <= 0:
            unranked_items.append({
                "scheme_id": sid,
                "name": scheme.get("name"),
                "note": "No estimated benefit value recorded.",
                "eligibility_status": elig_status,
            })
            continue

        # Normalized benefit score (cap at 50,000 INR baseline)
        benefit_norm = min(float(est_val) / 25000.0, 3.0)

        # Effort score: missing docs + form length
        req_docs = scheme.get("required_documents", [])
        req_doc_ids = {d.get("doc_id") for d in req_docs if d.get("doc_id")}
        missing_count = len(req_doc_ids - available_doc_ids)
        effort_score = 1.0 + (missing_count * 0.75)

        # Weighted calculation
        score = (
            (benefit_norm ** weights["benefit"])
            * (confidence ** weights["confidence"])
            / (effort_score ** weights["effort"])
        )

        ranked_items.append({
            "scheme_id": sid,
            "name": scheme.get("name"),
            "final_score": round(score, 3),
            "estimated_value_inr": est_val,
            "confidence": confidence,
            "effort_score": round(effort_score, 2),
            "missing_docs_count": missing_count,
            "eligibility_status": elig_status,
            "benefit_type": benefit.get("type", "scheme"),
        })

    # Sort descending by final_score
    ranked_items.sort(key=lambda x: x["final_score"], reverse=True)

    top_pick = ranked_items[0] if ranked_items else None
    explanation = ""
    if top_pick:
        missing_phrase = (
            "आपको सभी आवश्यक दस्तावेज पहले से प्राप्त हैं"
            if top_pick["missing_docs_count"] == 0
            else f"आपको केवल {top_pick['missing_docs_count']} दस्तावेज बनवाने होंगे"
        )
        explanation = (
            f"आपके लिए सबसे उत्तम विकल्प '{top_pick['name']}' है। "
            f"इसमें प्रति वर्ष लगभग ₹{top_pick['estimated_value_inr']:,} का लाभ मिलता है और {missing_phrase}।"
        )

    return {
        "ok": True,
        "preference": preference,
        "top_pick": top_pick,
        "ranked_schemes": ranked_items,
        "unranked_schemes": unranked_items,
        "explanation": explanation,
    }
