"""Unit tests for Phase 8: STT and TTS voice integration with text-only fallback."""

from voice.stt import SpeechToText
from voice.tts import TextToSpeech


def test_stt_transcription_text_input():
    """Verify STT passes string through without errors."""
    stt = SpeechToText(provider="mock")
    text = stt.transcribe("मुझे किसान योजना चाहिए")
    assert text == "मुझे किसान योजना चाहिए"


def test_stt_transcription_none_input():
    """Verify STT handles empty audio gracefully."""
    stt = SpeechToText(provider="mock")
    assert stt.transcribe(None) == ""


def test_tts_text_fallback_mode(capsys):
    """Verify TTS prints cleanly with play_audio=False."""
    tts = TextToSpeech(provider="mock")
    tts.speak("नमस्ते, आपका स्वागत है।", play_audio=False)

    captured = capsys.readouterr()
    assert "नमस्ते, आपका स्वागत है।" in captured.out


def test_tts_play_audio_mock(capsys):
    """Verify TTS executes without crashing in mock mode with play_audio=True."""
    tts = TextToSpeech(provider="mock")
    tts.speak("जाँच सफल रही।", play_audio=True)

    captured = capsys.readouterr()
    assert "जाँच सफल रही।" in captured.out
