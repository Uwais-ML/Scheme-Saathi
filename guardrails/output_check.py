"""Output safety check: blocks approval promises, unlisted URLs/numbers, sensitive data, OTP requests."""

import json
import logging
import re
from pathlib import Path
from config.settings import settings

logger = logging.getLogger(__name__)

ALLOWLISTS_PATH = Path(settings.BASE_DIR) / "data" / "allowlists.json"

_APPROVAL_PATTERNS = [
    r"you\s+will\s+(definitely|guaranteed|certainly|surely)\s+(get|receive)",
    r"guaranteed\s+(approval|benefit|amount|payment)",
    r"100%\s*(approval|milega|guaranteed)",
    r"पक्का\s*मिलेगा|जरूर\s*मिलेगा|गारंटी\s*है|निश्चित\s*रूप\s*से\s*मिलेगा",
    r"pakka\s*milega|zaroor\s*milega|guarantee\s*hai",
]

_COMPILED_APPROVAL = [re.compile(pat, re.IGNORECASE) for pat in _APPROVAL_PATTERNS]

_OTP_REQUEST_PATTERNS = [
    r"(please\s+)?(share|give|tell|enter|send|provide)\s+(your\s+)?(otp|pin|cvv|password)",
    r"(apna|apni|अपना|अपनी)\s*(otp|pin|cvv|password|पिन|ओटीपी)\s*(batao|bataiye|share\s*karo|do|bhejo|नंबर\s*बताइए|बताइए|दीजिए)",
    r"(otp|pin|cvv|password|पिन|ओटीपी)\s*(bataiye|dijiye|share\s*kijiye|बताइए|दीजिए)",
    r"\b(pin|otp|cvv|password)\b\s*नंबर\s*(बताइए|दीजिए)",
]

_COMPILED_OTP = [re.compile(pat, re.IGNORECASE) for pat in _OTP_REQUEST_PATTERNS]

_LEGAL_MEDICAL_PATTERNS = [
    r"as\s+your\s+(lawyer|doctor|attorney)",
    r"legal\s+verdict|i\s+advise\s+legal\s+action",
    r"take\s+this\s+medication|prescription\s+dose",
]

_COMPILED_LEGAL_MEDICAL = [re.compile(pat, re.IGNORECASE) for pat in _LEGAL_MEDICAL_PATTERNS]

# URLs regex
_URL_PATTERN = re.compile(r"https?://([A-Za-z0-9.-]+)(/[^\s]*)?", re.IGNORECASE)

# 12-digit ID regex (like Aadhaar)
_AADHAAR_PATTERN = re.compile(r"\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b")


def _load_allowlists() -> dict:
    if ALLOWLISTS_PATH.exists():
        try:
            with open(ALLOWLISTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load allowlists.json: %s", e)
    return {"domains": [".gov.in", ".nic.in"], "phone_numbers": []}


def check_output(text: str) -> tuple[str, list[str]]:
    """Inspect and sanitize agent output.

    Returns:
        (sanitized_text, violations_list)
    """
    violations = []
    cleaned = text

    # 1. Mask full 12-digit IDs
    def mask_id(match: re.Match) -> str:
        d1, d2, d3 = match.groups()
        return f"XXXX-XXXX-{d3}"

    if _AADHAAR_PATTERN.search(cleaned):
        cleaned = _AADHAAR_PATTERN.sub(mask_id, cleaned)
        violations.append("unmasked_id_detected")

    # 2. Check for OTP / PIN / CVV requests
    for pat in _COMPILED_OTP:
        if pat.search(cleaned):
            violations.append("otp_or_secret_request")
            cleaned = (
                "⚠️ सुरक्षा सूचना: हम कभी भी आपसे OTP, PIN, पासवर्ड या बैंक विवरण नहीं मांगते।"
            )
            break

    # 3. Check for approval promises
    for pat in _COMPILED_APPROVAL:
        if pat.search(cleaned):
            violations.append("approval_promise")
            cleaned = pat.sub(
                "you appear to be eligible; the final decision is made by the government office",
                cleaned,
            )

    # 4. Check for legal / medical advice
    for pat in _COMPILED_LEGAL_MEDICAL:
        if pat.search(cleaned):
            violations.append("legal_or_medical_advice")
            cleaned = pat.sub("Please consult a certified professional", cleaned)

    # 5. Check URLs against allowlist
    allowlists = _load_allowlists()
    allowed_domains = allowlists.get("domains", [])

    def check_url(match: re.Match) -> str:
        full_url = match.group(0)
        domain = match.group(1).lower()
        is_allowed = any(
            domain == d.lower() or domain.endswith(d.lower())
            for d in allowed_domains
        )
        if not is_allowed:
            violations.append(f"unlisted_url: {domain}")
            return "[आधिकारिक पोर्टल पर संपर्क करें]"
        return full_url

    cleaned = _URL_PATTERN.sub(check_url, cleaned)

    return cleaned, violations
