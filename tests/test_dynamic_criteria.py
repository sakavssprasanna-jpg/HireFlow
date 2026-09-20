import pytest
import json
import io
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
from backend.app.domain.enums import EvidenceStatus, RequirementCategory, AuditAction

# In-memory test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
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

def create_sample_role(title="Platform Engineer"):
    res = client.post("/api/v1/roles", json={
        "title": title,
        "department": "Infrastructure",
        "raw_jd_text": "Production Kubernetes, Terraform, and AWS cloud management.",
        "min_years_experience": 4,
        "weight_must_have": 0.65,
        "weight_nice_to_have": 0.20,
        "weight_experience": 0.15
    })
    assert res.status_code == 201
    return res.json()

def upload_sample_candidate(role_id, name="Jordan Lee", resume_text=None):
    if resume_text is None:
        resume_text = (
            "Jordan Lee - Senior Cloud Engineer\n"
            "Over 6 years of experience managing production Kubernetes clusters.\n"
            "Automated multi-region infrastructure provisioning using Terraform.\n"
            "Designed and implemented high-availability AWS architecture."
        )
    file_bytes = resume_text.encode("utf-8")
    files = {
        "file": ("resume.txt", io.BytesIO(file_bytes), "text/plain")
    }
    data = {
        "role_id": role_id,
        "candidate_name": name
    }
    res = client.post("/api/v1/candidates/upload", data=data, files=files)
    assert res.status_code == 201
    return res.json()


# 1. ADD CRITERION TESTS
def test_add_criterion_success():
    """Verify adding a valid criterion to a role works and persists."""
    role = create_sample_role()
    role_id = role["id"]

    res = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Kubernetes",
        "category": "MUST_HAVE",
        "description": "Production container orchestration and ingress.",
        "weight": 1.5
    })
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Kubernetes"
    assert data["category"] == "MUST_HAVE"
    assert data["weight"] == 1.5
    assert data["role_id"] == role_id

    # Verify role reflects it
    role_res = client.get(f"/api/v1/roles/{role_id}")
    assert role_res.status_code == 200
    req_names = [r["name"] for r in role_res.json()["requirements"]]
    assert "Kubernetes" in req_names


# 2. DUPLICATE REJECTION TESTS
def test_duplicate_rejection_exact_match():
    """Verify adding identical criterion name rejects with 400 and exact error message."""
    role = create_sample_role()
    role_id = role["id"]

    res1 = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Machine Learning",
        "category": "MUST_HAVE",
        "description": "ML pipeline experience.",
        "weight": 1.0
    })
    assert res1.status_code == 201

    res2 = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Machine Learning",
        "category": "NICE_TO_HAVE",
        "description": "Another ML description.",
        "weight": 2.0
    })
    assert res2.status_code == 400
    assert res2.json()["detail"] == "This criterion already exists for the selected role."


def test_duplicate_rejection_case_insensitive():
    """Verify case variations (machine learning, MACHINE LEARNING) are rejected."""
    role = create_sample_role()
    role_id = role["id"]

    res1 = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Machine Learning",
        "category": "MUST_HAVE",
        "description": "ML pipelines.",
        "weight": 1.0
    })
    assert res1.status_code == 201

    # lowercase
    res_lower = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "machine learning",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    assert res_lower.status_code == 400
    assert res_lower.json()["detail"] == "This criterion already exists for the selected role."

    # UPPERCASE
    res_upper = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "MACHINE LEARNING",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    assert res_upper.status_code == 400
    assert res_upper.json()["detail"] == "This criterion already exists for the selected role."


def test_duplicate_rejection_whitespace_normalized():
    """Verify whitespace variations (leading/trailing/repeated spaces) are normalized and rejected."""
    role = create_sample_role()
    role_id = role["id"]

    res1 = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Machine Learning",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    assert res1.status_code == 201

    # Leading and trailing spaces
    res_pad = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "   Machine Learning   ",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    assert res_pad.status_code == 400
    assert res_pad.json()["detail"] == "This criterion already exists for the selected role."

    # Repeated internal spaces
    res_spaces = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Machine    Learning",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    })
    assert res_spaces.status_code == 400
    assert res_spaces.json()["detail"] == "This criterion already exists for the selected role."


