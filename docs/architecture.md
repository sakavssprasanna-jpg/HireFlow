# HireFlow — Architectural Decision Record (ADR)

## 1. System Overview & Architecture Objective
HireFlow is an evidence-first AI candidate screening and interview intelligence platform designed to assist human recruiters in making grounded, explainable, bias-resistant, and auditable hiring decisions.

**Central Operating Principle:**
> AI reasons. Tools retrieve and act. Deterministic code validates. Humans decide. Everything important is auditable.

HireFlow operates strictly under human oversight. The system produces intelligence and recommendations, but never autonomously hires or rejects candidates.

### Current Implementation Status Matrix (as of Phase 6 Verification Checkpoint)
| Component | Status | Verification / Notes |
| :--- | :--- | :--- |
| **FastAPI Core & Routing** | **Implemented & Tested** | `backend/app/main.py`, `/api/v1/health`, `/candidates/*`, `/roles/*`, `/interviews/*`, `/roles/{id}/matrix`, `/candidates/{id}/audit-trail`, `/candidates/{id}/document` verified |
| **SQLAlchemy 2.0 ORM** | **Implemented & Tested** | 9 tables + `interview_evidence_proposals`, relationships & indexes verified on SQLite |
| **Domain Pydantic v2 Schemas**| **Implemented & Tested** | Strict contracts, proposal review schemas, candidate matrix schemas, override validation tested via pytest |
| **BaseLLMProvider Protocol** | **Implemented & Tested** | `backend/app/ai/base.py` abstract interface with latency/token tracking |
| **OfflineFallbackProvider** | **Implemented & Tested** | Deterministic rule engine; explicitly non-AI (`is_fallback=True`), authentic excerpts |
| **GeminiProvider** | **Implemented & Tested** | `google-genai` SDK implementation with fallback resilience |
| **GroqProvider** | **Implemented & Tested** | `httpx` async OpenAI-compatible REST implementation |
| **Provider Factory** | **Implemented & Tested** | Graceful fallback on missing API keys with zero crashes |
| **Document Parsers (PDF/DOCX/TXT)**| **Implemented & Tested** | `pypdf`, `python-docx`, text decoders with magic byte checks |
| **Prompt Injection Quarantine** | **Implemented & Tested** | Multi-rule scanner with zero-width de-obfuscation stripping & line-start filters, 20/20 attacks quarantined (100% recall), 0 false positives |
| **Deterministic Quote Verifier**| **Implemented & Tested** | Substring search with character offset provenance & smart punctuation normalization; 100% hallucination blocking |
| **Deterministic Gap Detector**| **Implemented & Tested** | Prioritized classification (CRITICAL, HIGH, MEDIUM, LOW) |
| **AI Evidence Matching Agent**| **Implemented & Tested** | Quote verification gating AI claims; prevents hallucinated citations |
| **Gap-Directed Interview Gen**| **Implemented & Tested** | Grounding invariant enforced; no orphaned questions |
| **Interview Evidence Service**| **Implemented & Tested** | Post-interview notes ingestion, AI proposal extraction, human review gate |
| **Multi-Source Reconciliation**| **Implemented & Tested** | Contradiction priority, recruiter override precedence, NOT_FOUND!=NO_SKILL invariant |
| **Recruiter Overrides** | **Implemented & Tested** | Human-in-the-loop with audit logging & live score recalculation |
| **Deterministic Scoring Service**| **Implemented & Tested** | 100% mathematical formula, zero-variance verified ($\sigma^2 = 0.0$ across 50 runs) |
| **Frontend UI (React 19 + TS)** | **Implemented & Tested** | Phase 5 Recruiter Cockpit, Dual-Pane Studio, Audit & Security Center, Stale-State Leak Protection, Formula Inspector (`tsc && vite build` in ~2.2s) |
| **Evaluation & Adversarial Harness** | **Implemented & Tested** | `tests/eval_harness.py` 8-section automated evaluation, 59/59 pytest passing, `docs/evaluation-report.md` |


