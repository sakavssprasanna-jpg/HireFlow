import re
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...db.base import get_db
from ...db.models import (
    RoleModel,
    RequirementModel,
    CandidateModel,
    CandidateDocumentModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    AuditEventModel,
    InterviewEvidenceProposalModel,
    InterviewQuestionModel
)
from ...domain.enums import (
    AuditAction,
    AuditActor,
    RequirementCategory,
    EvidenceStatus,
    SourceType
)
from ...domain.schemas import (
    RoleCreate,
    RoleRead,
    RequirementRead,
    RequirementCreate,
    CandidateRead,
    CandidateMatrixResponse,
    CandidateMatrixRow,
    CandidateMatrixCell
)
from ...services.scoring_engine import DeterministicScoringEngine
from ...services.quote_verifier import QuoteVerifier

router = APIRouter(prefix="/roles", tags=["Roles"])

def normalize_criterion_name(name: str) -> str:
    """Trim leading/trailing whitespace, collapse repeated whitespace, lowercase."""
    return re.sub(r"\s+", " ", (name or "").strip()).lower()

def recalculate_candidate_score(db: Session, candidate: CandidateModel, role: RoleModel) -> ScoreSnapshotModel:
    """Recalculate deterministic fit score snapshot for a candidate against role requirements."""
    requirements = db.query(RequirementModel).filter(RequirementModel.role_id == role.id).all()
    all_claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate.id).all()
    claims_by_req = {c.requirement_id: EvidenceStatus(c.status) for c in all_claims}

    req_dicts = [{
        "id": r.id,
        "name": r.name,
        "category": RequirementCategory(r.category),
        "weight": r.weight
    } for r in requirements]

    score_breakdown = DeterministicScoringEngine.calculate_score(
        candidate_id=candidate.id,
        requirements=req_dicts,
        claims_by_req_id=claims_by_req,
        candidate_years_exp=candidate.years_experience,
        required_years_exp=role.min_years_experience,
        weights={
            "must_have": role.weight_must_have,
            "nice_to_have": role.weight_nice_to_have,
            "experience": role.weight_experience
        }
    )

    score_snapshot = ScoreSnapshotModel(
        candidate_id=candidate.id,
        overall_score=score_breakdown.overall_score,
        must_have_score=score_breakdown.must_have_score,
        nice_to_have_score=score_breakdown.nice_to_have_score,
        experience_score=score_breakdown.experience_score,
        formula_representation=score_breakdown.formula_representation,
        breakdown_json=score_breakdown.model_dump_json()
    )
    db.add(score_snapshot)
    return score_snapshot

