"""Tools for rejection letter analysis, explanation, and grievance drafting."""

import json
import re
from pathlib import Path
from typing import Any
from config.settings import settings
from agent.schemas import RejectionAnalysis, RejectionCategory
from state.models import mask_sensitive_id
from state.store import load_household, load_profile
from tools.registry import register_tool

REJECTIONS_DIR = Path(settings.BASE_DIR) / "data" / "rejection_reasons"


def analyze_rejection_text(text: str) -> RejectionAnalysis:
    """Analyze rejection text/letter deterministically to categorize reason."""
    t_lower = text.lower()
    cat: RejectionCategory = "unknown"
    confidence = 0.9

    if re.search(r"name\s*mismatch|naam\s*alagh|naam\s*me\s*antar|spelling|नाम\s*का\s*मिलान\s*नहीं|नाम\s*भिन्न", t_lower):
        cat = "name_mismatch"
    elif re.search(r"npci|dbt|aadhaar\s*(not\s*linked|seeding|link)|bank\s*not\s*seeded|आधार\s*(लिंक\s*नहीं|सीडिंग|सीडेड\s*नहीं)", t_lower):
        cat = "aadhaar_bank_link"
    elif re.search(r"income\s*(exceed|limit|high|above)|aay\s*adhik|वार्षिक\s*आय\s*अधिक|आय\s*सीमा", t_lower):
        cat = "ineligible_income"
    elif re.search(r"incomplete\s*doc|missing\s*doc|unreadable|blur|photo\s*not\s*clear|अस्पष्ट|दस्तावेज\s*अपूर्ण", t_lower):
        cat = "incomplete_documents"
    elif re.search(r"duplicate|already\s*applied|pehle\s*se\s*labh|दोहरा\s*आवेदन|पहले\s*से\s*पंजीकृत", t_lower):
        cat = "duplicate"
    elif re.search(r"deadline|date\s*over|samay\s*samapt|cycle\s*closed|समय\s*सीमा\s*समाप्त", t_lower):
        cat = "deadline_missed"
    elif re.search(r"wrong\s*(account|ifsc|khasra)|incorrect\s*details|गलत\s*(खाता|आईएफएससी|खसरा)", t_lower):
        cat = "wrong_details"
    else:
        cat = "unknown"
        confidence = 0.5

    # Extract reference number if present
    ref_match = re.search(r"(?:application|ref|registration|क्रमांक|आवेदन\s*संख्या)\s*(?:no\.?|id|:)?\s*([A-Za-z0-9\-_/]{6,25})", text, re.IGNORECASE)
    ref_num = ref_match.group(1) if ref_match else None

    return RejectionAnalysis(
        reason_text_original=text[:300],
        reason_category=cat,
        reference_number=ref_num,
        confidence=confidence,
    )


def _load_rejection_data(category: str) -> dict[str, Any] | None:
    path = REJECTIONS_DIR / f"{category}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


@register_tool(
    "explain_rejection",
    "Explain the cause of a rejected welfare application in simple words with step-by-step resolution advice.",
)
def explain_rejection(
    rejection_text: str | None = None,
    category: str | None = None,
    scheme_id: str | None = None,
) -> dict[str, Any]:
    """Provide plain-language explanation and recommended fix plan for rejection."""
    # Determine category
    analysis = None
    if rejection_text:
        analysis = analyze_rejection_text(rejection_text)
        cat = analysis.reason_category
    else:
        cat = category or "unknown"

    rec = _load_rejection_data(cat)
    if not rec or cat == "unknown":
        return {
            "ok": True,
            "category": "unknown",
            "explanation": (
                "अस्वीकृति पत्र का कारण स्पष्ट नहीं हो सका है। "
                "कृपया पत्र को अपने नजदीकी सीएससी (CSC) या ब्लॉक कार्यालय में दिखाएं।"
            ),
            "how_to_fix": ["नजदीकी कार्यालय जाकर कारण स्पष्ट करवाएं"],
            "recommended_route": "office_visit",
            "needs_human_handoff": True,
        }

    return {
        "ok": True,
        "category": cat,
        "title": rec.get("title", {}).get("hi", cat),
        "explanation": rec.get("explanation", ""),
        "how_to_fix": rec.get("how_to_fix", []),
        "recommended_route": rec.get("recommended_route", "reapply"),
        "portal": rec.get("official_grievance_portal", "https://pgportal.gov.in"),
        "reference_number": analysis.reference_number if analysis else None,
        "advice": (
            f"अस्वीकृति का मुख्य कारण '{rec.get('title', {}).get('hi', cat)}' है। "
            f"घबराएं नहीं, इसे ठीक किया जा सकता है। {rec.get('how_to_fix', [''])[0]}"
        ),
    }


