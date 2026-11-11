"""Deterministic voice command detection and entity confirmation.

Handles quick voice controls (repeat, slower, faster, stop, wait, go back)
and binary confirmation (yes / no) without requiring an LLM call.
"""

import re

# Deterministic patterns for voice navigation / audio controls
COMMAND_PATTERNS = {
    "repeat": [
        r"\b(?:repeat|say\s*again|one\s*more\s*time|replay)\b",
        r"(?:दोहराएं|दोहराओ|फिर\s*से\s*बोलो|फिर\s*से\s*बताएं|एक\s*बार\s*और|फिर\s*से)",
    ],
    "slower": [
        r"\b(?:slower|slow\s*down|too\s*fast|speak\s*slowly)\b",
        r"(?:धीरे|धीमे|आहिस्ता|कम\s*रफ़्तार|धीरे\s*बोलो|धीमे\s*बोलिए)",
    ],
    "faster": [
        r"\b(?:faster|speed\s*up|too\s*slow|speak\s*faster)\b",
        r"(?:तेज़|जल्दी|रफ़्तार\s*बढ़ाओ|तेज़\s*बोलो|तेज़ी\s*से)",
    ],
    "stop": [
        r"\b(?:stop|cancel|quiet|shut\s*up|end)\b",
        r"(?:रुकें|रुको|बंद\s*करो|चुप|समाप्त|रोको)",
    ],
    "wait": [
        r"\b(?:wait|hold\s*on|just\s*a\s*minute|one\s*sec|pause)\b",
        r"(?:इंतज़ार|रुकिए|एक\s*मिनट|थोड़ा\s*रुको|ठहरो)",
    ],
    "go back": [
        r"\b(?:go\s*back|back|previous|return)\b",
        r"(?:वापस|पीछे|पिछला|वापस\s*जाएं|पीछे\s*जाओ)",
    ],
}

# Yes/No confirmation patterns
YES_PATTERNS = [
    r"\b(?:yes|yeah|yep|correct|right|true|sure|okay|ok)\b",
    r"(?:हाँ|हा|सही|बिल्कुल|ठीक\s*है|जी\s*हाँ|अवश्य)",
]

NO_PATTERNS = [
    r"\b(?:no|nope|wrong|incorrect|not\s*really|cancel)\b",
    r"(?:नहीं|ना|गलत|जी\s*नहीं|अशुद्ध)",
]


def detect_voice_command(text: str, language: str = "hi") -> str | None:
    """Detect whether user utterance is a deterministic voice control command.

    Returns command name ('repeat', 'slower', 'faster', 'stop', 'wait', 'go back')
    or None if the utterance is normal conversation.
    """
    if not text:
        return None

    cleaned = text.strip().lower()

    # Short utterances or direct commands
    # If the user says a whole paragraph, it's not a simple command unless it matches directly
    for cmd, patterns in COMMAND_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, cleaned, re.IGNORECASE):
                # Only treat as a voice command if input is relatively brief (< 35 chars)
                if len(cleaned) < 35:
                    return cmd

    return None


def confirm_entity_response(text: str, language: str = "hi") -> bool | None:
    """Determine whether utterance confirms (True) or denies (False) an entity.

    Returns:
        True if affirmed ("yes", "हाँ", "सही है").
        False if denied ("no", "नहीं", "गलत है").
        None if ambiguous or unrecognized.
    """
    if not text:
        return None

    cleaned = text.strip().lower()

    for pat in YES_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            return True

    for pat in NO_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            return False

    return None