```
+-----------------------------------------------------------------------------------+
|                                PRESENTATION LAYER                                 |
|          React 19 + TypeScript (Modular CSS current; Tailwind planned)            |
+-----------------------------------------------------------------------------------+
                                         │  HTTP / REST (JSON Contracts)
                                         ▼
+-----------------------------------------------------------------------------------+
|                                   API LAYER                                       |
|               FastAPI (Python 3.12) - Routers, Request Validation, CORS           |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                             APPLICATION & USE CASES                               |
|   RoleRequisitionUseCase | CandidateIngestionUseCase | GroundingUseCase           |
|   InterviewIntelligenceUseCase | ScoringUseCase | AuditUseCase                    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                              DOMAIN & SERVICE LAYER                               |
|   Domain Entities & Enums | Evidence Reconciliation Engine | Deterministic Scoring |
|   Prompt-Injection Sanitizer | PII Anonymizer | Citation Substring Verifier       |
+-----------------------------------------------------------------------------------+
                     │                                         │
                     ▼                                         ▼
+-----------------------------------------+   +-------------------------------------+
|        AI PROVIDER ABSTRACTION          |   |          PERSISTENCE LAYER          |
|  BaseLLMProvider Protocol               |   |  SQLAlchemy 2.0 ORM                 |
|  ├── GeminiProvider (Google GenAI Free) |   |  SQLite (Initial portable, zero-cfg)|
|  ├── GroqProvider (Llama 3.3 Free)      |   |  PostgreSQL Ready (Clean repository |
|  └── OfflineFallbackProvider (Non-AI)   |   |  pattern, zero SQL lock-in)         |
+-----------------------------------------+   +-------------------------------------+
```

---

## 2. Architectural Layers & Boundaries

1. **Presentation Layer (`frontend/`):**
   * Single-Page Application in React with TypeScript.
   * Consumes typed REST API contracts from backend.
   * Houses zero business logic or scoring algorithms; focuses purely on state display, side-by-side synchronized citation highlighting, and recruiter interactions.
2. **API Layer (`backend/app/api/`):**
   * FastAPI routing, request validation via Pydantic v2 schemas, and standardized error response serialization.
   * Uniform error schema: `{ "detail": str, "error_code": str, "timestamp": str }`.
3. **Application / Use Cases Layer (`backend/app/use_cases/`):**
   * Orchestrates domain workflows (e.g., ingest resume -> sanitize -> extract claims -> match against requirements -> compute deterministic score).
4. **Domain Layer (`backend/app/domain/`):**
   * Pure business rules, entity models, and enums.
   * Independent of databases, frameworks, or AI providers.
5. **Services Layer (`backend/app/services/`):**
   * Domain-specific operations: `ScoringService` (100% deterministic math), `SanitizerService` (prompt-injection quarantine), `PIIService` (anonymization for blind screening), `EvidenceService` (grounding verification).
6. **AI Provider Abstraction (`backend/app/ai/`):**
   * Abstract interface decoupling business logic from concrete LLM APIs.
   * Handles timeouts, structured JSON schema enforcement, model metadata, and graceful fallback.
7. **Persistence Layer (`backend/app/db/`):**
   * SQLAlchemy 2.0 declarative models and repository abstractions.
   * Initialized on SQLite with WAL mode for zero-setup execution; easily targeted to PostgreSQL via connection string configuration.

---

## 3. Domain Modules & Responsibilities

1. **Job Description Module:** Parsing raw JD text, extracting structured competencies, identifying minimum experience requirements, and classifying Must-Have vs. Nice-to-Have criteria.
2. **Requirements Module:** Normalizing skills and criteria into immutable entities with unique identifiers and configurable weights.
3. **Candidates Module:** Managing candidate profiles, contact details, anonymized aliases, and pipeline status.
4. **Documents Module:** Ingesting raw uploaded resumes, performing file format validation, sanitizing text, and sectioning documents.
5. **Evidence Module:** Verifying candidate claims, enforcing verbatim substring citations, and classifying claims into strict taxonomy states.
6. **Scoring Module:** Purely deterministic, weighted mathematical calculation of fit scores. No LLM involvement in score calculation.
7. **Interview Intelligence Module:** Synthesizing targeted technical/behavioral interview questions conditioned on unmet criteria, and extracting evidence from post-interview notes.
8. **Human Overrides Module:** Enabling recruiters to override AI-generated statuses and criteria weights with mandatory justification logging.
9. **Audit Events Module:** Append-only, tamper-evident log capturing all system and human decisions with provenance metadata.
10. **Security Module:** Multi-rule detection of indirect prompt injection, adversarial payloads, and malicious file inputs.
11. **AI Providers Module:** Provider-agnostic adapters for Google Gemini, Groq Cloud, and Offline Fallback.
12. **Evaluation Module:** Automated validation harness measuring schema validity, citation accuracy, injection detection recall, and scoring reproducibility.

---

## 4. Database Schema Design (Normalized SQLite / PostgreSQL)

