# 🤝 Scheme Saathi – योजना साथी

A **voice-first welfare scheme assistant** for low-literacy users in India.  
Supports Hindi, English, Marathi and Tamil; works on any mobile or desktop browser.

---

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Configure secrets
cp .env.example .env
# Edit .env with your API keys

# 3. Ingest scheme data into RAG
make ingest

# 4. Start the server
make run
# → http://localhost:8000
```

Then open `http://localhost:8000` in your browser.

---

## Make Targets

| Command        | Description                                       |
|----------------|---------------------------------------------------|
| `make install` | Create venv + install all deps                   |
| `make ingest`  | Build ChromaDB from `rag/data/schemes/`          |
| `make test`    | Run all 132+ unit & integration tests (100% pass) |
| `make eval`    | Run full Phase 3 CI evaluation suite             |
| `make run`     | Production server on `:8000`                     |
| `make dev`     | Dev server with `--reload`                       |

---

## Phase 3 Upgrades & Capabilities

1. **Safety Guardrails & Scam Protection (Phase 18)**
   - Two-step input classifier: crisis detection (self-harm, domestic violence, child protection, medical, hunger) routes immediately to national verified helplines.
   - Output verification: zero-tolerance regex & heuristic interceptor preventing approval promises, OTP/PIN requests, and unlisted URLs.
   - Aadhaar number masking in memory and logs.

2. **Household Profiles & Member Switching (Phase 17)**
   - Multiple family members under one household account (`self`, `spouse`, `child`, `mother`, etc.).
   - Explicit consent tracking for assisted filing.
   - Complete data isolation preventing field leaks between family members.

3. **Document Acquisition Help & Alternatives (Phase 19)**
   - Step-by-step acquisition instructions for missing documents (Aadhaar, Ration Card, Income Certificate, Land Records).
   - Topological dependency sort ensuring prerequisite documents are acquired in correct order.
   - Accepted alternatives lookup before requiring new applications.

4. **Deterministic Benefit Ranking (Phase 20)**
   - Mathematical ranking: `(benefit_norm^w_b) * (confidence^w_c) / (effort_score^w_e)`.
   - Tunable user preferences: `balanced`, `highest_value`, `easiest`, `fastest`.
   - Automatic exclusion of expired deadlines or closed schemes.

5. **Human Escalation & CSC Handoff Packet (Phase 21)**
   - Identifies verified local government offices (Tehsil, CSC, Panchayat) in district.
   - Generates clean, printable HTML/PDF handoff summary containing verified document status and checklist to take to the local office.

6. **Rejection Explanation & Grievance Draft (Phase 22)**
   - Regex and structural classification of rejection letters (`name_mismatch`, `aadhaar_bank_link`, `incomplete_documents`, etc.).
   - Generates official grievance appeal letters without fabricated facts.

7. **Scheme Freshness Pipeline (Phase 23)**
   - Content hash monitoring via SHA256 checksums (`python -m scripts.refresh_schemes`).
   - Human review & staging in pending directory before touching the live RAG corpus (`python -m scripts.review_updates`).
   - *Optional Automation Note:* The owner may run `refresh_schemes` periodically via an OS cron job or systemd timer (e.g., `0 2 * * 0 .venv/bin/python -m scripts.refresh_schemes` for weekly updates).

8. **Voice Upgrades & Audio Controls (Phase 24)**
   - Code-level `speech_formatter.py`: digit-by-digit reading with pauses for Aadhaar / phone numbers, natural spoken currencies, and abbreviation expansions.
   - Web Audio `AnalyserNode` Barge-in: interrupting the agent immediately pauses TTS playback and activates the microphone.
   - Silence auto-stop after 1.5s silence; gentle prompt after 8s silence (single prompt, never loops).
   - Deterministic voice commands: "repeat", "slower" (0.8x), "faster" (1.2x), "stop", "wait", "go back".

---

## API Endpoints

| Method | Path                       | Description                                      |
|--------|----------------------------|--------------------------------------------------|
| POST   | `/api/session`             | Create / resume a session                        |
| POST   | `/api/chat`                | Agent turn (text + optional upload IDs)          |
| POST   | `/api/stt`                 | Audio → text (AssemblyAI)                        |
| POST   | `/api/tts`                 | Text → WAV (Cartesia Sonic + speech formatter)   |
| POST   | `/api/voice_command`       | Deterministic voice control & entity confirmation|
| GET    | `/api/household`           | Retrieve household members                       |
| POST   | `/api/household/member`    | Add family member to household                   |
| POST   | `/api/household/switch`    | Switch active family member                      |
| POST   | `/api/handoff/packet`      | Generate printable CSC/Panchayat handoff summary |
| POST   | `/api/grievance/draft`     | Generate formal grievance appeal letter          |
| POST   | `/api/upload`              | Upload document for VLM analysis                 |
| GET    | `/api/form/preview/{id}`   | Current form preview                             |
| POST   | `/api/form/confirm`        | User confirms form correctness                   |
| GET    | `/api/health`              | Liveness check                                   |
| GET    | `/api/admin/status?dev=1`  | ModelRouter health status table                  |

---

## Running Verification & Evals

```bash
# 1. Run full test suite (132 tests)
pytest tests/ -v

# 2. Run CI evaluation suite (100% CI Gate)
make eval

# 3. Check curated data for unverified entries or TODO_VERIFY
python -m scripts.check_data
```
