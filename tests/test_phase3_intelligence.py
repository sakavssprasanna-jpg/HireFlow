import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.base import Base, get_db
from backend.app.db.models import (
    RoleModel,
    RequirementModel,
    CandidateModel,
    CandidateDocumentModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    AuditEventModel
)
from backend.app.domain.enums import (
    RequirementCategory,
    EvidenceStatus,
    GapPriority,
    AIMode,
    AuditAction,
    AuditActor
)
from backend.app.services.gap_detector import GapDetector
from backend.app.services.ai_evidence_service import AIEvidenceService
from backend.app.services.interview_generator import InterviewGeneratorService
from backend.app.services.scoring_engine import DeterministicScoringEngine
from backend.app.ai.factory import get_llm_provider
from backend.app.ai.base import BaseLLMProvider, ProviderMetadata, ProviderResponse
from backend.app.domain.schemas import (
    EvidenceMatchingOutput,
    ExtractedCandidateClaim,
    InterviewQuestionOutput,
    GeneratedQuestion
)

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_gap_detector_priority_ordering(db_session):
    """
    Verify deterministic gap detection logic and priority sorting:
    CRITICAL: MUST_HAVE + (NOT_FOUND | UNVERIFIED | CONTRADICTED)
    HIGH:     MUST_HAVE + PARTIALLY_PROVEN
    MEDIUM:   NICE_TO_HAVE + (NOT_FOUND | UNVERIFIED | CONTRADICTED)
    LOW:      NICE_TO_HAVE + PARTIALLY_PROVEN
    PROVEN items are not gaps.
    """
    req1 = RequirementModel(id="req-1", role_id="role-1", name="Python", category=RequirementCategory.MUST_HAVE.value, weight=1.0)
    req2 = RequirementModel(id="req-2", role_id="role-1", name="FastAPI", category=RequirementCategory.MUST_HAVE.value, weight=1.0)
    req3 = RequirementModel(id="req-3", role_id="role-1", name="Docker", category=RequirementCategory.MUST_HAVE.value, weight=1.0)
    req4 = RequirementModel(id="req-4", role_id="role-1", name="Redis", category=RequirementCategory.NICE_TO_HAVE.value, weight=1.0)
    req5 = RequirementModel(id="req-5", role_id="role-1", name="GraphQL", category=RequirementCategory.NICE_TO_HAVE.value, weight=1.0)
    req6 = RequirementModel(id="req-6", role_id="role-1", name="Git", category=RequirementCategory.MUST_HAVE.value, weight=1.0)

    claims = {
        "req-1": EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL,  # -> CRITICAL
        "req-2": EvidenceStatus.PARTIALLY_PROVEN,                # -> HIGH
        "req-3": EvidenceStatus.UNVERIFIED,                      # -> CRITICAL
        "req-4": EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL,  # -> MEDIUM
        "req-5": EvidenceStatus.PARTIALLY_PROVEN,                # -> LOW
        "req-6": EvidenceStatus.PROVEN,                          # -> NOT A GAP
    }

    gaps = GapDetector.detect_gaps(requirements=[req1, req2, req3, req4, req5, req6], claims=claims)

    assert len(gaps) == 5  # req-6 is PROVEN, so omitted
    # Verify priority sorting: CRITICAL items first
    priorities = [g.priority for g in gaps]
    assert priorities[0] == GapPriority.CRITICAL
    assert priorities[1] == GapPriority.CRITICAL
    assert priorities[2] == GapPriority.HIGH
    assert priorities[3] == GapPriority.MEDIUM
    assert priorities[4] == GapPriority.LOW

    response = GapDetector.build_response("cand-1", gaps)
    assert response.total_gaps == 5
    assert response.critical_count == 2
    assert response.high_count == 1
    assert response.medium_count == 1
    assert response.low_count == 1