def test_allow_identical_name_under_different_roles():
    """Verify that different roles CAN have criteria with the same name."""
    role1 = create_sample_role(title="Platform Engineer")
    role2 = create_sample_role(title="Data Engineer")

    res1 = client.post(f"/api/v1/roles/{role1['id']}/requirements", json={
        "name": "Python",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    assert res1.status_code == 201

    res2 = client.post(f"/api/v1/roles/{role2['id']}/requirements", json={
        "name": "Python",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    assert res2.status_code == 201


# 3. DELETE CRITERION TESTS
def test_delete_criterion_success():
    """Verify deleting a criterion removes it from role and database."""
    role = create_sample_role()
    role_id = role["id"]

    req1 = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Kubernetes",
        "category": "MUST_HAVE",
        "weight": 1.0
    }).json()

    req2 = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Terraform",
        "category": "MUST_HAVE",
        "weight": 1.0
    }).json()

    # Delete req2
    del_res = client.delete(f"/api/v1/roles/{role_id}/requirements/{req2['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["id"] == req2["id"]

    # Verify role now only has req1
    role_res = client.get(f"/api/v1/roles/{role_id}")
    req_ids = [r["id"] for r in role_res.json()["requirements"]]
    assert req2["id"] not in req_ids
    assert req1["id"] in req_ids


def test_prevent_deleting_only_remaining_criterion():
    """Verify role cannot delete its last remaining criterion."""
    role = create_sample_role()
    role_id = role["id"]

    req = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Core Criterion",
        "category": "MUST_HAVE",
        "weight": 1.0
    }).json()

    del_res = client.delete(f"/api/v1/roles/{role_id}/requirements/{req['id']}")
    assert del_res.status_code == 400
    assert "at least one" in del_res.json()["detail"].lower()