@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(role_in: RoleCreate, db: Session = Depends(get_db)):
    """Create a new job requisition role."""
    title = role_in.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Role title is required and cannot be empty.")

    department = role_in.department.strip() if (role_in.department and role_in.department.strip()) else "General"
    raw_jd = role_in.raw_jd_text.strip() if (role_in.raw_jd_text and role_in.raw_jd_text.strip()) else f"Job requisition profile for {title}."

    role = RoleModel(
        title=title,
        department=department,
        raw_jd_text=raw_jd,
        min_years_experience=role_in.min_years_experience,
        weight_must_have=role_in.weight_must_have,
        weight_nice_to_have=role_in.weight_nice_to_have,
        weight_experience=role_in.weight_experience
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.get("", response_model=List[RoleRead])
def list_roles(db: Session = Depends(get_db)):
    """List all job requisitions."""
    return db.query(RoleModel).all()

@router.get("/{role_id}", response_model=RoleRead)
def get_role(role_id: str, db: Session = Depends(get_db)):
    """Get single role with its requirements."""
    role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.post("/{role_id}/requirements", response_model=RequirementRead, status_code=status.HTTP_201_CREATED)
def add_role_requirement(role_id: str, req_in: RequirementCreate, db: Session = Depends(get_db)):
    """Add a requirement criterion to an existing role with duplicate prevention and candidate sync."""
    role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    target_norm = normalize_criterion_name(req_in.name)
    if not target_norm:
        raise HTTPException(status_code=400, detail="Criterion name cannot be empty.")

    # Duplicate check within role
    for existing in role.requirements:
        if normalize_criterion_name(existing.name) == target_norm:
            raise HTTPException(status_code=400, detail="This criterion already exists for the selected role.")

    req = RequirementModel(
        role_id=role_id,
        name=req_in.name.strip(),
        category=req_in.category.value if hasattr(req_in.category, "value") else str(req_in.category),
        description=req_in.description.strip() if req_in.description else "",
        weight=req_in.weight
    )
    db.add(req)
    db.flush()

    # Ingest evidence claims for existing candidates and recalculate their scores
    existing_candidates = db.query(CandidateModel).filter(CandidateModel.role_id == role_id).all()
    for candidate in existing_candidates:
        if candidate.quarantined:
            continue

        doc = (
            db.query(CandidateDocumentModel)
            .filter(CandidateDocumentModel.candidate_id == candidate.id)
            .order_by(CandidateDocumentModel.created_at.desc())
            .first()
        )

        claim_created = False
        if doc and doc.raw_text:
            req_name_lower = req.name.lower()
            raw_text_lower = doc.raw_text.lower()
            if req_name_lower in raw_text_lower:
                idx = raw_text_lower.find(req_name_lower)
                snippet_start = max(0, idx - 40)
                snippet_end = min(len(doc.raw_text), idx + len(req.name) + 60)
                extracted_quote = doc.raw_text[snippet_start:snippet_end].strip()

                verification = QuoteVerifier.verify_quote(
                    raw_source_text=doc.raw_text,
                    quote=extracted_quote
                )
                claim_status = EvidenceStatus.PROVEN if verification.valid else EvidenceStatus.UNVERIFIED
                claim = EvidenceClaimModel(
                    candidate_id=candidate.id,
                    requirement_id=req.id,
                    source_document_id=doc.id,
                    source_type=SourceType.RESUME.value,
                    section_reference="Resume",
                    verbatim_quote=verification.matched_text if verification.valid else extracted_quote,
                    start_offset=verification.start_offset,
                    end_offset=verification.end_offset,
                    status=claim_status.value,
                    reasoning="Keyword match found during dynamic criterion addition.",
                    confidence=0.9 if verification.valid else 0.4
                )
                db.add(claim)
                claim_created = True

        if not claim_created:
            claim = EvidenceClaimModel(
                candidate_id=candidate.id,
                requirement_id=req.id,
                source_document_id=doc.id if doc else None,
                source_type=SourceType.RESUME.value,
                section_reference="Not Located",
                verbatim_quote=None,
                status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL.value,
                reasoning="No evidence found in candidate documents for this new requirement.",
                confidence=1.0
            )
            db.add(claim)

        db.flush()
        recalculate_candidate_score(db, candidate, role)

    # Log audit event
    db.add(AuditEventModel(
        entity_type="ROLE_REQUIREMENT",
        entity_id=req.id,
        actor=AuditActor.RECRUITER.value,
        action=AuditAction.CRITERION_CREATED.value,
        details_json=json.dumps({
            "role_id": role_id,
            "requirement_name": req.name,
            "category": req.category,
            "weight": req.weight
        })
    ))

    db.commit()
    db.refresh(req)
    return req

@router.delete("/{role_id}/requirements/{requirement_id}", status_code=status.HTTP_200_OK)
def delete_role_requirement(role_id: str, requirement_id: str, db: Session = Depends(get_db)):
    """Delete a criterion from a role, cascade-delete its claims, and recalculate candidate scores."""
    role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    req = db.query(RequirementModel).filter(
        RequirementModel.id == requirement_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Criterion not found")
    if req.role_id != role_id:
        raise HTTPException(status_code=400, detail="Criterion does not belong to the selected role")

    if len(role.requirements) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the only remaining criterion for this role. A role must maintain at least one evaluation criterion."
        )

    req_name = req.name
    req_category = req.category

    # 1. Delete associated evidence claims
    db.query(EvidenceClaimModel).filter(
        EvidenceClaimModel.requirement_id == requirement_id
    ).delete(synchronize_session=False)

    # 2. Delete associated interview evidence proposals
    db.query(InterviewEvidenceProposalModel).filter(
        InterviewEvidenceProposalModel.requirement_id == requirement_id
    ).delete(synchronize_session=False)

    # 3. Unlink interview questions pointing to this requirement
    db.query(InterviewQuestionModel).filter(
        InterviewQuestionModel.requirement_id == requirement_id
    ).update({"requirement_id": None}, synchronize_session=False)

    # 4. Delete the requirement
    db.delete(req)
    db.flush()

    # 5. Recalculate scores for all non-quarantined candidates
    remaining_candidates = db.query(CandidateModel).filter(
        CandidateModel.role_id == role_id,
        CandidateModel.quarantined == False
    ).all()
    for candidate in remaining_candidates:
        recalculate_candidate_score(db, candidate, role)

    # 6. Log audit event
    db.add(AuditEventModel(
        entity_type="ROLE_REQUIREMENT",
        entity_id=requirement_id,
        actor=AuditActor.RECRUITER.value,
        action=AuditAction.CRITERION_DELETED.value,
        details_json=json.dumps({
            "role_id": role_id,
            "requirement_name": req_name,
            "category": req_category,
            "remaining_requirements_count": len(role.requirements) - 1
        })
    ))

    db.commit()
    return {
        "success": True,
        "deleted_id": requirement_id,
        "id": requirement_id,
        "role_id": role_id,
        "message": f"Criterion '{req_name}' deleted successfully",
        "detail": f"Criterion '{req_name}' deleted successfully"
    }

@router.get("/{role_id}/candidates", response_model=List[CandidateRead])
def list_role_candidates(role_id: str, db: Session = Depends(get_db)):
    """List all candidate records attached to a role."""
    from ...db.models import CandidateModel
    role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return db.query(CandidateModel).filter(CandidateModel.role_id == role_id).order_by(CandidateModel.created_at.desc()).all()

@router.get("/{role_id}/matrix", response_model=CandidateMatrixResponse)
def get_role_comparison_matrix(role_id: str, db: Session = Depends(get_db)):
    """
    Retrieve candidate comparison matrix across requirements for a role.
    Computes rows for every candidate with active claim status and verified deterministic score.
    """
    from ...db.models import CandidateModel, EvidenceClaimModel, ScoreSnapshotModel
    from ...domain.enums import EvidenceStatus
    from ...domain.schemas import CandidateMatrixCell, CandidateMatrixRow, CandidateMatrixResponse

    role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    requirements = role.requirements
    candidates = db.query(CandidateModel).filter(CandidateModel.role_id == role_id).order_by(CandidateModel.created_at.desc()).all()

    matrix_rows: List[CandidateMatrixRow] = []

    for c in candidates:
        # Get latest score snapshot
        latest_snap = (
            db.query(ScoreSnapshotModel)
            .filter(ScoreSnapshotModel.candidate_id == c.id)
            .order_by(ScoreSnapshotModel.created_at.desc())
            .first()
        )
        score_val = latest_snap.overall_score if latest_snap else None

        # Build cells for each requirement
        claims_by_req = {cl.requirement_id: cl for cl in c.evidence_claims}
        cells_dict: dict = {}

        for req in requirements:
            claim = claims_by_req.get(req.id)
            if claim:
                cells_dict[req.id] = CandidateMatrixCell(
                    requirement_id=req.id,
                    requirement_name=req.name,
                    status=EvidenceStatus(claim.status),
                    confidence=claim.confidence,
                    source_type=claim.source_type,
                    verbatim_quote=claim.verbatim_quote,
                    is_human_overridden=claim.is_human_overridden
                )
            else:
                cells_dict[req.id] = CandidateMatrixCell(
                    requirement_id=req.id,
                    requirement_name=req.name,
                    status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL,
                    confidence=1.0,
                    source_type="SYSTEM",
                    verbatim_quote=None,
                    is_human_overridden=False
                )

        matrix_rows.append(CandidateMatrixRow(
            candidate_id=c.id,
            full_name=c.full_name,
            anonymous_alias=c.anonymous_alias,
            years_experience=c.years_experience,
            quarantined=c.quarantined,
            quarantine_reason=c.quarantine_reason,
            overall_score=score_val,
            cells=cells_dict
        ))

    return CandidateMatrixResponse(
        role_id=role.id,
        role_title=role.title,
        requirements=[RequirementRead.model_validate(r) for r in requirements],
        candidates=matrix_rows
    )