@pytest.mark.asyncio
async def test_quote_verification_gating_hallucination_prevention(db_session, monkeypatch):
    """
    CRITICAL ANTI-HALLUCINATION INVARIANT:
    If an AI model proposes a positive evidence claim with an invented citation,
    the deterministic QuoteVerifier must reject the citation and force status to UNVERIFIED.
    """
    # 1. Setup Role and Requirements
    role = RoleModel(
        id="role-test",
        title="Senior Python Engineer",
        raw_jd_text="Must have Python programming and Kubernetes.",
        weight_must_have=0.65,
        weight_nice_to_have=0.20,
        weight_experience=0.15
    )
    req1 = RequirementModel(id="req-py", role_id="role-test", name="Python Programming", category="MUST_HAVE", weight=1.0)
    db_session.add_all([role, req1])
    db_session.flush()

    # 2. Setup Candidate with real resume text
    real_resume = "Software developer with 5 years building scalable web applications. Skilled in Python and Django."
    candidate = CandidateModel(
        id="cand-hallucinate",
        role_id="role-test",
        full_name="Alex River",
        anonymous_alias="Candidate #201",
        quarantined=False
    )
    doc = CandidateDocumentModel(
        id="doc-test",
        candidate_id="cand-hallucinate",
        filename="resume.txt",
        file_type="txt",
        raw_text=real_resume,
        sanitized_text=real_resume,
        file_hash="hash123"
    )
    db_session.add_all([candidate, doc])
    db_session.commit()

    # 3. Create a Mock Provider that hallucinates a quote NOT in the resume
    class HallucinatingProvider(BaseLLMProvider):
        def get_metadata(self):
            return ProviderMetadata(provider_name="MockLLM", model_name="hallucinator-v1", ai_mode=AIMode.OFFLINE_FALLBACK)

        async def generate_structured(self, prompt, schema, system_instruction=None):
            return ProviderResponse(
                data=EvidenceMatchingOutput(
                    candidate_name="Alex River",
                    years_experience=5.0,
                    claims=[
                        ExtractedCandidateClaim(
                            requirement_name="Python Programming",
                            status=EvidenceStatus.PROVEN,
                            verbatim_quote="Invented statement: Alex architected the Python compiler from scratch at Google.",
                            section_reference="Experience",
                            reasoning="Claimed deep mastery.",
                            confidence=0.99
                        )
                    ]
                ),
                metadata=self.get_metadata()
            )

    monkeypatch.setattr("backend.app.services.ai_evidence_service.get_llm_provider", lambda mode=None: HallucinatingProvider())

    # 4. Run AI Evidence Service
    result = await AIEvidenceService.analyze_candidate_evidence(db=db_session, candidate_id="cand-hallucinate")

    # 5. Verify hallucination was prevented: status forced to UNVERIFIED
    claim = db_session.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == "cand-hallucinate").first()
    assert claim is not None
    assert claim.status == EvidenceStatus.UNVERIFIED.value
    assert "UNVERIFIED_HALLUCINATION_PREVENTED" in claim.reasoning
    assert result.unverified_count == 1
    assert result.proven_count == 0


@pytest.mark.asyncio
async def test_quote_verification_accepts_valid_quote(db_session, monkeypatch):
    """
    When an AI model cites an authentic quote from the candidate's resume,
    the deterministic QuoteVerifier validates it, preserves PROVEN status, and records exact offsets.
    """
    role = RoleModel(id="role-valid", title="DevOps Engineer", raw_jd_text="Kubernetes required.")
    req = RequirementModel(id="req-k8s", role_id="role-valid", name="Kubernetes", category="MUST_HAVE", weight=1.0)
    candidate = CandidateModel(id="cand-valid", role_id="role-valid", full_name="Jordan Lee", anonymous_alias="Candidate #202")
    
    source_text = "Managed 15 production Kubernetes clusters across AWS and GCP with 99.99% uptime."
    doc = CandidateDocumentModel(
        id="doc-valid",
        candidate_id="cand-valid",
        filename="resume.txt",
        file_type="txt",
        raw_text=source_text,
        sanitized_text=source_text,
        file_hash="hash456"
    )
    db_session.add_all([role, req, candidate, doc])
    db_session.commit()

    class AccurateProvider(BaseLLMProvider):
        def get_metadata(self):
            return ProviderMetadata(provider_name="MockLLM", model_name="accurate-v1", ai_mode=AIMode.OFFLINE_FALLBACK)

        async def generate_structured(self, prompt, schema, system_instruction=None):
            return ProviderResponse(
                data=EvidenceMatchingOutput(
                    candidate_name="Jordan Lee",
                    years_experience=4.0,
                    claims=[
                        ExtractedCandidateClaim(
                            requirement_name="Kubernetes",
                            status=EvidenceStatus.PROVEN,
                            verbatim_quote="Managed 15 production Kubernetes clusters across AWS and GCP with 99.99% uptime.",
                            section_reference="Experience",
                            reasoning="Direct verified production cluster management experience.",
                            confidence=0.95
                        )
                    ]
                ),
                metadata=self.get_metadata()
            )

    monkeypatch.setattr("backend.app.services.ai_evidence_service.get_llm_provider", lambda mode=None: AccurateProvider())

    result = await AIEvidenceService.analyze_candidate_evidence(db=db_session, candidate_id="cand-valid")

    claim = db_session.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == "cand-valid").first()
    assert claim.status == EvidenceStatus.PROVEN.value
    assert claim.start_offset == 0
    assert claim.end_offset == len(source_text)
    assert result.proven_count == 1
    assert result.unverified_count == 0


