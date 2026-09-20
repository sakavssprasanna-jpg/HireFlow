# HireFlow — Technical Judge & Evaluator FAQ

This document addresses key architectural, technical, and security questions commonly asked by hackathon judges and evaluators.

---

### 1. Why not let the LLM calculate the candidate score?

**Answer:**  
Because numerical candidate scoring must be deterministic, mathematically explainable, auditable, and free from stochastic model drift. 

In HireFlow:
- **LLMs reason and extract**: They identify structured factual claims from resume text and interview transcripts.
- **Pure Python calculates**: The deterministic scoring engine applies a published weighted formula:
  $$\text{Final Fit} = (S_{\text{must}} \times W_{\text{must}} + S_{\text{nice}} \times W_{\text{nice}} + S_{\text{exp}} \times W_{\text{exp}}) \times 100$$
- Across 50 repeated evaluations of the same evidence profile, HireFlow achieved a measured variance of **$\sigma^2 = 0.0$**. An LLM cannot guarantee mathematical reproducibility or defend its numerical calculations in a formal audit.

---

### 2. How do you prevent hallucinated resume evidence?

**Answer:**  
Through the deterministic **`QuoteVerifier`** service. 

When an AI provider extracts an evidence claim with a supporting citation quote, the system conducts a strict substring search against the raw, unmodified candidate document text:
1. The quote must match the text exactly (with normalized whitespace and typographical punctuation).
2. The verifier calculates exact character offsets (`start_offset`, `end_offset`) anchoring the quote to the document.
3. If an LLM fabricates a quote, paraphrases text without verbatim grounding, or references text from another candidate, the citation is immediately blocked.
4. In our evaluation harness, the hallucination block rate was **100.0%** (5/5 fabricated/cross-candidate claims blocked).

---

### 3. What happens if the resume contains prompt injection?

**Answer:**  
The candidate document is evaluated by the **`SecurityScanner`** pre-processor *before* any downstream AI service is invoked.

The scanner evaluates the text for:
- Role hijacking patterns (`[SYSTEM: ...]`, `<|im_start|>`, `system:`)
- Instruction overrides (`IGNORE PREVIOUS INSTRUCTIONS`)
- Recruiter score tampering (`set score to 100%`)
- Zero-width character obfuscation (`\u200B`, `\u00AD`) used to split adversarial tokens

If high-severity indicators are detected, the document is immediately assigned a `QUARANTINED` status. Under the **0-LLM Quarantine Invariant**, zero LLM calls are executed, zero evidence claims are processed, and zero scores are computed. The document is safely isolated.

---

### 4. Can AI override a recruiter?

**Answer:**  
**No.** Never.

Under HireFlow's architecture, AI systems produce *intelligence* and *proposals*, not authoritative decisions. The system enforces the **Human Confirmation Gate Invariant**:
- Evidence extracted by an LLM from interview notes remains in a `PENDING_REVIEW` proposal state.
- Proposals have zero mathematical effect on candidate scores or competency gaps until a human recruiter explicitly approves, modifies, or rejects them.

---

### 5. Can the recruiter override AI evidence?

**Answer:**  
**Yes.** Recruiters retain complete operational authority.

A recruiter can manually override any evidence claim status (e.g., changing `NOT_FOUND` to `PROVEN`, or `PROVEN` to `CONTRADICTED`). To maintain organizational accountability:
1. The override requires a non-empty, mandatory **justification string**.
2. The override triggers an immediate deterministic recalculation of candidate fit scores.
3. The override is permanently recorded in the immutable audit ledger with the recruiter's actor attribution, prior status, new status, and written rationale.

---

### 6. What happens when the model/API fails?

**Answer:**  
HireFlow includes a fault-tolerant **`ProviderFactory`** and a built-in **`OfflineFallbackProvider`**:
1. If a cloud API key is missing, network latency times out, or the remote endpoint returns an HTTP 429 / 500 error, the factory seamlessly switches to the offline engine.
2. The offline engine executes deterministic rule-based extractions from candidate text.
3. Critically, the offline provider returns `is_fallback=True` in its metadata. The UI header immediately reflects `OFFLINE_FALLBACK`, maintaining 100% honesty about the origin of the intelligence rather than masquerading as a live model.

---

### 7. Did you test the live Gemini/Groq APIs?

**Answer:**  
**Live cloud-provider execution was not verified in the final local evaluation environment. The provider abstraction and offline fallback were verified.**

Both the Google Gemini provider (via the `google-genai` SDK) and the Groq provider (via `httpx` async OpenAI-compatible REST) are implemented and unit-tested for schema conformism. However, because live API keys are deliberately omitted from the submission repository for security, the system operates under the fully verified `OfflineFallbackEngine`.

---

### 8. Does HireFlow guarantee unbiased hiring?

**Answer:**  
**No.** No algorithmic system can guarantee bias-free hiring.

What HireFlow provides is a suite of rigorous engineering controls designed to mitigate common sources of bias:
- **Anti-Bias Blind Mode**: Strips candidate names, email addresses, and phone numbers, displaying candidates with anonymized hashes (e.g., `Candidate 6fd3`).
- **Evidence-First Scoring**: Scores reflect only verified skills and requirements from the job requisition, eliminating subjective or demographic evaluations.
- **Auditable Accountability**: Every assessment, approval, and override is permanently logged, allowing compliance teams to review recruiter decisions for disparate impact.

---

### 9. Does it support scanned PDFs?

**Answer:**  
**Not currently without OCR.**

`DocumentParser` supports native text-layer PDFs via `pypdf`, DOCX files via `python-docx`, and plain text files. Scanned image-only PDFs that lack a text layer explicitly raise:
```text
DocumentParsingError: Scanned image PDFs are not supported without OCR
```
Optical Character Recognition (OCR) engines like Tesseract were deliberately excluded to maintain a lightweight, cross-platform installation footprint without external C-binary dependencies.

---

### 10. Is the audit log cryptographically tamper-proof?

**Answer:**  
**No.**

The audit trail is stored in SQLite (`audit_events` table) with timestamps, actor roles (`RECRUITER` vs `SYSTEM_AGENT`), event types, and structured JSON payloads. While the application enforces append-only semantics, cryptographic hash-chaining (such as Merkle trees or blockchain-style hashing where row $N$ contains the SHA-256 hash of row $N-1$) is not implemented in the current persistence layer.
