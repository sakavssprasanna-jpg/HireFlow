# HireFlow — Technical Deep Dive & Defense Guide

This document provides concise, code-accurate technical explanations corresponding directly to the implementation in `backend/app/`, `frontend/src/`, and `tests/`.

---

### 1. Why this architecture?
**Code Reference**: `backend/app/main.py`, `docs/architecture.md`  
**Explanation**: We chose a decoupled, evidence-first architecture:
$$\text{Evidence Extraction} \longrightarrow \text{Quote Verification} \longrightarrow \text{Deterministic Scoring} \longrightarrow \text{Human Confirmation} \longrightarrow \text{Audit Logging}$$
This decouples non-deterministic LLM reasoning from deterministic numerical scoring and access control. AI is used solely where semantic understanding is required; deterministic Python code governs all state mutations and scores.

---

### 2. Why FastAPI?
**Code Reference**: `backend/app/main.py`, `backend/app/api/v1/`  
**Explanation**: FastAPI provides native asynchronous request handling, tight integration with Pydantic v2 schemas for runtime validation, automatic OpenAPI / Swagger generation, and high throughput on Python 3.12.

---

### 3. Why Pydantic?
**Code Reference**: `backend/app/domain/schemas.py`  
**Explanation**: Pydantic v2 enforces strict runtime data contracts. In HireFlow, Pydantic validates all incoming API payloads and out-of-bounds LLM responses. For example, `CandidateScoreResponse` enforces that weights sum to $\le 1.0$, confidence is bounded between $0.0$ and $1.0$, and invalid enum states are rejected with clear validation errors.

---

### 4. Why deterministic scoring?
**Code Reference**: `backend/app/services/scoring_engine.py`  
**Explanation**: Stochastic LLMs cannot guarantee consistent numerical outputs across runs ($\sigma^2 > 0$). In `ScoringEngine.calculate_score()`, scoring is a published, reproducible mathematical equation:
$$\text{Final Fit} = (S_{\text{must}} \times W_{\text{must}} + S_{\text{nice}} \times W_{\text{nice}} + S_{\text{exp}} \times W_{\text{exp}}) \times 100$$
Tested across 50 repeated executions, measured variance is exactly $\sigma^2 = 0.0$.

---

### 5. Why multiple providers?
**Code Reference**: `backend/app/ai/base.py`, `backend/app/ai/gemini_provider.py`, `backend/app/ai/groq_provider.py`  
**Explanation**: To prevent single-vendor lock-in and enable latency vs. quality trade-offs. The `BaseLLMProvider` abstraction standardizes calls across Google Gemini (high reasoning depth via `google-genai`) and Groq (ultra-low inference latency via OpenAI-compatible endpoints).

---

### 6. Why offline fallback?
**Code Reference**: `backend/app/ai/offline_fallback.py`, `backend/app/ai/factory.py`  
**Explanation**: Hackathon evaluators and enterprise CI/CD environments may lack cloud API keys or experience network outages. `OfflineFallbackProvider` provides a zero-dependency, deterministic heuristic engine that runs locally with zero external API calls while maintaining metadata honesty (`is_fallback=True`).

---

### 7. How is prompt injection handled?
**Code Reference**: `backend/app/services/security_scanner.py`  
**Explanation**: `SecurityScanner.scan_text()` executes regex and unicode analysis on resume and interview text prior to any AI invocation:
- Strips zero-width characters (`\u200B`, `\u00AD`) to defeat de-obfuscation evasion.
- Detects instruction overrides, ChatML delimiters (`<|im_start|>`), role prefixes (`system:`), and score tampering (`set score to 100%`).
- High-severity findings assign a `QUARANTINED` status, halting the pipeline under the 0-LLM Quarantine Invariant.

---

### 8. How is hallucinated evidence prevented?
**Code Reference**: `backend/app/services/quote_verifier.py`, `backend/app/services/ai_evidence_service.py`  
**Explanation**: `QuoteVerifier` enforces that every citation quote proposed by an LLM exists verbatim in the candidate's original document. If a model generates an ungrounded claim or paraphrases without exact source text, the verifier flags it as unverified and blocks it from becoming an accepted claim.

---

### 9. How does quote verification work?
**Code Reference**: `backend/app/services/quote_verifier.py`  
**Explanation**: 
1. Substring search matches the quote within the raw document.
2. If exact match fails, it applies whitespace normalization and typographic punctuation normalization (converting smart quotes `“`, `”` to straight quotes `"`).
3. On a match, it returns `is_valid=True` with exact `start_offset` and `end_offset` character indices.
4. If no match is found, it returns `is_valid=False`, flagging the claim as ungrounded.

---

### 10. Why human confirmation?
**Code Reference**: `backend/app/services/interview_service.py`, `backend/app/domain/enums.py`  
**Explanation**: Autonomous AI decision-making in hiring introduces legal, ethical, and compliance liabilities (EEOC, EU AI Act). AI outputs remain in an `InterviewEvidenceProposal` state (`PENDING_REVIEW`). Scores and candidate claims only update when a human recruiter executes an `approve` or `override` action.

