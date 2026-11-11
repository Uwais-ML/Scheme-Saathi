"""Text-to-Speech (TTS) interface with Cartesia Sonic API and text fallback."""

import logging
import os
import shutil
import subprocess
from pathlib import Path
import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class TextToSpeech:
    """Handles converting text responses into speech via Cartesia or local fallback."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        voice_id: str | None = None,
    ):
        self.provider = provider or settings.TTS_PROVIDER
        self.api_key = api_key or settings.TTS_API_KEY
        self.voice_id = voice_id or settings.CARTESIA_VOICE_ID

    def speak(self, text: str, lang: str = "hi", play_audio: bool = True) -> None:
        """Speak the given text or print it in text mode."""
        if not text:
            return

        # Print text output for readability in the console
        print(f"\n[Agent]: {text}")

        if not play_audio:
            return

        # Cartesia TTS API provider
        if self.provider == "cartesia" and self.api_key and "placeholder" not in self.api_key.lower():
            try:
                # Map language codes if necessary (Cartesia accepts 'hi', 'en', etc.)
                cartesia_lang = "hi" if lang.startswith("hi") else lang

                payload = {
                    "model_id": "sonic-latest",
                    "transcript": text,
                    "voice": {"mode": "id", "id": self.voice_id},
                    "language": cartesia_lang,
                    "output_format": {
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": 24000,
                    },
                }

                resp = requests.post(
                    "https://api.cartesia.ai/tts/bytes",
                    headers={
                        "X-API-Key": self.api_key,
                        "Cartesia-Version": "2024-06-10",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=15,
                )

                if resp.status_code == 200:
                    temp_wav = Path("/tmp/agent_speech.wav")
                    with open(temp_wav, "wb") as f:
                        f.write(resp.content)

                    # Play audio on macOS using afplay or Linux aplay
                    player = shutil.which("afplay") or shutil.which("aplay")
                    if player:
                        subprocess.run([player, str(temp_wav)], check=False)
                    return
                else:
                    logger.warning("Cartesia TTS API returned %d: %s", resp.status_code, resp.text)
            except Exception as exc:
                logger.error("Cartesia TTS synthesis failed: %s", exc)

        # Fallback to macOS native speech if available
        if shutil.which("say"):
            try:
                subprocess.run(
                    ["say", text],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
