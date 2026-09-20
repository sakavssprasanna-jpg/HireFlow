import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.base import Base, get_db
from backend.app.db.models import (
    RoleModel,
    RequirementModel,
    CandidateModel,
    CandidateDocumentModel,
    EvidenceClaimModel
)
from backend.app.domain.enums import EvidenceStatus, RequirementCategory, AIMode, SourceType
from backend.app.domain.schemas import (
    RoleCreate,
    RequirementCreate,
    CandidateBase,
    EvidenceClaimBase,
    FitScoreBreakdown,
    JDAnalysisOutput,
    HealthCheckResponse
)
from backend.app.ai.offline_fallback import OfflineFallbackProvider

# In-memory test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()

def test_pydantic_schemas_instantiation():
    """Verify that core domain Pydantic schemas instantiate correctly with valid inputs."""
    role = RoleCreate(
        title="Senior Cloud Engineer",
        department="Platform",
        raw_jd_text="Requirements: 4+ years Terraform, Kubernetes.",
        min_years_experience=4
    )
    assert role.title == "Senior Cloud Engineer"
    assert role.weight_must_have == 0.65

    req = RequirementCreate(
        name="Terraform",
        category=RequirementCategory.MUST_HAVE,
        weight=1.0
    )
    assert req.name == "Terraform"
    assert req.category == RequirementCategory.MUST_HAVE

    claim = EvidenceClaimBase(
        requirement_id="req-123",
        status=EvidenceStatus.PROVEN,
        verbatim_quote="Architected Terraform pipelines.",
        confidence=0.95,
        start_offset=120,
        end_offset=155
    )
    assert claim.status == EvidenceStatus.PROVEN
    assert claim.verbatim_quote is not None
    assert claim.start_offset == 120

def test_pydantic_validation_rejections():
    """Verify that Pydantic schemas strictly reject invalid inputs."""
    # 1. Empty name should raise ValidationError
    with pytest.raises(ValidationError):
        RequirementCreate(name="", category=RequirementCategory.MUST_HAVE)

    # 2. Negative weight should raise ValidationError
    with pytest.raises(ValidationError):
        RequirementCreate(name="Kubernetes", weight=-0.5)

    # 3. Excessive weight (> 5.0) should raise ValidationError
    with pytest.raises(ValidationError):
        RequirementCreate(name="Kubernetes", weight=6.0)

    # 4. Out-of-bounds confidence (> 1.0) should raise ValidationError
    with pytest.raises(ValidationError):
        EvidenceClaimBase(
            requirement_id="req-1",
            status=EvidenceStatus.PROVEN,
            confidence=1.5
        )

    # 5. Negative confidence (< 0.0) should raise ValidationError
    with pytest.raises(ValidationError):
        EvidenceClaimBase(
            requirement_id="req-1",
            status=EvidenceStatus.PROVEN,
            confidence=-0.1
        )

    # 6. Negative character offset should raise ValidationError
    with pytest.raises(ValidationError):
        EvidenceClaimBase(
            requirement_id="req-1",
            status=EvidenceStatus.PROVEN,
            start_offset=-10
        )

    # 7. Invalid enum status should raise ValidationError
    with pytest.raises(ValidationError):
        EvidenceClaimBase(
            requirement_id="req-1",
            status="TOTALLY_FABRICATED_STATUS"  # type: ignore
        )

def test_database_all_tables_and_relationships():
    """Verify that all 9 ORM models can be persisted and related in SQLite cleanly."""
    db = TestingSessionLocal()
    try:
        # Create role
        role = RoleModel(
            title="DevOps Architect",
            department="Infrastructure",
            raw_jd_text="Senior DevOps Architect with AWS and Kubernetes experience."
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        assert role.id is not None

        # Create requirement
        req = RequirementModel(
            role_id=role.id,
            category=RequirementCategory.MUST_HAVE.value,
            name="AWS Cloud",
            weight=1.0
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        assert req.id is not None

        # Create candidate
        candidate = CandidateModel(
            role_id=role.id,
            full_name="Jane Doe",
            email="jane@example.com",
            anonymous_alias="Candidate #101",
            years_experience=5.0
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        assert candidate.id is not None

        # Create evidence claim referencing candidate & requirement
        claim = EvidenceClaimModel(
            candidate_id=candidate.id,
            requirement_id=req.id,
            source_type=SourceType.RESUME.value,
            verbatim_quote="5 years deploying production AWS ECS clusters.",
            status=EvidenceStatus.PROVEN.value,
            confidence=0.95
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)
        assert claim.id is not None
        assert claim.candidate_id == candidate.id
        assert claim.requirement_id == req.id

        # Verify relationship traversals
        assert len(role.requirements) == 1
        assert role.requirements[0].name == "AWS Cloud"
        assert len(candidate.evidence_claims) == 1
        assert candidate.evidence_claims[0].status == EvidenceStatus.PROVEN.value
    finally:
        db.close()

def test_fastapi_health_endpoint():
    """Verify that FastAPI health check endpoint returns 200 and valid schema."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert data["database_connected"] is True
    assert data["ai_mode"] in [mode.value for mode in AIMode]

@pytest.mark.asyncio
async def test_offline_fallback_provider():
    """Verify that OfflineFallbackProvider implements BaseLLMProvider without crashing."""
    provider = OfflineFallbackProvider()
    metadata = provider.get_metadata()
    assert metadata.is_fallback is True
    assert metadata.ai_mode == AIMode.OFFLINE_FALLBACK

    prompt = "Senior DevOps Engineer. Must have: Python, Kubernetes, Terraform."
    response = await provider.generate_structured(prompt=prompt, schema=JDAnalysisOutput)
    
    assert response.metadata.is_fallback is True
    assert isinstance(response.data, JDAnalysisOutput)
    assert len(response.data.requirements) > 0
    assert any(r.name.startswith("Kubernetes") for r in response.data.requirements)
