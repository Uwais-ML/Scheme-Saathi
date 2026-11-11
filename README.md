# 🤝 Scheme Saathi – योजना साथी

> **AgentX Hackathon 2026 Submission**  
> **Organized by:** Hack4Hack · Startup  
> **Problem Statement:** `PS-01 · Scheme Saathi: a welfare scheme agent`  
> *"Build an agent that talks to the user by voice or text in Hindi or a regional language, works out which schemes they qualify for, builds their document checklist, pre-fills the application form and tracks follow-ups."*

---

## 🏆 Hackathon Mandates & Core Compliance

| Mandatory Criteria | Scheme Saathi Implementation | Code References |
|---|---|---|
| **1. Tool calls for eligibility rules** | Evaluates scheme qualification deterministically across age, land holding, gender, state, and income using strict rule engines (not LLM hallucination). | [`tools/eligibility.py`](file:///Users/apple/Scheme%20Saathi/tools/eligibility.py)<br/>[`tools/household_tools.py`](file:///Users/apple/Scheme%20Saathi/tools/household_tools.py) |
| **2. Tool calls for form filling** | Multi-step form pipeline: `form_plan` checks missing fields, `fill_form` maps verified profile attributes into scheme templates, and `form_preview` generates a clean draft. | [`tools/form.py`](file:///Users/apple/Scheme%20Saathi/tools/form.py)<br/>[`forms/templates/`](file:///Users/apple/Scheme%20Saathi/forms/templates/) |
| **3. Human confirmation before submission** | **Zero blind or autonomous submissions.** Enforces a mandatory 3-layer human confirmation gate (verbal read-back of masked details, visual provisional preview banner, and explicit `✅ जानकारी सही है` confirmation button). | [`tools/form.py`](file:///Users/apple/Scheme%20Saathi/tools/form.py#L196-L212)<br/>[`api/routes/form.py`](file:///Users/apple/Scheme%20Saathi/api/routes/form.py#L27-L49)<br/>[`voice/commands.py`](file:///Users/apple/Scheme%20Saathi/voice/commands.py) |
| **4. Voice-first in Hindi & Regional Languages** | High-fidelity STT/TTS in Hindi, English, Marathi, and Tamil with Web Audio `AnalyserNode` barge-in interruption, silence VAD, and digit/currency speech formatting. | [`voice/speech_formatter.py`](file:///Users/apple/Scheme%20Saathi/voice/speech_formatter.py)<br/>[`voice/commands.py`](file:///Users/apple/Scheme%20Saathi/voice/commands.py)<br/>[`static/app.js`](file:///Users/apple/Scheme%20Saathi/static/app.js) |

---

## 🔒 The Human Confirmation Protocol

To ensure citizens have 100% control over their applications, Scheme Saathi requires explicit user consent before any form is finalized:

```
[Agent Gathers Info & Verifies Docs]
               │
               ▼
   [form_preview Tool Call]
               │
               ├─► Verbal Read-Back: "मैंने आपका आवेदन तैयार कर लिया है: [नाम, ज़मीन, खाता संख्या: XXXX-1234]... क्या ये विवरण सही हैं?"
               │
               ├─► Visual UI Preview: Displays draft fields under "⚠️ यह फ़ॉर्म अस्थायी है। कृपया जाँचें कि जानकारी सही है।"
               │
               ▼
[User Explicit Confirmation] ──(Voice: "हाँ, सही है" OR Button: "✅ जानकारी सही है")
               │
               ├─► Confirmed: Marks submission status & generates printable CSC/Panchayat visit packet.
               │
               └─► Denied: "नहीं / गलत है" ──► Halts immediately and asks which details to correct.
```

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
make install

# 2. Configure secrets (.env)
cp .env.example .env
# Add your API keys (AssemblyAI, Cartesia, OpenRouter/Cohere, Tavily)

# 3. Ingest welfare scheme database into RAG
make ingest

# 4. Start the application
make run
# → Open http://localhost:8000
```

---

## 🛠️ Tool Call Architecture

Scheme Saathi is **not a plain chatbot**. The agent operates via a strict 4-turn state execution matrix (`agent/loop.py`) invoking purpose-built deterministic tools:

```
User Spoken Voice / Text
          │
          ▼
   [check_input] ────────► Crisis / Emergency? ──► Immediate Helpline (112, 181, 1098, 1930)
          │
          ▼
   [Agent Loop (Plain Python / LangChain)]
          │
          ├── search_schemes ─────────► Multilingual ChromaDB parent-child vector search
          ├── check_eligibility ──────► Rule validation for PM-KISAN, PMJAY, Ujjwala, MGNREGA, Ladli Behna
          ├── add_member / switch ────► Multi-member household profiling with data isolation
          ├── rank_schemes ───────────► Mathematical benefit/effort optimization formula
          ├── form_plan & fill_form ──► Automated form template population from verified documents
          ├── form_preview ───────────► Read-back summary with masked sensitive IDs
          ├── find_nearest_office ────► Verified local CSC / Panchayat assistance lookup
          └── create_handoff_packet ──► Printable offline handoff packet
          │
          ▼
   [check_output] ───────► Approval promises? OTP/PIN requests? Unlisted URLs? ──► Intercepted & Blocked
          │
          ▼
TTS Voice & High-Contrast UI
```

---

## 📋 Comprehensive Make Targets

| Command        | Description                                            |
|----------------|--------------------------------------------------------|
| `make install` | Create virtual environment and install dependencies    |
| `make ingest`  | Build ChromaDB vector database from `rag/data/schemes/`|
| `make test`    | Run all 132+ unit & integration tests (100% pass)      |
| `make eval`    | Run CI evaluation suite against safety thresholds      |
| `make run`     | Start FastAPI production server on `:8000`             |
| `make dev`     | Start local development server with `--reload`         |

---

## 🚀 Key Innovation Highlights

1. **Dual-Layer Guardrails (Phase 18)**:
   - Zero-tolerance blocking on approval promises (*"पक्का मिलेगा"*), OTP/PIN harvesting, and unlisted phishing links.
   - Immediate routing for self-harm, domestic violence, child protection, and medical emergencies to verified national helplines.

2. **Multi-Member Households (Phase 17)**:
   - Manage multiple family members under one account with complete attribute isolation (farmer status or land sizes never bleed across members).
   - Auditable consent logging before storing data for another individual.

3. **Missing-Document Recovery (Phase 19)**:
   - Topological dependency sort ensuring prerequisite documents are acquired in order (e.g. Aadhaar prior to Income Certificate).
   - Accepted alternatives lookup before requiring brand-new documents.

4. **Deterministic Benefit Ranking (Phase 20)**:
   - Multi-factor scoring: $\text{Score} = \frac{(\text{benefit\_norm})^{w_b} \times (\text{confidence})^{w_c}}{(\text{effort\_score})^{w_e}}$
   - Adapts to user preferences: `balanced`, `highest_value`, `easiest`, `fastest`.

5. **Voice Upgrades & Audio Controls (Phase 24)**:
   - Speech formatter translates numbers to grouped pauses (Aadhaar 4-4-4, Phone 5-5) and spells out Hindi/English currencies.
   - Web Audio `AnalyserNode` barge-in allows interrupting the agent at any point during playback.
   - Deterministic voice controls: *"repeat"*, *"slower"* (0.8x), *"faster"* (1.2x), *"stop"*, *"wait"*, *"go back"*.

6. **Offline CSC / Panchayat Handoff (Phase 21 & 22)**:
   - Generates clean, printable HTML/PDF handoff summaries and formal grievance appeal letters when applications are rejected.

---

## 🧪 Verification & CI Gate

```bash
# 1. Run all Pytest tests
.venv/bin/pytest tests/ -q
======================= 132 passed, 7 warnings in 8.19s ========================

# 2. Run CI Gate
make eval
=================================================================
             SCHEME SAATHI: ALL EVALUATIONS & CI GATE            
=================================================================
RAG Hit@3 Accuracy:           100.0%
Crisis Recall (Safety):       100.0%
Unlisted URLs Escaped:        0
OTP Requests Escaped:         0
Approval Promises Escaped:    0
Household Member Isolation:   100.0%
Voice Command Accuracy:       100.0%
CI Gate Outcome:              PASSED
=================================================================
```

---

## 📄 Documentation Links

- [System Architecture](ARCHITECTURE.md)
- [Operational & Safety Rules](RULES.md)
- [REST API Reference](API_DOCS.md)
- [Data Verification Checklist](DATA_TODO.md)
