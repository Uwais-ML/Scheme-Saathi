"""Input safety checks: crisis detection, scam risk, injection, and abuse filtering.

Two-step approach:
  1. Deterministic keyword/regex matching (fast, always runs).
  2. LLM disambiguation only when step-1 is ambiguous (try/except guarded).
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

CrisisType = Literal[
    "none",
    "hunger",
    "domestic_violence",
    "child_in_danger",
    "self_harm",
    "medical_emergency",
    "other_emergency",
]

OutOfScopeType = Literal[
    "none",
    "legal_advice",
    "medical_advice",
    "politics",
    "private_loans",
    "other",
]


class InputFlags(BaseModel):
    """Structured safety flags for a single user input."""

    crisis: CrisisType = "none"
    scam_risk: bool = False
    out_of_scope: OutOfScopeType = "none"
    prompt_injection: bool = False
    abusive: bool = False
    needs_human: bool = False


# ---------------------------------------------------------------------------
# Keyword / regex dictionaries
# ---------------------------------------------------------------------------

# Crisis keywords mapped to crisis_type
_CRISIS_PATTERNS: list[tuple[str, CrisisType]] = [
    # self-harm
    (r"आत्महत्या|suicide|kill\s+myself|khud ko maar|apne aap ko maar|jaan de|jeena nahi|"
     r"marna chahta|marna chahti|self.harm|cut myself|hang myself|end(?:ing)?\s+(?:my\s+)?life", "self_harm"),
    # child in danger (specific, check before generic violence)
    (r"बच्च[ाेों].{0,25}(?:खतर|मार|पीट|क्रूरता|हिंसा)|child.{0,25}(?:danger|abuse|beat)|bach[a-z]{1,4}.{0,15}khatr|"
     r"bacche.{0,10}khatr|child abuse|bachcha maar|bacha maar|"
     r"ladki bhaag|kidnap|childline", "child_in_danger"),
    # hunger
    (r"भूख|bhooka|bhooki|hungry|no food|khana nahi|kha nahi|starving|starved|bhookha", "hunger"),
    # domestic violence
    (r"मार|पीट|हिंसा|domestic violence|maar raha|maar rahi|pit raha|pit rahi|"
     r"darr|dara raha|dhamki|abuse|marpit|dahej|dowry|beats?\s+me|beating\s+me", "domestic_violence"),
    # medical emergency
    (r"हार्ट\s*अटैक|दिल\s*का\s*दौरा|एम्बुलेंस|ambulance|heart\s*attack|medical emergency|"
     r"hospital jana|behosh|seizure|fit aa|accident hua|khoon aa raha|blood coming|"
     r"dawa nahi|dawai nahi|injection chahiye", "medical_emergency"),
    # other emergency
    (r"\bemergency\b|aag lagi|fire lagi|flood|baadh|bijli ka jhatkaa|"
     r"police bulao|police call|112|help me|bachao|save me", "other_emergency"),
]

_COMPILED_CRISIS: list[tuple[re.Pattern[str], CrisisType]] = [
    (re.compile(pat, re.IGNORECASE), ctype)
    for pat, ctype in _CRISIS_PATTERNS
]

# Scam keywords
_SCAM_PATTERNS: list[str] = [
    r"OTP",
    r"पैसे\s*दो|paise\s*do|paise\s*dena|paisa\s*dena|fee\s*pay",
    r"\d+\s*(रुपये|rupee|rs|₹|हजार|लाख)\s*(देने|देंगे|मांग|fees?|शुल्क|दो|dene|dena|do)",
    r"pay\s*to\s*get|payment\s*required\s*for\s*benefit",
    r"lottery\s*(jeet|win|won)|prize\s*(jeet|win|won|claim)",
    r"पुरस्कार|inaam|lucky\s*draw",
    r"mujhe\s*\d+\s*(rupee|rs|₹|dena|do)\s*(honge|chahiye|padega)",
    r"\d+\s*(rupee|rs|₹)\s*(dene|jama|deposit|pay)\s*(honge|padenge|chahiye)",
    r"advance\s*(fee|payment|jama)",
    r"processing\s*fee|registration\s*fee\s*pay",
    r"khata\s*(number|no)\s*(do|share|batao|bhejo)",
    r"bank\s*(details|detail)\s*(do|share|batao|bhejo|send)",
    r"pin\s*(number|no)?\s*(batao|share|do|bhejo)",
    r"cvv\s*(batao|share|do|bhejo)",
    r"(password|पासवर्ड)\s*(batao|bataiye|share|do|bhejo)?",
    r"free\s*gift|gift\s*voucher\s*(milega|mila|claim)",
]

_COMPILED_SCAM: list[re.Pattern[str]] = [
    re.compile(pat, re.IGNORECASE) for pat in _SCAM_PATTERNS
]

# Injection patterns
_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above|your)\s+instructions",
    r"you\s+are\s+now\s+a\s+different",
    r"act\s+as\s+(?:if\s+you\s+are|a)\s+(?:different|evil|hacker|dan|jailbreak)",
    r"jailbreak",
    r"DAN\s+mode",
    r"override\s+(your\s+)?(system|safety|prompt)",
    r"disable\s+(your\s+)?(safety|filter|guardrail)",
    r"pretend\s+(you\s+are|you're)\s+(not\s+an\s+ai|human|dan)",
    r"<\s*script",
    r"prompt\s*injection",
    r"system\s*prompt\s*(leak|show|reveal|ignore|bypass)",
]

_COMPILED_INJECTION: list[re.Pattern[str]] = [
    re.compile(pat, re.IGNORECASE) for pat in _INJECTION_PATTERNS
]

# Abusive keywords (Hindi transliteration + English)
_ABUSIVE_PATTERNS: list[str] = [
    r"\bbc\b|\bmc\b|\bbhenchod\b|\bmadarchod\b|\bchutiya\b|\bgandu\b|\bharami\b",
    r"\bsaala\s+kutta\b|\bkutte\b|\bkamina\b",
    r"\bbastard\b|\bfuck\s*you\b|\bfucking\b|\bshut\s*up\b|\basshole\b",
]

_COMPILED_ABUSIVE: list[re.Pattern[str]] = [
    re.compile(pat, re.IGNORECASE) for pat in _ABUSIVE_PATTERNS
]

# Out-of-scope patterns
_OOS_PATTERNS: list[tuple[str, OutOfScopeType]] = [
    (r"वकील|कोर्ट|अदालत|मुकदमा|कानूनी\s*सलाह|vakeel|lawyer|advocate|court\s*case|legal\s*advice|sue\s*you|litigation", "legal_advice"),
    (r"डॉक्टर|दवाई\s*लिखो|इलाज\s*बताओ|doctor\s+bano|medical\s+advice|prescription|dawa\s+likho|diagnos", "medical_advice"),
    (r"वोट\s*दो|राजनीति|vote\s+karo|party\s+(ko\s+)?support|BJP|Congress|AAP|political", "politics"),
    (r"साहूकार|सूद\s*पर|private\s+loan|personal\s+loan\s+from|money\s+lender|sahukar|sood\s+par", "private_loans"),
]

_COMPILED_OOS: list[tuple[re.Pattern[str], OutOfScopeType]] = [
    (re.compile(pat, re.IGNORECASE), oos_type)
    for pat, oos_type in _OOS_PATTERNS
]


# ---------------------------------------------------------------------------
# Step 1: Deterministic check
# ---------------------------------------------------------------------------

def _deterministic_check(text: str) -> InputFlags:
    """Run all regex patterns; returns InputFlags (may still be ambiguous)."""
    flags = InputFlags()
    lower = text.lower()

    # Crisis
    for pattern, ctype in _COMPILED_CRISIS:
        if pattern.search(lower):
            flags.crisis = ctype
            break  # first match wins (priority order)

    # Scam
    for pattern in _COMPILED_SCAM:
        if pattern.search(text):
            flags.scam_risk = True
            break

    # Injection
    for pattern in _COMPILED_INJECTION:
        if pattern.search(text):
            flags.prompt_injection = True
            break

    # Abusive
    for pattern in _COMPILED_ABUSIVE:
        if pattern.search(lower):
            flags.abusive = True
            break

    # Out-of-scope
    for pattern, oos_type in _COMPILED_OOS:
        if pattern.search(lower):
            flags.out_of_scope = oos_type
            break

    # Human request / escalation pattern
    if re.search(r"talk\s+to\s+(someone|human|person|agent|executive|operator)|kisi\s+(insaan|vyakti|adhikari)\s+se\s+baat|baat\s+karao|human\s+support|किसी\s*(इंसान|व्यक्ति|अधिकारी)\s*से\s*बात", lower):
        flags.needs_human = True

    return flags


def _is_ambiguous(flags: InputFlags, text: str) -> bool:
    """Determine if LLM disambiguation is warranted.

    We only call LLM when no crisis/injection/scam was found deterministically
    AND the text is long enough and potentially concerning (not trivially safe).
    """
    if flags.crisis != "none" or flags.prompt_injection or flags.scam_risk:
        return False  # already classified clearly
    # Short, benign-looking messages don't need LLM
    if len(text.strip()) < 20:
        return False
    # Look for vague distress signals that didn't match regex
    vague_signals = re.compile(
        r"mujhe\s+madad|help\s+karo|koi\s+nahi|akela|tension|pareshaan|"
        r"dar\s+lag|dara\s+hua|nahi\s+reh\s+sakta|problem\s+hai",
        re.IGNORECASE,
    )
    return bool(vague_signals.search(text))


# ---------------------------------------------------------------------------
# Step 2: LLM disambiguation
# ---------------------------------------------------------------------------

_LLM_PROMPT = """You are a safety classifier for a government welfare chatbot serving rural India.
Classify the following user message. Reply ONLY with a JSON object with these keys:
- crisis: one of ["none","hunger","domestic_violence","child_in_danger","self_harm","medical_emergency","other_emergency"]
- scam_risk: true or false
- out_of_scope: one of ["none","legal_advice","medical_advice","politics","private_loans","other"]
- prompt_injection: true or false
- abusive: true or false

