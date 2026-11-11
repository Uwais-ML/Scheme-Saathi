"""Speech-to-Text (STT) interface with AssemblyAI and text fallback."""

import logging
import time
from typing import Any
import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class SpeechToText:
    """Handles transcribing speech into text via AssemblyAI or text input."""

    def __init__(self, provider: str | None = None, api_key: str | None = None):
        self.provider = provider or settings.STT_PROVIDER
        self.api_key = api_key or settings.STT_API_KEY

    def transcribe(self, audio: Any, lang: str = "hi") -> str:
        """Transcribe an audio buffer, file path, or stream to text in the given language."""
        if audio is None:
            return ""

        # If already string (text mode or manual input)
        if isinstance(audio, str):
            return audio.strip()

        # AssemblyAI API provider
        if self.provider == "assemblyai" and self.api_key and "placeholder" not in self.api_key.lower():
            try:
                headers = {"Authorization": self.api_key}

                # Upload audio file
                upload_res = requests.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers=headers,
                    data=audio,
                    timeout=30,
                )
                if upload_res.status_code != 200:
                    logger.error("AssemblyAI upload failed: %s", upload_res.text)
                    return ""

                audio_url = upload_res.json().get("upload_url")
                if not audio_url:
                    return ""

                # Request transcription
                transcribe_res = requests.post(
                    "https://api.assemblyai.com/v2/transcript",
                    headers=headers,
                    json={"audio_url": audio_url, "language_code": lang},
                    timeout=15,
                )
                transcript_id = transcribe_res.json().get("id")
                if not transcript_id:
                    return ""

                # Poll status
                for _ in range(30):
                    time.sleep(1)
                    poll_res = requests.get(
                        f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                        headers=headers,
                        timeout=15,
                    )
                    data = poll_res.json()
                    status = data.get("status")
                    if status == "completed":
                        return data.get("text", "")
                    elif status == "error":
                        logger.error("AssemblyAI transcription error: %s", data.get("error"))
                        return ""

            except Exception as exc:
                logger.error("AssemblyAI transcription failed: %s", exc)

        return ""
