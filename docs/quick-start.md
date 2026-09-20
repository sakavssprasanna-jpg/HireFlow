# HireFlow — Quick-Start Guide for Judges & Evaluators

This guide provides step-by-step instructions to run, evaluate, and verify the HireFlow application locally.

---

## 1. Prerequisites

- **Python**: Python 3.12+ (tested on Python 3.12.10 AMD64)
- **Node.js**: Node v18+ or v20+ or v22+ (tested on Node v22.12.0 with npm 10.9.0)
- **Operating System**: Windows, macOS, or Linux
- **Cloud API Keys**: **Optional**. HireFlow operates 100% locally out-of-the-box using its built-in `OfflineFallbackProvider`.

---

## 2. Environment Configuration

1. In the repository root, copy `.env.example` to `.env` (optional, default settings work without it):
   ```powershell
   Copy-Item .env.example .env
   ```

2. Configuration Settings Reference:
   | Variable | Default Value | Description |
   | :--- | :--- | :--- |
   | `PROJECT_NAME` | `"HireFlow"` | Application name |
   | `DEBUG` | `True` | Fast logging & diagnostic output |
   | `API_V1_PREFIX` | `"/api/v1"` | API endpoint prefix |
   | `DATABASE_URL` | `"sqlite:///./hireflow.db"` | Database connection string (SQLite default; PostgreSQL compatible) |
   | `DEFAULT_AI_MODE` | `"OFFLINE_FALLBACK"` | Default AI engine: `OFFLINE_FALLBACK`, `LIVE_GEMINI`, or `LIVE_GROQ` |
   | `GEMINI_API_KEY` | `""` | Optional Google Gemini API key |
   | `GROQ_API_KEY` | `""` | Optional Groq API key |
   | `CORS_ORIGINS` | `["http://localhost:5173", ...]` | Permitted frontend origins |

---

## 3. Backend Setup & Startup

From the project root directory:

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # On Linux/macOS: source .venv/bin/activate

# 2. Install backend dependencies
pip install -r backend/requirements.txt

# 3. Launch the FastAPI server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **API Documentation (Swagger UI)**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.
- **Health Check Endpoint**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 4. Frontend Setup & Startup

From a second terminal, navigate to the `frontend` directory:

```powershell
cd frontend

# 1. Install dependencies
npm install

# 2. Verify clean production build (0 TypeScript errors)
npm run build

# 3. Start development server
npm run dev
```

- **Recruiter Cockpit UI**: Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 5. Automated Verification Gate

To execute the complete test suite and adversarial evaluation harness:

```powershell
# From project root:

# 1. Run all 59 backend pytest unit, integration, and security tests
python -m pytest -v

# 2. Run the automated 8-section Evaluation & Adversarial Hardening Harness
python tests/eval_harness.py
```

### Expected Output Summary:
- **Pytest**: `59 passed, 1 warning in ~4.0s`
- **Evaluation Harness**:
  - Valid Schema Acceptance: 100.0%
  - Malformed Input Rejection: 10/10 (100.0%)
  - Hallucination Block Rate: 5/5 (100.0%)
  - Scoring Variance: $\sigma^2 = 0.0$ across 50 repetitions
  - Prompt Injection Quarantined: 20/20 (100.0% Recall)
  - Benign Controls Preserved: 7/7 (100.0% Precision)
  - Security Invariants Enforced: 6/6
  - Document Edge Cases Handled: 10/10

---

## 6. Navigating the Judge Demo Flow

Once both the backend (port 8000) and frontend (port 5173) are running:

1. **Requisition Studio (`01 Requisition`)**:
   - Inspect the active job requisition: *Senior Cloud & Platform Engineer*.
   - Review the Must-Have criteria (Kubernetes, AWS, Terraform, CI/CD) and Nice-to-Have criteria (Go, Prometheus).
   - Inspect the **Formula Inspector** to see the exact deterministic math calculating fit scores.

2. **Candidate Matrix (`02 Candidates`)**:
   - Compare candidates side-by-side against all requirements.
   - Toggle **Anti-Bias Blind Mode** in the header to view anonymous candidate identifiers.
   - Observe the **Adversarial Candidate** quarantined with zero LLM execution.

3. **Evidence Studio (`03 Evidence`)**:
   - Click into a candidate to view the dual-pane view:
     - **Left**: Extracted claims, verification statuses, confidence levels, and detected competency gaps.
     - **Right**: Raw parsed resume text with highlighted citation excerpts and character offsets.

4. **Interview Cockpit (`04 Interview`)**:
   - View targeted interview probes generated specifically from the candidate's unverified gaps.
   - Test debrief notes analysis using the provided synthetic fixture buttons.
   - Experience the **Human Recruiter Confirmation Gate**: observe that AI evidence proposals do not alter scores until the recruiter approves or overrides them.

5. **Audit & Security (`05 Audit & Security`)**:
   - Inspect the immutable chronological ledger of all actions with actor attribution (`RECRUITER` vs `SYSTEM_AGENT`).
   - Review enterprise security defense guarantees and PII masking status.