# 4. DOWNSTREAM SCREENING & CASCADE SYNCHRONIZATION TESTS
def test_cascade_evidence_claims_and_score_recalculation():
    """Verify adding/deleting a criterion creates/removes claims and recalculates candidate scores."""
    role = create_sample_role()
    role_id = role["id"]

    # Add initial criteria
    client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Kubernetes",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Terraform",
        "category": "MUST_HAVE",
        "weight": 1.0
    })

    # Upload candidate Jordan Lee (mentions Kubernetes and Terraform in resume)
    upload_res = upload_sample_candidate(role_id=role_id, name="Jordan Lee")
    cand_id = upload_res["candidate"]["id"]
    initial_score = upload_res["fit_score"]["overall_score"]
    assert initial_score > 80.0

    # Jordan should have 2 claims
    ev_res1 = client.get(f"/api/v1/candidates/{cand_id}/evidence")
    assert ev_res1.status_code == 200
    claims1 = ev_res1.json()
    assert len(claims1) == 2

    # Now dynamically ADD a 3rd criterion: "Rust Systems" (NOT in Jordan's resume)
    req3_res = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Rust Systems",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    assert req3_res.status_code == 201
    req3_id = req3_res.json()["id"]

    # 1. Candidate's claims must now include Rust Systems (NOT_FOUND_IN_PROVIDED_MATERIAL)
    ev_res2 = client.get(f"/api/v1/candidates/{cand_id}/evidence")
    claims2 = ev_res2.json()
    assert len(claims2) == 3
    rust_claim = next((c for c in claims2 if c["requirement_id"] == req3_id), None)
    assert rust_claim is not None
    assert rust_claim["status"] == EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL.value

    # 2. Candidate's score must be recalculated down because a MUST_HAVE requirement is now 0 points
    score_res2 = client.get(f"/api/v1/candidates/{cand_id}/score")
    assert score_res2.status_code == 200
    new_score = score_res2.json()["overall_score"]
    assert new_score < initial_score

    # 3. Candidate's gaps must now report Rust Systems as a critical gap
    gaps_res2 = client.get(f"/api/v1/candidates/{cand_id}/gaps")
    assert gaps_res2.status_code == 200
    gap_names = [g["requirement_name"] for g in gaps_res2.json()["gaps"]]
    assert "Rust Systems" in gap_names

    # 4. Candidate matrix must include Rust Systems cell
    matrix_res2 = client.get(f"/api/v1/roles/{role_id}/matrix")
    assert matrix_res2.status_code == 200
    matrix_data2 = matrix_res2.json()
    assert any(r["id"] == req3_id for r in matrix_data2["requirements"])
    cand_row = matrix_data2["candidates"][0]
    assert req3_id in cand_row["cells"]
    assert cand_row["overall_score"] == new_score

    # 5. Now DELETE the "Rust Systems" criterion
    del_res = client.delete(f"/api/v1/roles/{role_id}/requirements/{req3_id}")
    assert del_res.status_code == 200

    # 6. Verify evidence claim for Rust Systems is cascade-deleted
    ev_res3 = client.get(f"/api/v1/candidates/{cand_id}/evidence")
    claims3 = ev_res3.json()
    assert len(claims3) == 2
    assert not any(c["requirement_id"] == req3_id for c in claims3)

    # 7. Candidate's score must be recalculated back up to original baseline
    score_res3 = client.get(f"/api/v1/candidates/{cand_id}/score")
    assert score_res3.status_code == 200
    restored_score = score_res3.json()["overall_score"]
    assert restored_score == initial_score

    # 8. Gaps must no longer contain Rust Systems
    gaps_res3 = client.get(f"/api/v1/candidates/{cand_id}/gaps")
    assert gaps_res3.status_code == 200
    gap_names3 = [g["requirement_name"] for g in gaps_res3.json()["gaps"]]
    assert "Rust Systems" not in gap_names3

    # 9. Matrix must no longer list Rust Systems
    matrix_res3 = client.get(f"/api/v1/roles/{role_id}/matrix")
    assert matrix_res3.status_code == 200
    assert not any(r["id"] == req3_id for r in matrix_res3.json()["requirements"])


# 5. AUDIT TRAIL LOGGING TESTS
def test_audit_trail_criterion_lifecycle():
    """Verify CRITERION_CREATED and CRITERION_DELETED events are logged in audit trail."""
    role = create_sample_role()
    role_id = role["id"]

    # Initial requirement so we don't hit "only 1" invariant on delete
    client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Core Requirement",
        "category": "MUST_HAVE",
        "weight": 1.0
    })

    req = client.post(f"/api/v1/roles/{role_id}/requirements", json={
        "name": "Audit Tracked Skill",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    }).json()

    del_res = client.delete(f"/api/v1/roles/{role_id}/requirements/{req['id']}")
    assert del_res.status_code == 200

    # Query audit events directly from DB session
    db = TestingSessionLocal()
    try:
        events = db.query(AuditEventModel).filter(
            AuditEventModel.entity_type == "ROLE_REQUIREMENT",
            AuditEventModel.entity_id == req["id"]
        ).all()
        actions = [e.action for e in events]
        assert AuditAction.CRITERION_CREATED.value in actions
        assert AuditAction.CRITERION_DELETED.value in actions
    finally:
        db.close()


