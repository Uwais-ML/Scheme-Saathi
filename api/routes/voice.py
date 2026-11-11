"""Voice routes for STT and TTS."""

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from api.schemas import STTResponse
from voice.stt import SpeechToText
from voice.speech_formatter import format_for_speech
from voice.commands import detect_voice_command, confirm_entity_response
from config.settings import settings

router = APIRouter(prefix="/api", tags=["voice"])

stt_service = SpeechToText()


class TTSRequest(BaseModel):
    text: str
    language: str = "hi"


class VoiceCommandRequest(BaseModel):
    text: str
    language: str = "hi"


class VoiceCommandResponse(BaseModel):
    command: str | None = None
    is_confirmation: bool | None = None


@router.post("/voice_command", response_model=VoiceCommandResponse)
def handle_voice_command(req: VoiceCommandRequest):
    """Detect voice command or entity yes/no confirmation deterministically."""
    cmd = detect_voice_command(req.text, language=req.language)
    conf = confirm_entity_response(req.text, language=req.language)
    return VoiceCommandResponse(command=cmd, is_confirmation=conf)


@router.post("/stt", response_model=STTResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("hi"),
    session_id: str = Form(None),
):
    """Transcribe uploaded audio file to text via AssemblyAI."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file provided.")

    text = stt_service.transcribe(content, lang=language)
    return STTResponse(text=text, confidence=0.95 if text else 0.0)


@router.post("/tts")
def synthesize_speech(req: TTSRequest):
    """Convert text to speech WAV stream via Cartesia Sonic API."""
    import requests as http

    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    spoken_text = format_for_speech(req.text, language=req.language)

    api_key = settings.TTS_API_KEY
    if api_key and "placeholder" not in api_key.lower() and api_key.startswith("sk_car"):
        try:
            resp = http.post(
                "https://api.cartesia.ai/tts/bytes",
                headers={
                    "X-API-Key": api_key,
                    "Cartesia-Version": "2024-06-10",
                    "Content-Type": "application/json",
                },
                json={
                    "model_id": "sonic-latest",
                    "transcript": spoken_text,
                    "voice": {"mode": "id", "id": settings.CARTESIA_VOICE_ID},
                    "language": "hi" if req.language.startswith("hi") else req.language,
                    "output_format": {
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": 24000,
                    },
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return Response(content=resp.content, media_type="audio/wav")
        except Exception:
            pass

    # Return silent WAV fallback (browser speechSynthesis will take over)
    return Response(content=b"", media_type="audio/wav")
