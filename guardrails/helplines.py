"""Helper for loading and looking up verified/unverified helplines."""

import json
import logging
from pathlib import Path
from typing import Any
from config.settings import settings

logger = logging.getLogger(__name__)

HELPLINES_PATH = Path(settings.BASE_DIR) / "data" / "helplines.json"


def load_helplines() -> list[dict[str, Any]]:
    """Load helplines from data/helplines.json."""
    if not HELPLINES_PATH.exists():
        return []
    try:
        with open(HELPLINES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("helplines", [])
    except Exception as exc:
        logger.error("Failed to load helplines.json: %s", exc)
        return []


def get_helpline_for_crisis(crisis_type: str) -> dict[str, Any] | None:
    """Find the best helpline matching a crisis type."""
    helplines = load_helplines()
    for h in helplines:
        if h.get("crisis_type") == crisis_type:
            return h
    # Fallback to general emergency (112)
    for h in helplines:
        if h.get("number") == "112":
            return h
    return None


def format_crisis_response(crisis_type: str, language: str = "hi") -> str:
    """Generate an immediate, empathetic crisis assistance message."""
    helpline = get_helpline_for_crisis(crisis_type)
    number = helpline.get("number", "112") if helpline else "112"
    name_obj = helpline.get("name", {}) if helpline else {}
    name = name_obj.get(language, name_obj.get("hi", "आपातकालीन सेवा"))

    if language == "en":
        return (
            f"Please stay safe. If you or someone with you is in immediate distress, "
            f"please call {name} at {number} right now. Your safety is the first priority.\n"
            f"Would you like to continue with welfare scheme information, or do you need other help?"
        )
    elif language == "mr":
        return (
            f"कृपया सुरक्षित राहा. आपल्याला तात्काळ मदतीची गरज असल्यास, कृपया {name} - {number} वर त्वरित संपर्क साधा. आपली सुरक्षितता सर्वात महत्त्वाची आहे.\n"
            f"आपण सरकारी योजनेची माहिती पुढे चालू ठेवू इच्छिता का?"
        )
    elif language == "ta":
        return (
            f"தயவுசெய்து பாதுகாப்பாக இருங்கள். உங்களுக்கு அவசர உதவி தேவைப்பட்டால், {name} - {number} என்ற எண்ணை உடனடியாக தொடர்பு கொள்ளவும்.\n"
            f"திட்ட விவரங்களை தொடர விரும்புகிறீர்களா?"
        )
    else:  # Hindi default
        return (
            f"कृपया सुरक्षित रहें। आपकी सुरक्षा सबसे महत्वपूर्ण है। "
            f"यदि आपको तुरंत सहायता की आवश्यकता है, तो कृपया {name} ({number}) पर अभी कॉल करें।\n"
            f"क्या आप सरकारी योजनाओं की जानकारी जारी रखना चाहते हैं?"
        )
