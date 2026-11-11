"""Tool for detecting scam and fraud risk in messages, calls, or claims."""

import json
import re
from pathlib import Path
from config.settings import settings
from tools.registry import register_tool

ALLOWLISTS_PATH = Path(settings.BASE_DIR) / "data" / "allowlists.json"


def _load_allowlists() -> dict:
    if ALLOWLISTS_PATH.exists():
        try:
            with open(ALLOWLISTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"domains": [".gov.in", ".nic.in"], "phone_numbers": []}


@register_tool(
    "check_scam_risk",
    "Analyze a suspicious call, message, or link to check if it is a government welfare scam.",
)
def check_scam_risk(text: str) -> dict:
    """Analyze a message, call description, or link for scam/fraud indicators.

    Args:
        text: The message or description provided by the user.

    Returns:
        dict with risk_level ("low", "medium", "high"), reasons list, and advice.
    """
    reasons = []
    text_lower = text.lower()

    # 1. Money asked to release government benefit
    if re.search(r"(fee|paisa|paise|rupee|rs|₹|charges|processing|deposit)\b.*(release|milega|dene|dena|dega|apply|do\b)", text_lower) or \
       re.search(r"(पैसे|रुपये|रुपया|शुल्क|फीस)\s+(दो|दें|दीजिए|देना|जमा)", text_lower) or \
       re.search(r"(पैसे|रुपये|रुपया|शुल्क|फीस).*(मिलेगा|पैसा)", text_lower):
        reasons.append("सरकारी योजनाओं के लिए किसी को भी रिश्वत या शुल्क देना गैर-कानूनी है। सरकारी आवेदन निशुल्क या तयशुदा न्यूनतम सीएससी शुल्क पर होते हैं।")

    # 2. OTP / PIN / CVV request
    if re.search(r"\b(otp|pin|cvv|password)\b", text_lower):
        reasons.append("किसी भी अधिकारी या व्यक्ति के साथ कभी भी OTP या PIN साझा न करें। सरकारी विभाग कभी OTP नहीं मांगते।")

    # 3. Urgency pressure
    if re.search(r"(urgent|immediately|last chance|24 hours|aaj hi|turant|jaldi|akhiri mauka|तुरंत|जल्दी|आखिरी मौका)", text_lower):
        reasons.append("दबाव या जल्दबाज़ी बनाना ठगों का मुख्य तरीका होता है।")

    # 4. Lottery or prize
    if re.search(r"(lottery|prize|lucky draw|crorepati|jeeta|inaam|इनाम|लॉटरी|विजेता)", text_lower):
        reasons.append("लॉटरी या मुफ्त इनाम का लालच देकर सरकारी योजना के नाम पर ठगी की कोशिश।")

    # 5. Non-official URLs
    urls = re.findall(r"https?://([A-Za-z0-9.-]+)", text_lower)
    allowlist = _load_allowlists().get("domains", [".gov.in", ".nic.in"])
    suspicious_urls = []
    for u in urls:
        if not any(u == d or u.endswith(d) for d in allowlist):
            suspicious_urls.append(u)
    if suspicious_urls:
        reasons.append(f"संदिग्ध या गैर-सरकारी वेबसाइट लिंक मिला: {', '.join(suspicious_urls)}")

    # Score calculation
    count = len(reasons)
    if count >= 2 or any("otp" in r.lower() for r in reasons) or any("रिश्वत" in r for r in reasons):
        risk_level = "high"
    elif count == 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    if risk_level == "high":
        advice = (
            "🚨 यह एक गंभीर धोखाधड़ी (Scam) का प्रयास लग रहा है! "
            "कृपया कोई भी पैसा न दें और न ही OTP साझा करें। "
            "यदि आपके साथ धोखाधड़ी हुई है तो तुरंत राष्ट्रीय साइबर हेल्पलाइन 1930 पर कॉल करें या cybercrime.gov.in पर शिकायत दर्ज करें।"
        )
    elif risk_level == "medium":
        advice = (
            "⚠️ सावधानी बरतें। सरकारी योजनाओं की आधिकारिक जानकारी सिर्फ .gov.in या .nic.in वेबसाइटों पर या अपने स्थानीय ग्राम पंचायत/सीएससी केंद्र से ही प्राप्त करें।"
        )
    else:
        advice = (
            "✅ इस संदेश में सामान्य धोखाधड़ी के स्पष्ट संकेत नहीं मिले हैं। फिर भी, कभी भी अपना पासवर्ड या OTP किसी को न दें।"
        )

    return {
        "risk_level": risk_level,
        "reasons": reasons,
        "advice": advice,
    }
