"""Unit tests for Phase 24 speech formatter."""

from voice.speech_formatter import (
    format_for_speech,
    format_digits_for_speech,
    format_currency_for_speech,
)


def test_digit_grouping_aadhaar_phone():
    # 12 digits (Aadhaar)
    aadhaar_hi = format_digits_for_speech("123456789012", language="hi")
    assert "एक दो तीन चार" in aadhaar_hi
    assert "," in aadhaar_hi

    # 10 digits (Phone)
    phone_en = format_digits_for_speech("9876543210", language="en")
    assert "nine eight seven six five" in phone_en
    assert "," in phone_en


def test_currency_formatting():
    hi_curr = format_currency_for_speech("₹6,000", language="hi")
    assert "छह हज़ार रुपये" in hi_curr or "हज़ार" in hi_curr

    en_curr = format_currency_for_speech("Rs. 500", language="en")
    assert "five hundred rupees" in en_curr


def test_abbreviation_expansion():
    text = "कृपया PM-KISAN और CSC केंद्र पर अपना OTP न दें।"
    formatted = format_for_speech(text, language="hi")
    assert "प्रधानमंत्री किसान" in formatted
    assert "सीएससी" in formatted
    assert "ओटीपी" in formatted


def test_mixed_text_with_digits_and_currency():
    text = "आपका मोबाइल नंबर 9876543210 है और लाभ ₹2,000 मिलेगा।"
    res = format_for_speech(text, language="hi")
    # Currency expanded
    assert "दो हज़ार रुपये" in res or "हज़ार" in res
    # Digits expanded
    assert "नौ आठ" in res or "आठ सात" in res