---

### 11. How does interview evidence reconcile with resume evidence?
**Code Reference**: `backend/app/services/interview_service.py`  
**Explanation**: When an interview proposal is approved:
1. It looks up the existing `EvidenceClaimModel` for that skill requirement.
2. If the resume had `NOT_FOUND` and the interview provides `PROVEN`, the status upgrades to `PROVEN`, closing the competency gap.
3. If interview notes reveal that a resume claim was fabricated, the claim updates to `CONTRADICTED`.
4. `ScoringEngine.recalculate_for_candidate()` then computes the updated score and confidence.

---

### 12. How are contradictions handled?
**Code Reference**: `backend/app/services/scoring_engine.py`, `backend/app/domain/enums.py`  
**Explanation**: `CONTRADICTED` represents active negative evidence (e.g., a candidate claimed senior Kubernetes mastery on their resume, but could not explain basic pod lifecycle concepts during the interview). In the scoring math, `CONTRADICTED` carries a negative multiplier ($-0.5$), actively deducting points from the competency category.

---

### 13. How is missing evidence treated?
**Code Reference**: `backend/app/services/scoring_engine.py`  
**Explanation**: We enforce the invariant: `NOT_FOUND != NO_SKILL`.
A missing claim on a resume means there is no evidence yet, not that the candidate is disqualified. `NOT_FOUND` contributes $0.0$ points and lowers overall score *confidence*, but does NOT apply the active negative penalty ($-0.5$) reserved for `CONTRADICTED`.

---

### 14. How are recruiter overrides recorded?
**Code Reference**: `backend/app/api/v1/candidates.py`, `backend/app/db/models.py`  
**Explanation**: In `POST /api/v1/candidates/{id}/evidence/{claim_id}/override`:
1. The payload requires `new_status` and a non-empty `justification` string.
2. The claim is updated with `is_recruiter_override=True`.
3. An `AuditRecordModel` is committed with `event_type="RECRUITER_OVERRIDE"`, `actor="RECRUITER"`, the old status, the new status, and the justification.
4. Scores are immediately recalculated deterministically.

---

### 15. What happens if an LLM returns invalid JSON?
**Code Reference**: `backend/app/ai/base.py`, `backend/app/ai/offline_fallback.py`  
**Explanation**: LLM responses are parsed using Pydantic schemas. If JSON decoding fails or fields violate schema validation, a `ProviderSchemaValidationError` is raised. The calling service catches the error, logs the failure, and falls back to deterministic rule extraction without crashing the API.

---

### 16. What happens when an API key is missing?
**Code Reference**: `backend/app/ai/factory.py`  
**Explanation**: `ProviderFactory.get_provider()` checks environment variables. If `GEMINI_API_KEY` or `GROQ_API_KEY` is empty, it does not raise an unhandled exception. It automatically instantiates `OfflineFallbackProvider` and logs a transparent fallback notice.

---

### 17. What happens when a candidate changes in the UI?
**Code Reference**: `frontend/src/App.tsx`  
**Explanation**: In `loadCandidateContext()`, all previous candidate state is immediately flushed (`setFitScore(null)`, `setEvidenceClaims([])`, `setCandidateGaps(null)`, etc.) before dispatching network requests for the new candidate. This guarantees zero visual or logical state leakage between candidates.

---

### 18. How did you test cross-candidate state leakage?
**Code Reference**: `tests/eval_harness.py` (Section B & Section E)  
**Explanation**: The evaluation harness explicitly tested:
1. Submitting a citation from Candidate B's document to validate Candidate A's claim -> blocked with `is_valid=False`.
2. Inspecting Candidate B's score and gap models after updating Candidate A -> Candidate B's database records and fit score remained 100% unchanged.

---

### 19. What are the current limitations?
**Code Reference**: `docs/evaluation-report.md`  
**Explanation**: 
1. Scanned image PDFs without a text layer are unsupported without OCR.
2. SQLite audit logs lack cryptographic hash-chaining (Merkle tree tamper-evidence).
3. Cloud LLM live execution was not verified in the local evaluation environment due to absent API keys.
4. The security scanner relies on static pattern matching and unicode normalization, which cannot guarantee 100% defense against all future adversarial prompt jailbreaks.

---

### 20. What would you build next for production scale?
**Code Reference**: `docs/architecture.md`  
**Explanation**:
1. Migrate SQLite persistence to PostgreSQL with row-level security and read replicas.
2. Introduce an asynchronous task worker (Celery / Redis) for background PDF processing and bulk resume ingestion.
3. Implement cryptographic hash-chaining on the audit event ledger for regulatory SOC2/EEOC audits.
4. Add OCR support (via Tesseract or cloud Vision APIs) for scanned resume parsing.
5. Deploy an auxiliary lightweight LLM classifier for semantic prompt-injection defense.
