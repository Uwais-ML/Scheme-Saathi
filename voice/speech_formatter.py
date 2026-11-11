"""Speech text formatter: separates display text and speech-optimized text.

Transforms numbers, digits, currencies, and abbreviations into smooth natural
text suitable for Text-to-Speech (TTS) engines in Hindi and English.
"""

import re

# Digit words mapping
HINDI_DIGITS = {
    "0": "शून्य",
    "1": "एक",
    "2": "दो",
    "3": "तीन",
    "4": "चार",
    "5": "पाँच",
    "6": "छह",
    "7": "सात",
    "8": "आठ",
    "9": "नौ",
}

ENGLISH_DIGITS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

# Common abbreviations expansion
ABBREVIATIONS_HI = {
    "pm-kisan": "प्रधानमंत्री किसान",
    "pm kisan": "प्रधानमंत्री किसान",
    "pmjay": "आयुष्मान भारत",
    "pmay": "प्रधानमंत्री आवास योजना",
    "mgnrega": "मनरेगा",
    "nrega": "नरेगा",
    "csc": "सीएससी",
    "dbt": "डायरेक्ट बेनिफिट ट्रांसफर",
    "otp": "ओटीपी",
    "sms": "एसएमएस",
    "pin": "पिन",
    "bpl": "बीपीएल",
    "ifsc": "आईएफएससी",
    "kyc": "केवाईसी",
}

ABBREVIATIONS_EN = {
    "pm-kisan": "Pradhan Mantri Kisan",
    "pm kisan": "Pradhan Mantri Kisan",
    "pmjay": "Pradhan Mantri Jan Arogya Yojana",
    "mgnrega": "MGNREGA",
    "csc": "CSC centre",
    "dbt": "Direct Benefit Transfer",
    "otp": "O T P",
    "sms": "SMS",
    "pin": "PIN",
    "bpl": "BPL",
    "ifsc": "I F S C code",
    "kyc": "K Y C",
}


def _number_to_hindi_words(n: int) -> str:
    """Convert an integer <= 99,99,99,999 to Hindi words."""
    if n == 0:
        return "शून्य"

    units = [
        "", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ",
        "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस",
        "बीस", "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाइस", "उनतीस",
        "तीस", "इकतीस", "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस", "सैंतीस", "अड़तीस", "उनतालीस",
        "चालीस", "इकतालीस", "बयालीस", "तैंतालीस", "चवालीस", "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास",
        "पचास", "इक्यावन", "बावन", "तिरेपन", "चौवन", "पचपन", "छप्पन", "सत्तावन", "अट्ठावन", "उनसठ",
        "साठ", "इकसठ", "बासठ", "तिरेसठ", "चौंसठ", "पैंसठ", "छियासठ", "सरसठ", "अड़सठ", "उनहत्तर",
        "सत्तर", "इकहत्तर", "बहत्तर", "तिहत्तर", "चौहत्तर", "पचहत्तर", "छिहत्तर", "सतहत्तर", "अठहत्तर", "उनासी",
        "अस्सी", "इक्यासी", "बयासी", "तिरासी", "चौरासी", "पचासी", "छियासी", "सत्तासी", "अट्ठासी", "नवासी",
        "नब्बे", "इक्यानवे", "बानवे", "तिरानवे", "चौरानवे", "पंचानवे", "छियानवे", "सत्तानवे", "अट्ठानवे", "निन्यानवे",
    ]

    parts = []
    crore = n // 10000000
    n %= 10000000
    if crore > 0:
        parts.append(f"{_number_to_hindi_words(crore)} करोड़")

    lakh = n // 100000
    n %= 100000
    if lakh > 0:
        parts.append(f"{_number_to_hindi_words(lakh)} लाख")

    thousand = n // 1000
    n %= 1000
    if thousand > 0:
        parts.append(f"{_number_to_hindi_words(thousand)} हज़ार")

    hundred = n // 100
    n %= 100
    if hundred > 0:
        parts.append(f"{units[hundred]} सौ")

    if n > 0:
        parts.append(units[n])

    return " ".join(parts).strip()


