"""Unit tests for Phase 24 voice command detection and entity confirmation."""

from voice.commands import detect_voice_command, confirm_entity_response


def test_voice_commands_hindi():
    assert detect_voice_command("कृपया फिर से बोलो", language="hi") == "repeat"
    assert detect_voice_command("थोड़ा धीरे बोलो", language="hi") == "slower"
    assert detect_voice_command("तेज़ बोलो", language="hi") == "faster"
    assert detect_voice_command("रुको", language="hi") == "stop"
    assert detect_voice_command("एक मिनट इंतज़ार करो", language="hi") == "wait"
    assert detect_voice_command("वापस जाएं", language="hi") == "go back"


def test_voice_commands_english():
    assert detect_voice_command("repeat please", language="en") == "repeat"
    assert detect_voice_command("slow down", language="en") == "slower"
    assert detect_voice_command("speed up", language="en") == "faster"
    assert detect_voice_command("stop", language="en") == "stop"
    assert detect_voice_command("wait a moment", language="en") == "wait"
    assert detect_voice_command("go back", language="en") == "go back"


def test_non_commands_return_none():
    assert detect_voice_command("मुझे पीएम किसान योजना के बारे में जानना है") is None
    assert detect_voice_command("मेरी उम्र 45 साल है और मेरे पास जमीन है") is None


def test_entity_confirmation():
    # Affirmative
    assert confirm_entity_response("हाँ", language="hi") is True
    assert confirm_entity_response("जी हाँ", language="hi") is True
    assert confirm_entity_response("yes that is right", language="en") is True
    assert confirm_entity_response("correct", language="en") is True

    # Negative
    assert confirm_entity_response("नहीं", language="hi") is False
    assert confirm_entity_response("गलत है", language="hi") is False
    assert confirm_entity_response("no", language="en") is False

    # Ambiguous
    assert confirm_entity_response("शायद हो सकता है") is None