```sql
-- Core Role Requisition
CREATE TABLE roles (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    raw_jd_text TEXT NOT NULL,
    min_years_experience INTEGER DEFAULT 0,
    weight_must_have REAL DEFAULT 0.65,
    weight_nice_to_have REAL DEFAULT 0.20,
    weight_experience REAL DEFAULT 0.15,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Decomposed Requirements
CREATE TABLE requirements (
    id VARCHAR(36) PRIMARY KEY,
    role_id VARCHAR(36) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    category VARCHAR(32) NOT NULL, -- 'MUST_HAVE' | 'NICE_TO_HAVE'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    weight REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_req_role ON requirements(role_id);

-- Candidates
CREATE TABLE candidates (
    id VARCHAR(36) PRIMARY KEY,
    role_id VARCHAR(36) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(64),
    anonymous_alias VARCHAR(64) NOT NULL, -- e.g. 'Candidate #101'
    years_experience REAL DEFAULT 0,
    quarantined BOOLEAN DEFAULT FALSE,
    quarantine_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_cand_role ON candidates(role_id);

-- Candidate Documents
CREATE TABLE candidate_documents (
    id VARCHAR(36) PRIMARY KEY,
    candidate_id VARCHAR(36) NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(16) NOT NULL, -- 'PDF' | 'DOCX' | 'TXT'
    raw_text TEXT NOT NULL,
    sanitized_text TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Evidence Claims (Grounded Provenance)
CREATE TABLE evidence_claims (
    id VARCHAR(36) PRIMARY KEY,
    candidate_id VARCHAR(36) NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    requirement_id VARCHAR(36) NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    source_document_id VARCHAR(36) REFERENCES candidate_documents(id),
    source_type VARCHAR(32) NOT NULL, -- 'RESUME' | 'INTERVIEW_NOTE'
    section_reference VARCHAR(255),
    verbatim_quote TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    status VARCHAR(32) NOT NULL, -- 'PROVEN' | 'PARTIALLY_PROVEN' | 'UNVERIFIED' | 'CONTRADICTED' | 'NOT_FOUND'
    reasoning TEXT,
    confidence REAL DEFAULT 1.0,
    is_human_overridden BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_evidence_cand_req ON evidence_claims(candidate_id, requirement_id);

-- Interview Sessions & Questions
CREATE TABLE interview_sessions (
    id VARCHAR(36) PRIMARY KEY,
    candidate_id VARCHAR(36) NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    interviewer_name VARCHAR(255),
    interview_round VARCHAR(64) DEFAULT 'TECHNICAL_SCREEN',
    raw_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Score Snapshots (Deterministic Reproducibility)
CREATE TABLE score_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    candidate_id VARCHAR(36) NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    must_have_score REAL NOT NULL,
    nice_to_have_score REAL NOT NULL,
    experience_score REAL NOT NULL,
    formula_representation TEXT NOT NULL,
    breakdown_json TEXT NOT NULL,
    calculation_version VARCHAR(16) DEFAULT 'v1.0',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Append-Only Audit Trail
CREATE TABLE audit_events (
    id VARCHAR(36) PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    actor VARCHAR(64) NOT NULL, -- 'SYSTEM_AGENT' | 'RECRUITER'
    action VARCHAR(64) NOT NULL, -- 'INGEST' | 'CLASSIFY' | 'OVERRIDE' | 'RECALCULATE'
    details_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);
```

---

## 5. State Model & Transitions

Evidence claims move through controlled states strictly validated by the domain reconciliation service:

```
[ NOT_FOUND_IN_PROVIDED_MATERIAL ]
            │
            ▼
    [ UNVERIFIED ]  (Keyword listed without project context)
            │
            ├──► [ PARTIALLY_PROVEN ] (Contextual mention lacking scale/outcomes)
            │           │
            │           ▼
            └──► [ PROVEN ] (Explicit hands-on verification with verbatim quote)
                     │
                     ▼
             [ CONTRADICTED ] (Explicit factual conflict in documents)
```

* **Human Override Transition:** A recruiter can transition any status with mandatory audit logging.
* **Interview Evidence Reconciliation:** Validated answers in interview notes transition `UNVERIFIED` -> `PROVEN`.

---

## 6. Deterministic Fit Scoring Formulation

$$\text{Final Fit Score} = \left( S_{\text{must}} \times W_{\text{must}} + S_{\text{nice}} \times W_{\text{nice}} + S_{\text{exp}} \times W_{\text{exp}} \right) \times 100$$