@pytest.mark.asyncio
async def test_security_invariant_quarantined_candidate_zero_llm_calls(db_session, monkeypatch):
    """
    STRICT SECURITY INVARIANT:
    If a candidate document was quarantined during ingestion, all subsequent AI operations
    (evidence matching and interview generation) must be rejected with HTTP 403,
    guaranteeing ZERO calls to any LLM.
    """
    from fastapi import HTTPException

    role = RoleModel(id="role-sec", title="Engineer", raw_jd_text="Engineering role")
    candidate = CandidateModel(
        id="cand-quarantined",
        role_id="role-sec",
        full_name="Attacker",
        anonymous_alias="Candidate #999",
        quarantined=True,
        quarantine_reason="Prompt injection payload detected"
    )
    db_session.add_all([role, candidate])
    db_session.commit()

    llm_invoked = False
    class TrapProvider(BaseLLMProvider):
        def get_metadata(self):
            return ProviderMetadata(provider_name="Trap", model_name="trap", ai_mode=AIMode.OFFLINE_FALLBACK)
        async def generate_structured(self, *args, **kwargs):
            nonlocal llm_invoked
            llm_invoked = True
            raise AssertionError("SECURITY BREACH: LLM was invoked on a quarantined candidate!")

    monkeypatch.setattr("backend.app.services.ai_evidence_service.get_llm_provider", lambda mode=None: TrapProvider())
    monkeypatch.setattr("backend.app.services.interview_generator.get_llm_provider", lambda mode=None: TrapProvider())

    # 1. Attempt Evidence Analysis -> Expect 403
    with pytest.raises(HTTPException) as exc_info:
        await AIEvidenceService.analyze_candidate_evidence(db=db_session, candidate_id="cand-quarantined")
    assert exc_info.value.status_code == 403
    assert not llm_invoked

    # 2. Attempt Interview Generation -> Expect 403
    with pytest.raises(HTTPException) as exc_info:
        await InterviewGeneratorService.generate_interview_questions(db=db_session, candidate_id="cand-quarantined")
    assert exc_info.value.status_code == 403
    assert not llm_invoked


@pytest.mark.asyncio
async def test_interview_question_grounding_invariant(db_session):
    """
    GROUNDING INVARIANT:
    Every interview question generated by the AI agent must ground directly to a valid role requirement.
    No orphaned questions are permitted.
    """
    role = RoleModel(id="role-ground", title="Backend Engineer", raw_jd_text="Python and AWS")
    req_py = RequirementModel(id="req-py-1", role_id="role-ground", name="Python", category="MUST_HAVE")
    req_aws = RequirementModel(id="req-aws-1", role_id="role-ground", name="AWS", category="MUST_HAVE")
    candidate = CandidateModel(id="cand-ground", role_id="role-ground", full_name="Taylor Smith", anonymous_alias="Candidate #203")
    doc = CandidateDocumentModel(
        id="doc-ground",
        candidate_id="cand-ground",
        filename="resume.txt",
        file_type="txt",
        raw_text="Experienced in Python scripting.",
        sanitized_text="Experienced in Python scripting.",
        file_hash="hash789"
    )
    # AWS is missing (gap!)
    claim_py = EvidenceClaimModel(
        candidate_id="cand-ground",
        requirement_id=req_py.id,
        status=EvidenceStatus.PROVEN.value,
        verbatim_quote="Experienced in Python scripting."
    )
    claim_aws = EvidenceClaimModel(
        candidate_id="cand-ground",
        requirement_id=req_aws.id,
        status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL.value
    )
    db_session.add_all([role, req_py, req_aws, candidate, doc, claim_py, claim_aws])
    db_session.commit()

    # Generate questions using the offline generator
    session = await InterviewGeneratorService.generate_interview_questions(
        db=db_session,
        candidate_id="cand-ground",
        ai_mode=AIMode.OFFLINE_FALLBACK,
        max_questions=3
    )

    assert len(session.questions) > 0
    valid_req_ids = {req_py.id, req_aws.id}
    for q in session.questions:
        # INVARIANT: requirement_id must NOT be null and must belong to this role
        assert q.requirement_id is not None
        assert q.requirement_id in valid_req_ids
        assert len(q.question_text) > 10
        assert q.probing_context is not None


