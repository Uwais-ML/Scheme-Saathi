"""Tools for human handoff, office lookup, and printable offline handoff packets."""

import json
from pathlib import Path
from typing import Any
from config.settings import settings
from state.models import mask_sensitive_id
from state.store import load_household, load_profile
from tools.registry import register_tool

OFFICES_PATH = Path(settings.BASE_DIR) / "data" / "offices.json"


def _load_offices() -> list[dict[str, Any]]:
    if not OFFICES_PATH.exists():
        return []
    try:
        with open(OFFICES_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("offices", [])
    except Exception:
        return []


@register_tool(
    "find_nearest_office",
    "Look up local government assistance offices (Panchayat, CSC, Tehsil) for a district.",
)
def find_nearest_office(district: str, kind: str | None = None) -> dict[str, Any]:
    """Find verified government offices in a district, or return safe generic local guidance."""
    offices = _load_offices()
    dist_norm = district.strip().lower()
    matches = []

    for o in offices:
        if o.get("district", "").lower() == dist_norm:
            if kind and o.get("kind") != kind:
                continue
            # Only speak verified addresses
            if o.get("verified") is True and o.get("address") != "TODO_VERIFY":
                matches.append(o)

    if matches:
        return {
            "ok": True,
            "district": district,
            "found_verified": True,
            "offices": matches,
            "advice": f"आपके जिले {district} में {len(matches)} सत्यापित कार्यालय मिले हैं।",
        }

    # Safe fallback if not verified
    return {
        "ok": True,
        "district": district,
        "found_verified": False,
        "offices": [],
        "advice": (
            f"हमारे पास {district} के लिए अभी सत्यापित कार्यालय सूची उपलब्ध नहीं है। "
            f"कृपया अपने नजदीकी ग्राम पंचायत भवन, वार्ड कार्यालय या स्थानीय जन सेवा केंद्र (CSC) पर संपर्क करें।"
        ),
    }


@register_tool(
    "create_handoff_packet",
    "Generate a one-page printable summary for the user to carry to a government office or CSC.",
)
def create_handoff_packet(
    member_id: str | None = None,
    issue_description: str = "दस्तावेज या सत्यापन में सहायता की आवश्यकता है।",
    household_id: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Compile an offline handoff packet with verified/rejected docs and carrying checklist."""
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

    if not profile:
        return {"ok": False, "error": "No user profile found for handoff packet."}

    user_name = profile.name or "आवेदक"
    district = profile.district or "अनिर्दिष्ट जिला"
    state = profile.state or "भारत"
    active_scheme = profile.active_scheme or "सामान्य सरकारी योजना सहायता"

    # Categorize documents
    verified_docs = []
    rejected_docs = []
    missing_docs = []

    for doc in profile.documents:
        if doc.status == "verified":
            verified_docs.append(doc.doc_id)
        elif doc.status == "rejected":
            rejected_docs.append(f"{doc.doc_id} (कारण: {doc.reason or 'अस्पष्ट'})")
        else:
            missing_docs.append(doc.doc_id)

    # Originals to carry
    originals_to_carry = [d for d in verified_docs] or ["आधार कार्ड", "बैंक पासबुक", "राशन कार्ड"]

    # Build clean printable HTML
    html = f"""<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8">
  <title>कार्यालय सहायता पत्र – {user_name}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; margin: 30px; color: #111; line-height: 1.5; }}
    .header {{ border-bottom: 2px solid #1a6b3c; padding-bottom: 12px; margin-bottom: 20px; }}
    h1 {{ color: #1a6b3c; font-size: 22px; margin: 0 0 4px 0; }}
    .badge {{ background: #e8f5e9; color: #1a6b3c; padding: 4px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; }}
    .meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
    .meta-table td {{ padding: 6px 10px; border-bottom: 1px solid #eee; }}
    .section-title {{ font-weight: bold; margin-top: 18px; margin-bottom: 8px; color: #333; }}
    ul {{ margin: 0; padding-left: 20px; }}
    .carry-box {{ background: #fffde7; border: 1px solid #ffd54f; padding: 12px; border-radius: 6px; margin-top: 15px; }}
    .footer {{ margin-top: 30px; font-size: 12px; color: #777; border-top: 1px solid #ddd; padding-top: 8px; text-align: center; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>🤝 योजना साथी – कार्यालय सहायता पत्र</h1>
    <span class="badge">ऑफलाइन प्रस्तुत करने हेतु</span>
  </div>

  <table class="meta-table">
    <tr><td><strong>आवेदक का नाम:</strong></td><td>{user_name}</td></tr>
    <tr><td><strong>जिला एवं राज्य:</strong></td><td>{district}, {state}</td></tr>
    <tr><td><strong>लक्षित योजना:</strong></td><td>{active_scheme}</td></tr>
    <tr><td><strong>सहायता का कारण:</strong></td><td>{issue_description}</td></tr>
  </table>

  <div class="section-title">📋 दस्तावेजों की वर्तमान स्थिति:</div>
  <ul>
    <li><strong>जांचे गए एवं मान्य दस्तावेज:</strong> {', '.join(verified_docs) if verified_docs else 'कोई नहीं'}</li>
    <li><strong>अमान्य / पुनः आवश्यक दस्तावेज:</strong> {', '.join(rejected_docs) if rejected_docs else 'कोई नहीं'}</li>
    <li><strong>शेष / अनुपलब्ध दस्तावेज:</strong> {', '.join(missing_docs) if missing_docs else 'कोई नहीं'}</li>
  </ul>

  <div class="carry-box">
    <strong>📌 कार्यालय में साथ ले जाने हेतु मूल (Original) दस्तावेज:</strong>
    <ul>
      {''.join(f'<li>{d}</li>' for d in originals_to_carry)}
    </ul>
  </div>

  <div class="footer">
    यह पत्र डिजिटल सहायक द्वारा तैयार किया गया है। कृपया कार्यालय में सभी विवरणों की मूल दस्तावेजों से पुष्टि करें।
  </div>
</body>
</html>
"""

    return {
        "ok": True,
        "member_name": user_name,
        "scheme": active_scheme,
        "district": district,
        "packet_html": html,
        "summary": (
            f"मैंने आपके लिए एक सहायता पर्ची (Handoff Summary) तैयार कर दी है जिसे आप अपने नजदीकी सीएससी या सरकारी कार्यालय में दिखा सकते हैं। "
            f"कृपया अपने साथ मूल दस्तावेज अवश्य ले जाएं।"
        ),
    }
