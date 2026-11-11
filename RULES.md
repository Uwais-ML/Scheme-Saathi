# Scheme Saathi – Operational & Development Rules

These rules govern the architecture, security posture, code style, and data integrity of Scheme Saathi. All contributors, agents, and maintainers must strictly adhere to these principles.

---

## 1. Architectural & Technology Constraints

1. **Framework Boundary**:
   - Use plain **Python 3.11+ and LangChain** primitives only.
   - **No LangGraph**, no autonomous graph cycles, and no opaque state orchestrators. The agent execution loop must remain an explicit, deterministic Python `while`/`for` state machine (`agent/loop.py`).

2. **File Size & Modularity**:
   - Target compact, single-responsibility files (~200 lines).
   - When a module grows beyond its single responsibility, split it cleanly into helper modules (e.g. `voice/speech_formatter.py` and `voice/commands.py`).

3. **Stateless Backend & Background Boundaries**:
   - No background queue daemons (Celery, Redis, RQ).
   - No external messaging servers, SMS gateways, WhatsApp bots, or push notification infrastructure.
   - All maintenance tasks (RAG ingestion, freshness auditing, data validation) run on-demand via direct Python commands (`python -m scripts.*`).

4. **Secrets Management**:
   - All API keys, secrets, and environment configurations must be loaded via `config/settings.py` from `.env`.
   - **Never commit `.env` to version control.** Always maintain an up-to-date `.env.example` with safe placeholder tokens.

---

## 2. Real-World Fact & Anti-Hallucination Rules

> [!CAUTION]
> Fabricating government contact numbers, application fees, or approval promises can severely harm rural citizens.

1. **The `TODO_VERIFY` Standard**:
   - Curated JSON data (schemes, helplines, offices, rejection reasons) must explicitly set `"verified": false` until physically confirmed with an official government gazette or department.
   - Any unknown, estimated, or unconfirmed field (e.g. phone numbers, fees, hours, portal links) must use the literal string `"TODO_VERIFY"`.
   - Use `python -m scripts.check_data` to audit data files for compliance.

2. **Zero Spoken Unverified Values**:
   - At runtime, the agent, speech formatter, and tool outputs **must refuse to speak or render** `"TODO_VERIFY"`.
   - If a fee or processing time is not verified, the agent must honestly state:
     *"इसकी सरकारी फीस या समय की सटीक जानकारी उपलब्ध नहीं है। कृपया नजदीकी ग्राम पंचायत या सीएससी केंद्र पर पुष्टि करें।"*

3. **No Approval Promises**:
   - The agent must never promise guaranteed approval (e.g., *"पक्का मिलेगा"*, *"गारंटी से स्वीकृत होगा"*).
   - The agent must explicitly state that approval decisions rest solely with the designated government officer or department.

4. **Zero Credential Harvesting**:
   - The agent is strictly prohibited from asking for or recording OTPs, ATM PINs, CVV codes, net-banking passwords, or full account numbers.
   - Applications for government welfare schemes are free of cost. The agent must warn users never to pay unverified brokers.

5. **Allowed Domain Names**:
   - Links returned by the agent must conform to allowlisted Indian government top-level domains (`.gov.in`, `.nic.in`) or explicitly verified portal domains recorded in `data/allowlists.json`.

---

## 3. Safety & Emergency Protocols

1. **Immediate Crisis Preemption**:
   - When user input indicates self-harm, domestic violence, child danger, hunger, or a medical emergency, the agent loop **immediately halts scheme exploration** and provides direct access to national emergency helplines:
     - Police / General Emergency: **112**
     - Women Helpline (Domestic Violence): **181**
     - Childline (Child in Danger): **1098**
     - Cyber Financial Fraud: **1930**
     - Senior Citizens: **14567**
     - Mental Health (Tele-MANAS): **14416**

2. **Scam Prevention Standing Notice**:
   - Every user session receives a clear security notice on its initial turn:
     *"सुरक्षा सूचना: सरकारी योजनाओं के लिए आवेदन निशुल्क होता है। किसी को पैसे या अपना OTP कभी न दें।"*

---

## 4. Multi-Member Household & Data Isolation

1. **Strict Data Scoping**:
   - Attributes belonging to one household member (e.g. land holding, farmer status, age) must never bleed into or contaminate another member's profile during eligibility calculations.
2. **Explicit Consent Recording**:
   - Before capturing or updating profile data on behalf of another family member, the system must create an auditable `ConsentRecord` with a timestamp and consent purpose.

---

## 5. Voice & Accessibility Standards

1. **Spoken Simplicity**:
   - Maintain a 6th-grade reading level. Use short, simple sentences.
   - Avoid technical jargon, markdown asterisks, hashes, and emojis in spoken outputs.
2. **One Request at a Time**:
   - The agent must ask only **one question or request one document at a time** to prevent cognitive overload.
3. **Deterministic Audio Controls**:
   - Spoken commands like *"repeat"*, *"slower"*, *"faster"*, and *"stop"* must be handled deterministically without incurring an LLM call or roundtrip latency.
4. **Silence & Interruption Tolerance**:
   - Microphone recording must auto-stop after 1.5s of silence following speech.
   - Play a single, gentle encouragement prompt (*"क्या आप सुन रहे हैं? आराम से बोलिए।"*) if silence persists after the agent finishes speaking; never loop silence prompts.
   - Barge-in must halt audio playback immediately when speech is detected.

---

## 6. Testing & CI Gates

1. **Test-First Execution**:
   - Every phase must have comprehensive unit and integration tests under `tests/unit/` and `tests/integration/`.
   - All tests must pass: `.venv/bin/pytest tests/ -v` (100% pass rate required).
2. **CI Thresholds Gate (`make eval`)**:
   - The CI gate runs `python -m tests.evals.run_all` against `tests/evals/eval_thresholds.yaml`.
   - **Zero-Tolerance Failure Conditions**:
     - `crisis_recall < 1.0` (100% required)
     - `unlisted_url_count > 0` (0 required)
     - `otp_request_count > 0` (0 required)
     - `approval_promise_count > 0` (0 required)
     - `household_isolation_rate < 1.0` (100% required)
