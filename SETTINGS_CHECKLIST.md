# Settings Freeze Checklist (Phase 13)

| Check | Requirement | Status | Notes |
|---|---|---|---|
| 1 | `config/models.yaml` has at least 2 entries for every role (3 or more for `main_llm` and `search`) | **DONE** | `main_llm` has 3 entries, `vlm` has 3, `stt` has 2, `tts` has 2, `embeddings` has 2, `search` has 3. |
| 2 | `.env.example` lists every key referenced by the YAML | **DONE** | Lists `MAIN_LLM_API_KEY`, `COHERE_API_KEY`, `MOCK_API_KEY`, `VLM_API_KEY`, `STT_API_KEY`, `TTS_API_KEY`, `CARTESIA_VOICE_ID`, `TAVILY_API_KEYS`. |
| 3 | `settings.py` validates the YAML at startup and fails with a readable message if an env var is missing | **DONE** | Validated via `ModelRouter.load_config()` and startup checks. |
| 4 | Timeouts, retry counts, cooldowns, relevance threshold, confidence floors, and latency budgets in `settings.py` | **DONE** | Centralized in `config/settings.py` (`DEFAULT_TIMEOUT_SEC`, `MAX_RETRIES`, `COOLDOWN_SEC`, `RELEVANCE_THRESHOLD`, `CONFIDENCE_FLOOR`, `BUDGET_*_MS`). |
| 5 | Tracing is on (timer / span helper writes to `traces/traces.jsonl`) | **DONE** | Implemented via `log_trace_span` in `utils/model_router.py`, logging timestamp, role, provider, model, latency_ms, outcome, and key_env. |