Message: {text}
"""


def _llm_check(text: str) -> InputFlags | None:
    """Call the main LLM for disambiguation. Returns None on any error."""
    try:
        import json
        from agent.llm import get_main_llm

        llm = get_main_llm()
        prompt = _LLM_PROMPT.format(text=text[:500])

        # Support both invoke() patterns (MockMainLLM returns AgentTurn; raw LLMs return str/obj)
        if hasattr(llm, "invoke"):
            result = llm.invoke([{"role": "user", "content": prompt}])
        else:
            return None

        # Extract text from result (AgentTurn or dict or str)
        if hasattr(result, "content") and result.content:
            raw = result.content
        elif isinstance(result, dict):
            raw = result.get("content", "")
        elif isinstance(result, str):
            raw = result
        else:
            return None

        if not raw:
            return None

        # Find JSON object in response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group())
        return InputFlags.model_validate(data)

    except Exception as exc:
        logger.warning("LLM disambiguation failed (non-fatal): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_input(text: str, language: str = "hi") -> InputFlags:
    """Classify user input for safety flags.

    Args:
        text: The raw user message.
        language: User's preferred language code (default "hi").

    Returns:
        InputFlags with crisis, scam_risk, out_of_scope, prompt_injection, abusive.
    """
    flags = _deterministic_check(text)

    if _is_ambiguous(flags, text):
        llm_flags = _llm_check(text)
        if llm_flags:
            # Merge: take the more severe classification
            if llm_flags.crisis != "none" and flags.crisis == "none":
                flags.crisis = llm_flags.crisis
            if llm_flags.scam_risk:
                flags.scam_risk = True
            if llm_flags.out_of_scope != "none" and flags.out_of_scope == "none":
                flags.out_of_scope = llm_flags.out_of_scope
            if llm_flags.prompt_injection:
                flags.prompt_injection = True
            if llm_flags.abusive:
                flags.abusive = True

    return flags