* Status point map:
  * `PROVEN`: $1.0$
  * `PARTIALLY_PROVEN`: $0.5$
  * `UNVERIFIED`: $0.0$
  * `NOT_FOUND`: $0.0$
  * `CONTRADICTED`: $-0.5$
* Pure mathematical execution in `ScoringService`. Zero LLM math. Fully auditable and reproducible.

---

## 7. AI Provider Abstraction & Fallback Engine

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Type[BaseModel], system_instruction: Optional[str] = None) -> ProviderResponse:
        pass

    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        pass
```

* **Live Mode:** Integrates Google Gemini Flash or Groq Cloud via structured JSON output.
* **Offline Fallback:** `OfflineFallbackProvider` operates 100% deterministically using rule-based keyword/regex extraction. It is explicitly labeled in metadata as `is_fallback: True` and never disguised as live AI.

---

## 8. Security & Privacy Architecture

1. **Prompt Injection Quarantine:** Document sanitizer scans candidate text for system prompt prefixes, role overrides, and delimiter hijacking before model processing. Adversarial resumes are quarantined with status `quarantined: True`.
2. **Anti-Bias Blind Screening:** Presentation-layer transformation masking candidate names, emails, phones, photos, and graduation dates to prevent demographic bias during initial screening.
3. **Safe Document Ingestion:** Whitelist file extensions (`.pdf`, `.docx`, `.txt`), sanitize filenames, isolate extracted text from system instructions, and enforce size limits (10MB max).

---

## 9. Premium Recruiter Cockpit UI Architecture & Information Hierarchy

The Phase 5 frontend represents a complete recruiter workstation optimized for 1280px+ desktop/laptop displays with high visual density, zero horizontal truncation, and an immediate visual hierarchy communicating trust in under 15 seconds:

$$\text{Evidence} \longrightarrow \text{Explainability} \longrightarrow \text{Candidate Comparison} \longrightarrow \text{Interview Intelligence} \longrightarrow \text{Human Control} \longrightarrow \text{Auditability}$$

### Tab 1: Requisition Studio (`RequisitionStudio.tsx`)
- **Criteria & Formula Management:** Clear separation of `MUST_HAVE` and `NICE_TO_HAVE` requirements with relative weights.
- **Formula Inspector (`FormulaInspector.tsx`):** Renders the exact mathematical fit formula with interactive score weights and point value reference tables, demystifying the deterministic engine for evaluators.

### Tab 2: Candidate Comparison Matrix (`CandidateMatrix.tsx`)
- **Pre-computed Candidate $\times$ Requirements Grid:** High-density table fetched via `GET /api/v1/roles/{role_id}/matrix`.
- **Status Pills:** Instant color-coded badges (`PROVEN`, `PARTIALLY_PROVEN`, `UNVERIFIED`, `CONTRADICTED`, `NOT_FOUND`).
- **Interactive Deep-Links:** Clicking any cell immediately loads the candidate and selects the target criterion in the Dual-Pane Evidence Studio.
- **Direct Resume Ingestion:** Ingest PDF/DOCX/TXT resumes with security scan feedback and automatic matrix refresh.

### Tab 3: Dual-Pane Evidence Studio (`EvidenceStudio.tsx`)
- **Left Pane:** Categorized requirements and claims with recruiter override modal triggers, competency gap cockpit with urgency ratings (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Right Pane:** Source Document Inspector showing raw text excerpts, highlighted citations, verified start/end byte offsets, file hash checksums, and provenance confirmation badges.

### Tab 4: Interview Intelligence Cockpit (`InterviewCockpit.tsx`)
- **Gap-Targeted Questions:** Probes linked to specific unverified requirements, with expected positive signals and red flags.
- **Live Recruiter Notes Editor:** Real-time notes debrief with 3 `[SYNTHETIC DEMO FIXTURE]` prefill buttons for instant testing.
- **AI Proposal Confirmation Gate:** Human recruiter review gate requiring explicit approval or override before candidate score updates.
- **Dynamic Reassessment Banner:** Real-time score delta banner showing before/after score changes and remaining gaps count.

### Tab 5: Audit & Security Center (`AuditSecurityStudio.tsx`)
- **Chronological Audit Ledger:** Complete history from `GET /api/v1/candidates/{candidate_id}/audit-trail` with actor badges (`HUMAN RECRUITER` vs `SYSTEM AGENT`), formatted action types, and expandable JSON details.
- **Security & Trust Center:** Cards validating Prompt Injection Defense, 0-LLM Quarantine Guarantee, PII Masking preview, and Deterministic Quote Verification.