def _number_to_english_words(n: int) -> str:
    """Convert an integer <= 999,999,999 to English words."""
    if n == 0:
        return "zero"

    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    def _small_num(val: int) -> str:
        res = []
        if val >= 100:
            res.append(f"{ones[val // 100]} hundred")
            val %= 100
        if val >= 20:
            t = tens[val // 10]
            o = ones[val % 10]
            res.append(f"{t} {o}".strip() if o else t)
        elif val > 0:
            res.append(ones[val])
        return " ".join(res)

    parts = []
    if n >= 10000000:
        cr = n // 10000000
        parts.append(f"{_small_num(cr)} crore")
        n %= 10000000
    if n >= 100000:
        lk = n // 100000
        parts.append(f"{_small_num(lk)} lakh")
        n %= 100000
    if n >= 1000:
        th = n // 1000
        parts.append(f"{_small_num(th)} thousand")
        n %= 1000
    if n > 0:
        parts.append(_small_num(n))

    return " ".join(parts).strip()


def format_digits_for_speech(digits: str, language: str = "hi") -> str:
    """Format a long digit string (phone, Aadhaar, account) with pauses in groups.

    - 12 digits (Aadhaar): 4-4-4 grouping with comma pause
    - 10 digits (Phone): 5-5 grouping with comma pause
    - Other lengths (>=4): grouped in chunks of 3 or 4
    """
    cleaned = re.sub(r"\D", "", digits)
    if not cleaned:
        return digits

    dict_map = HINDI_DIGITS if language.startswith("hi") else ENGLISH_DIGITS

    def to_words(grp: str) -> str:
        return " ".join(dict_map.get(d, d) for d in grp)

    if len(cleaned) == 12:
        # Aadhaar: 4 - 4 - 4
        g1, g2, g3 = cleaned[:4], cleaned[4:8], cleaned[8:]
        return f"{to_words(g1)}, {to_words(g2)}, {to_words(g3)}"
    elif len(cleaned) == 10:
        # Phone: 5 - 5
        g1, g2 = cleaned[:5], cleaned[5:]
        return f"{to_words(g1)}, {to_words(g2)}"
    else:
        # Chunk in 3s or 4s
        chunks = [cleaned[i:i+4] for i in range(0, len(cleaned), 4)]
        return ", ".join(to_words(c) for c in chunks)


def format_currency_for_speech(amount_str: str, language: str = "hi") -> str:
    """Convert currency strings like '₹6,000', '6000 रुपये', 'Rs. 500' to words."""
    # Strip currency symbols and commas
    cleaned_num = re.sub(r"[^\d]", "", amount_str)
    if not cleaned_num:
        return amount_str

    val = int(cleaned_num)
    if language.startswith("hi"):
        words = _number_to_hindi_words(val)
        return f"{words} रुपये"
    else:
        words = _number_to_english_words(val)
        return f"{words} rupees"


def format_for_speech(text: str, language: str = "hi") -> str:
    """Transform raw text into TTS-optimized speech text.

    1. Expands abbreviations.
    2. Converts currency amounts to words.
    3. Formats long digit strings (Aadhaar, phones, accounts) with pauses.
    4. Removes markdown stars, hashes, and formatting bullets.
    """
    if not text:
        return ""

    out = text

    # Remove bold / italic / bullet markdown characters
    out = re.sub(r"[*#_`~]", " ", out)

    # 1. Expand abbreviations (case insensitive word boundary)
    abbr_map = ABBREVIATIONS_HI if language.startswith("hi") else ABBREVIATIONS_EN
    for abbr, expanded in abbr_map.items():
        pattern = re.compile(rf"\b{re.escape(abbr)}\b", re.IGNORECASE)
        out = pattern.sub(expanded, out)

    # 2. Currency amounts (e.g. ₹6000, ₹ 6,000, 6000 रुपये, Rs. 500, Rs 500)
    def _curr_repl(match: re.Match) -> str:
        return format_currency_for_speech(match.group(0), language=language)

    # Patterns for currencies
    curr_patterns = [
        r"[₹]\s*[\d,]+",
        r"\b(?:Rs\.?|INR)\s*[\d,]+",
        r"\b[\d,]+\s*(?:रुपये|रुपए|rupees)",
    ]
    for cp in curr_patterns:
        out = re.sub(cp, _curr_repl, out, flags=re.IGNORECASE)

    # 3. Long digit strings (Aadhaar 12-digit, phone 10-digit, account numbers 9+ digits)
    # Match standalone digit sequences of 9 to 16 digits (optionally space/dash separated)
    def _digit_repl(match: re.Match) -> str:
        raw_digits = match.group(0)
        return format_digits_for_speech(raw_digits, language=language)

    digit_pattern = r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b|\b\d{10}\b|\b\d{9,16}\b"
    out = re.sub(digit_pattern, _digit_repl, out)

    # Clean redundant whitespace
    out = re.sub(r"\s+", " ", out).strip()

    return out
