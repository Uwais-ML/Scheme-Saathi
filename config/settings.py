"""Application configuration and environment settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Holds configuration for models, storage, APIs, and languages."""

    # Project paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "rag" / "data" / "schemes"
    CHROMA_DIR: Path = BASE_DIR / "chroma_db"
    SQLITE_DB_PATH: Path = BASE_DIR / "welfare_agent.db"
    TEMPLATES_DIR: Path = BASE_DIR / "forms" / "templates"

    # API Keys
    MAIN_LLM_API_KEY: str = os.getenv("MAIN_LLM_API_KEY", "")
    VLM_API_KEY: str = os.getenv("VLM_API_KEY", "")
    STT_API_KEY: str = os.getenv("STT_API_KEY", "")
    TTS_API_KEY: str = os.getenv("TTS_API_KEY", "")

    # Multi-key fallback for Tavily search
    _tavily_raw = os.getenv("TAVILY_API_KEYS", "")
    TAVILY_API_KEYS: list[str] = [k.strip() for k in _tavily_raw.split(",") if k.strip()]

    # Swappable Providers & Models
    MAIN_LLM_PROVIDER: str = os.getenv("MAIN_LLM_PROVIDER", "mock")
    MAIN_LLM_MODEL: str = os.getenv("MAIN_LLM_MODEL", "gpt-4o-mini")

    VLM_PROVIDER: str = os.getenv("VLM_PROVIDER", "mock")
    VLM_MODEL: str = os.getenv("VLM_MODEL", "gpt-4o-mini")

    STT_PROVIDER: str = os.getenv("STT_PROVIDER", "mock")
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "mock")
    CARTESIA_VOICE_ID: str = os.getenv("CARTESIA_VOICE_ID", "01fc5e31-71e9-40dc-a220-06dbd4b4ed7e")

    # Languages
    DEFAULT_LANGUAGE: str = "hi"
    SUPPORTED_LANGUAGES: list[str] = ["hi", "en", "mr", "ta", "te", "bn"]

    # Retrieval & Agent loop constants
    RELEVANCE_THRESHOLD: float = 0.60
    CONFIDENCE_FLOOR: float = 0.50
    MAX_TOOL_STEPS: int = 6

    # Timeouts & Retries & Cooldowns
    DEFAULT_TIMEOUT_SEC: float = 15.0
    MAX_RETRIES: int = 2
    COOLDOWN_SEC: float = 60.0

    # Latency budgets (in milliseconds)
    BUDGET_TEXT_TURN_MS: float = 3000.0
    BUDGET_RAG_MS: float = 500.0
    BUDGET_VLM_MS: float = 10000.0
    BUDGET_TOTAL_PREVIEW_MS: float = 60000.0

    # Uploads limits
    MAX_UPLOAD_SIZE_MB: int = 15
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [".png", ".jpg", ".jpeg", ".pdf", ".webp"]

    # Ranking weights (Phase 20)
    RANKING_PREFERENCE_WEIGHTS: dict[str, dict[str, float]] = {
        "highest_value": {"benefit": 1.5, "confidence": 1.0, "effort": 0.5},
        "easiest": {"benefit": 0.5, "confidence": 1.0, "effort": 1.8},
        "fastest": {"benefit": 0.6, "confidence": 1.0, "effort": 1.6},
        "balanced": {"benefit": 1.0, "confidence": 1.0, "effort": 1.0},
    }

    # Scheme Freshness Pipeline (Phase 23)
    STALE_AFTER_DAYS: int = 30
    REFRESH_REPORT_DIR: Path = BASE_DIR / "reports" / "freshness"


settings = Settings()