@register_tool(
    "draft_grievance",
    "Draft a formal, polite grievance or appeal letter for a rejected welfare scheme application.",
)
def draft_grievance(
    member_id: str | None = None,
    category: str = "unknown",
    reference_number: str | None = None,
    issue_details: str = "",
    household_id: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Build printable complaint / appeal letter without fabricated facts."""
    profile = None
    if household_id:
        hh = load_household(household_id, db_path=db_path)
        if member_id:
            m = hh.get_member(member_id)
            if m:
                profile = m.profile
        if not profile:
            profile = hh.get_active_member().profile
    elif member_id:
        profile = load_profile(member_id, db_path=db_path)

    user_name = profile.name if profile and profile.name else "आवेदक"
    district = profile.district if profile and profile.district else "अनिर्दिष्ट जिला"
    state = profile.state if profile and profile.state else "भारत"
    scheme = profile.active_scheme if profile and profile.active_scheme else "कल्याणकारी योजना"
    ref_str = reference_number or "पूर्व आवेदन क्रमांक"

    rec = _load_rejection_data(category) or {}
    cat_title = rec.get("title", {}).get("hi", "आवेदन में त्रुटि")

    letter_body = (
        f"सेवा में,\n"
        f"श्रीमान जन शिकायत निवारण अधिकारी / संबंधित योजना प्रभारी,\n"
        f"जिला: {district}, {state}\n\n"
        f"विषय: {scheme} आवेदन (क्रमांक: {ref_str}) के अस्वीकृति संबंध में अपील / शिकायत।\n\n"
        f"महोदय,\n"
        f"सविनय निवेदन है कि प्रार्थी {user_name}, निवासी {district}, {state} ने {scheme} के लिए आवेदन किया था। "
        f"उक्त आवेदन को '{cat_title}' के आधार पर अस्वीकृत किया गया है।\n\n"
        f"प्रार्थी का पक्ष / आवश्यक सुधार:\n"
        f"{issue_details or 'प्रार्थी ने आवश्यक सभी सहायक दस्तावेज नियमानुसार सही करवा लिए हैं। अतः कृपया रिकॉर्ड का पुनर्सत्यापन करने की कृपा करें।'}\n\n"
        f"अतः श्रीमान से विनम्र निवेदन है कि प्रार्थी के आवेदन का पुनः परीक्षण कर योजना का लाभ प्रदान करने की कृपा करें।\n\n"
        f"भवदीय,\n"
        f"नाम: {user_name}\n"
        f"आवेदन संदर्भ: {ref_str}\n"
        f"स्थान: {district}\n"
    )

    return {
        "ok": True,
        "member_name": user_name,
        "scheme": scheme,
        "category": category,
        "reference_number": ref_str,
        "grievance_letter": letter_body,
        "official_portal": "https://pgportal.gov.in",
        "summary": "शिकायत / अपील पत्र तैयार कर दिया गया है। आप इसे पीजी पोर्टल (pgportal.gov.in) पर या तहसील/ब्लॉक कार्यालय में जमा कर सकते हैं।",
    }