def test_recruiter_override_updates_score_and_audit(client, db_session):
    """
    Verify recruiter override workflow:
    - Recruiter modifies claim status with mandatory justification reason.
    - System marks is_human_overridden = True.
    - Fit score is recalculation immediately.
    - Immutable audit event is logged with actor=RECRUITER.
    """
    # 1. Setup Role and Candidate with NOT_FOUND claim
    role = RoleModel(
        id="role-override",
        title="Full Stack Engineer",
        raw_jd_text="Python required",
        weight_must_have=1.0,
        weight_nice_to_have=0.0,
        weight_experience=0.0
    )
    req = RequirementModel(id="req-over-1", role_id="role-override", name="Python", category="MUST_HAVE", weight=1.0)
    candidate = CandidateModel(id="cand-override", role_id="role-override", full_name="Morgan Blue", anonymous_alias="Candidate #204")
    claim = EvidenceClaimModel(
        id="claim-over-1",
        candidate_id="cand-override",
        requirement_id="req-over-1",
        status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL.value,
        is_human_overridden=False
    )
    db_session.add_all([role, req, candidate, claim])
    db_session.commit()

    # 2. Send override request
    override_payload = {
        "candidate_id": "cand-override",
        "evidence_id": "claim-over-1",
        "new_status": "PROVEN",
        "override_reason": "Candidate demonstrated hands-on Python live coding during the screen."
    }
    resp = client.post(f"/api/v1/candidates/cand-override/evidence/claim-over-1/override", json=override_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["evidence_claim"]["status"] == "PROVEN"
    assert data["evidence_claim"]["is_human_overridden"] is True
    assert data["evidence_claim"]["override_reason"] == override_payload["override_reason"]
    assert data["fit_score"]["overall_score"] == 100.0  # Was 0.0, now 100.0

    # 3. Verify Audit Event
    audit = db_session.query(AuditEventModel).filter(AuditEventModel.action == AuditAction.RECRUITER_OVERRIDE.value).first()
    assert audit is not None
    assert audit.actor == AuditActor.RECRUITER.value


def test_provider_factory_fallback_on_missing_api_keys(monkeypatch):
    """
    Verify AI provider factory gracefully falls back to OfflineFallbackProvider
    when live provider API keys are missing, ensuring zero crash during offline usage.
    """
    from backend.app.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    p_gemini = get_llm_provider(AIMode.LIVE_GEMINI)
    assert p_gemini.get_metadata().ai_mode == AIMode.OFFLINE_FALLBACK
    assert p_gemini.get_metadata().is_fallback is True

    p_groq = get_llm_provider(AIMode.LIVE_GROQ)
    assert p_groq.get_metadata().ai_mode == AIMode.OFFLINE_FALLBACK
    assert p_groq.get_metadata().is_fallback is True


def test_api_endpoints_phase3_workflow(client, db_session):
    """
    End-to-end API integration test covering:
    - Candidate upload
    - Evidence analysis trigger
    - Gaps retrieval
    - Interview question generation
    - Interview sessions retrieval
    """
    # 1. Create Role
    role_resp = client.post("/api/v1/roles/", json={
        "title": "Cloud Architect",
        "department": "Infrastructure",
        "raw_jd_text": "Must have Terraform and Kubernetes experience."
    })
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    # 1b. Add requirements to role
    req1_resp = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Kubernetes",
        "category": "MUST_HAVE",
        "description": "Container orchestration",
        "weight": 1.0
    })
    assert req1_resp.status_code == 201

    req2_resp = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Terraform",
        "category": "MUST_HAVE",
        "description": "Infrastructure as code",
        "weight": 1.0
    })
    assert req2_resp.status_code == 201

    # 2. Ingest clean candidate
    resume_text = "Experienced infrastructure engineer. Proficient in Kubernetes cluster management."
    upload_resp = client.post(
        "/api/v1/candidates/upload",
        data={"role_id": role_id, "candidate_name": "Sam Carter"},
        files={"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}
    )
    assert upload_resp.status_code == 201
    cand_id = upload_resp.json()["candidate"]["id"]

    # 3. Trigger AI Evidence Analysis
    analyze_resp = client.post(f"/api/v1/candidates/{cand_id}/evidence/analyze", json={"ai_mode": "OFFLINE_FALLBACK"})
    assert analyze_resp.status_code == 200
    analyze_data = analyze_resp.json()
    assert analyze_data["candidate_id"] == cand_id
    assert "fit_score" in analyze_data

    # 4. Retrieve Gaps
    gaps_resp = client.get(f"/api/v1/candidates/{cand_id}/gaps")
    assert gaps_resp.status_code == 200
    gaps_data = gaps_resp.json()
    assert "gaps" in gaps_data
    assert "critical_count" in gaps_data

    # 5. Generate Interview Questions
    gen_resp = client.post(f"/api/v1/candidates/{cand_id}/interview/questions/generate", json={
        "ai_mode": "OFFLINE_FALLBACK",
        "max_questions": 3
    })
    assert gen_resp.status_code == 201
    gen_data = gen_resp.json()
    assert len(gen_data["questions"]) > 0
    assert gen_data["questions"][0]["requirement_id"] is not None

    # 6. Retrieve Interview Sessions
    sessions_resp = client.get(f"/api/v1/candidates/{cand_id}/interview/sessions")
    assert sessions_resp.status_code == 200
    sessions_data = sessions_resp.json()
    assert len(sessions_data) >= 1