# 6. ROLE MANAGEMENT, ISOLATION & DELETE ERROR HANDLING TESTS
def test_role_creation_and_persistence():
    """Verify creating a role via API persists in DB with all metadata."""
    res = client.post("/api/v1/roles", json={
        "title": "Machine Learning Engineer",
        "department": "Artificial Intelligence",
        "min_years_experience": 2,
        "raw_jd_text": "Train and deploy deep learning models into production."
    })
    assert res.status_code == 201
    role_data = res.json()
    assert role_data["title"] == "Machine Learning Engineer"
    assert role_data["department"] == "Artificial Intelligence"
    assert role_data["min_years_experience"] == 2
    assert "Train and deploy" in role_data["raw_jd_text"]
    role_id = role_data["id"]

    # Verify retrieval
    get_res = client.get(f"/api/v1/roles/{role_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Machine Learning Engineer"


def test_delete_invalid_criterion_id():
    """Verify deleting a non-existent criterion returns 404 with clear message."""
    role = create_sample_role()
    res = client.delete(f"/api/v1/roles/{role['id']}/requirements/non-existent-criterion-id")
    assert res.status_code == 404
    assert res.json()["detail"] == "Criterion not found"


def test_delete_criterion_from_wrong_role():
    """Verify deleting a criterion using a role ID it does not belong to returns 400."""
    role1 = create_sample_role(title="Role A")
    role2 = create_sample_role(title="Role B")

    # Add 2 criteria to Role 1
    req1 = client.post(f"/api/v1/roles/{role1['id']}/requirements", json={
        "name": "Criterion 1",
        "category": "MUST_HAVE",
        "weight": 1.0
    }).json()
    client.post(f"/api/v1/roles/{role1['id']}/requirements", json={
        "name": "Criterion 2",
        "category": "MUST_HAVE",
        "weight": 1.0
    })

    # Try to delete req1 from Role 2
    del_res = client.delete(f"/api/v1/roles/{role2['id']}/requirements/{req1['id']}")
    assert del_res.status_code == 400
    assert del_res.json()["detail"] == "Criterion does not belong to the selected role"


def test_delete_criterion_response_schema():
    """Verify successful deletion returns success flag, deleted_id, and clear message."""
    role = create_sample_role()
    client.post(f"/api/v1/roles/{role['id']}/requirements", json={
        "name": "Keeper Criterion",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    req_to_delete = client.post(f"/api/v1/roles/{role['id']}/requirements", json={
        "name": "Disposable Skill",
        "category": "NICE_TO_HAVE",
        "weight": 1.0
    }).json()

    del_res = client.delete(f"/api/v1/roles/{role['id']}/requirements/{req_to_delete['id']}")
    assert del_res.status_code == 200
    body = del_res.json()
    assert body["success"] is True
    assert body["deleted_id"] == req_to_delete["id"]
    assert "deleted successfully" in body["message"].lower()


def test_role_criteria_isolation_and_matrix_switching():
    """Verify criteria are strictly scoped to roles and never leak into another role."""
    roleA = create_sample_role(title="Cloud Architect")
    roleB = create_sample_role(title="ML Engineer")

    # Role A criteria
    client.post(f"/api/v1/roles/{roleA['id']}/requirements", json={
        "name": "Kubernetes",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    client.post(f"/api/v1/roles/{roleA['id']}/requirements", json={
        "name": "Terraform",
        "category": "MUST_HAVE",
        "weight": 1.0
    })

    # Role B criteria
    client.post(f"/api/v1/roles/{roleB['id']}/requirements", json={
        "name": "PyTorch",
        "category": "MUST_HAVE",
        "weight": 1.0
    })
    client.post(f"/api/v1/roles/{roleB['id']}/requirements", json={
        "name": "Distributed Training",
        "category": "MUST_HAVE",
        "weight": 1.0
    })

    # Verify Role A
    resA = client.get(f"/api/v1/roles/{roleA['id']}/matrix")
    reqsA = [r["name"] for r in resA.json()["requirements"]]
    assert "Kubernetes" in reqsA
    assert "Terraform" in reqsA
    assert "PyTorch" not in reqsA
    assert "Distributed Training" not in reqsA

    # Verify Role B
    resB = client.get(f"/api/v1/roles/{roleB['id']}/matrix")
    reqsB = [r["name"] for r in resB.json()["requirements"]]
    assert "PyTorch" in reqsB
    assert "Distributed Training" in reqsB
    assert "Kubernetes" not in reqsB
    assert "Terraform" not in reqsB
