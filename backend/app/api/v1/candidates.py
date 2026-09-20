import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db.models import (
    CandidateModel,
    CandidateDocumentModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    RequirementModel,
    InterviewSessionModel,
    AuditEventModel
)
from ...domain.enums import AuditActor, AuditAction, RequirementCategory, EvidenceStatus
from ...domain.schemas import (
    CandidateUploadResponse,
    CandidateRead,
    EvidenceClaimRead,
    FitScoreBreakdown,
    CandidateGapsResponse,
    EvidenceAnalysisRequest,
    EvidenceAnalysisResponse,
    InterviewGenerationRequest,
    InterviewSetupRequest,
    AdaptiveInterviewStateResponse,
    InterviewSessionRead,
    InterviewSessionCreate,
    OverrideCreate,
    OverrideResponse,
    AuditEventRead
)
from ...services.ingestion_service import CandidateIngestionService
from ...services.document_parser import FileValidationError, DocumentParsingError
from ...services.ai_evidence_service import AIEvidenceService
from ...services.gap_detector import GapDetector
from ...services.interview_generator import InterviewGeneratorService
from ...services.scoring_engine import DeterministicScoringEngine

router = APIRouter(prefix="/candidates", tags=["Candidates"])

@router.post("/upload", response_model=CandidateUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_candidate_resume(
    role_id: str = Form(..., min_length=1),
    candidate_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Ingest a candidate resume (PDF, DOCX, or TXT).
    Runs validation, security scanning, prompt injection defense, PII masking,
    evidence extraction, quote verification, and deterministic scoring.
    """
    try:
        content = await file.read()
        response = CandidateIngestionService.ingest_candidate_resume(
            db=db,
            role_id=role_id,
            filename=file.filename or "resume.txt",
            file_bytes=content,
            candidate_name_hint=candidate_name
        )
        return response
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DocumentParsingError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(e)}")

@router.get("", response_model=List[CandidateRead])
def list_candidates(role_id: Optional[str] = None, db: Session = Depends(get_db)):
    """List all candidate records, optionally filtered by role_id."""
    query = db.query(CandidateModel)
    if role_id:
        query = query.filter(CandidateModel.role_id == role_id)
    return query.order_by(CandidateModel.created_at.desc()).all()

@router.get("/{candidate_id}", response_model=CandidateRead)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    """Retrieve single candidate record."""
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.get("/{candidate_id}/document")
def get_candidate_document(candidate_id: str, db: Session = Depends(get_db)):
    """Retrieve the primary uploaded document and text for a candidate."""
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    doc = (
        db.query(CandidateDocumentModel)
        .filter(CandidateDocumentModel.candidate_id == candidate_id)
        .order_by(CandidateDocumentModel.created_at.desc())
        .first()
    )
    if not doc:
        return {"raw_text": "", "sanitized_text": "", "filename": "", "file_hash": ""}
    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "raw_text": doc.raw_text,
        "sanitized_text": doc.sanitized_text,
        "file_hash": doc.file_hash,
        "created_at": doc.created_at.isoformat() if doc.created_at else None
    }

@router.get("/{candidate_id}/audit-trail", response_model=List[AuditEventRead])
def get_candidate_audit_trail(candidate_id: str, db: Session = Depends(get_db)):
    """
    Retrieve chronological audit trail of all actions related to a candidate,
    their documents, evidence claims, and interview sessions.
    """
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    claim_ids = [c.id for c in candidate.evidence_claims]
    session_ids = [s.id for s in candidate.interview_sessions]
    proposal_ids = [p.id for s in candidate.interview_sessions for p in s.proposals]

    relevant_ids = [candidate.id] + claim_ids + session_ids + proposal_ids

    events = (
        db.query(AuditEventModel)
        .filter(AuditEventModel.entity_id.in_(relevant_ids))
        .order_by(AuditEventModel.created_at.desc())
        .all()
    )

    results = []
    for ev in events:
        details_dict = {}
        if ev.details_json:
            try:
                details_dict = json.loads(ev.details_json)
            except Exception:
                details_dict = {"raw": ev.details_json}

        try:
            actor_enum = AuditActor(ev.actor)
        except Exception:
            actor_enum = AuditActor.SYSTEM_AGENT

        try:
            action_enum = AuditAction(ev.action)
        except Exception:
            action_enum = AuditAction.CANDIDATE_INGESTED

        results.append(AuditEventRead(
            id=ev.id,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
            actor=actor_enum,
            action=action_enum,
            details=details_dict,
            created_at=ev.created_at
        ))
    return results

@router.get("/{candidate_id}/evidence", response_model=List[EvidenceClaimRead])
def get_candidate_evidence(candidate_id: str, db: Session = Depends(get_db)):
    """Retrieve all evidence claims with citation verification for a candidate."""
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate_id).all()
    return claims

@router.get("/{candidate_id}/score", response_model=FitScoreBreakdown)
def get_candidate_score(candidate_id: str, db: Session = Depends(get_db)):
    """Retrieve deterministic score breakdown and formula for a candidate."""
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if candidate.quarantined:
        raise HTTPException(status_code=403, detail="Candidate document is quarantined. Scoring is excluded.")

    snapshot = (
        db.query(ScoreSnapshotModel)
        .filter(ScoreSnapshotModel.candidate_id == candidate_id)
        .order_by(ScoreSnapshotModel.created_at.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Score snapshot not found")

    breakdown_data = json.loads(snapshot.breakdown_json)
    return FitScoreBreakdown.model_validate(breakdown_data)

@router.post("/{candidate_id}/evidence/analyze", response_model=EvidenceAnalysisResponse)
async def analyze_candidate_evidence(
    candidate_id: str,
    payload: Optional[EvidenceAnalysisRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Trigger AI evidence matching agent for a candidate.
    Applies strict quote verification gating: any invented citation is forced to UNVERIFIED.
    Quarantined candidates trigger zero LLM calls.
    """
    ai_mode = payload.ai_mode if payload else None
    return await AIEvidenceService.analyze_candidate_evidence(
        db=db,
        candidate_id=candidate_id,
        ai_mode=ai_mode
    )

@router.get("/{candidate_id}/gaps", response_model=CandidateGapsResponse)
def get_candidate_gaps(candidate_id: str, db: Session = Depends(get_db)):
    """
    Retrieve deterministic candidate competency gaps classified by urgency
    (CRITICAL, HIGH, MEDIUM, LOW) based on role criteria and current evidence status.
    """
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if candidate.quarantined:
        raise HTTPException(status_code=403, detail="Candidate document is quarantined. Gap analysis is excluded.")

    requirements = db.query(RequirementModel).filter(RequirementModel.role_id == candidate.role_id).all()
    claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate_id).all()

    gaps = GapDetector.detect_gaps(requirements=requirements, claims=claims)
    return GapDetector.build_response(candidate_id=candidate_id, gaps=gaps)

@router.post("/{candidate_id}/interview/questions/generate", response_model=InterviewSessionRead, status_code=status.HTTP_201_CREATED)
async def generate_interview_questions(
    candidate_id: str,
    payload: Optional[InterviewGenerationRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Generate targeted interview questions conditioned directly on candidate gaps.
    Enforces grounding invariant: every question must link to an actual role requirement.
    """
    ai_mode = payload.ai_mode if payload else None
    max_q = payload.max_questions if payload else 5
    focus_gaps = payload.focus_gaps_only if payload else True

    return await InterviewGeneratorService.generate_interview_questions(
        db=db,
        candidate_id=candidate_id,
        ai_mode=ai_mode,
        max_questions=max_q,
        focus_gaps_only=focus_gaps
    )

@router.post("/{candidate_id}/interview/setup", response_model=AdaptiveInterviewStateResponse, status_code=status.HTTP_201_CREATED)
async def setup_adaptive_interview(
    candidate_id: str,
    payload: InterviewSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Configure and generate a personalized, time-aware adaptive interview:
    - Conditioned on candidate resume, role JD, configured criteria, experience level, and duration.
    - Zero domain hardcoding across roles and technologies.
    """
    from ...services.adaptive_interview_service import AdaptiveInterviewService
    session = await InterviewGeneratorService.generate_adaptive_interview_plan(
        db=db,
        candidate_id=candidate_id,
        experience_level=payload.experience_level,
        duration_minutes=payload.duration_minutes,
        ai_mode=payload.ai_mode
    )
    return AdaptiveInterviewService.get_interview_state(db=db, session_id=session.id)

@router.post("/{candidate_id}/interviews", response_model=InterviewSessionRead, status_code=status.HTTP_201_CREATED)
def create_candidate_interview(
    candidate_id: str,
    payload: Optional[InterviewSessionCreate] = None,
    db: Session = Depends(get_db)
):
    """Create a new interview session for a candidate."""
    from ...services.interview_evidence_service import InterviewEvidenceService
    from .interviews import _serialize_session
    interviewer = payload.interviewer_name if payload else "Recruiter"
    round_name = payload.interview_round if payload else "TECHNICAL_SCREEN"
    session = InterviewEvidenceService.create_interview_session(
        db=db,
        candidate_id=candidate_id,
        interviewer_name=interviewer,
        interview_round=round_name
    )
    return _serialize_session(session, db)

@router.get("/{candidate_id}/interview/sessions", response_model=List[InterviewSessionRead])
def get_interview_sessions(candidate_id: str, db: Session = Depends(get_db)):
    """Retrieve all interview sessions and generated questions for a candidate."""
    from .interviews import _serialize_session
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    sessions = (
        db.query(InterviewSessionModel)
        .filter(InterviewSessionModel.candidate_id == candidate_id)
        .order_by(InterviewSessionModel.created_at.desc())
        .all()
    )
    return [_serialize_session(s, db) for s in sessions]

@router.post("/{candidate_id}/evidence/{evidence_id}/override", response_model=OverrideResponse)
def override_candidate_evidence(
    candidate_id: str,
    evidence_id: str,
    payload: OverrideCreate,
    db: Session = Depends(get_db)
):
    """
    Human recruiter override of an AI or system-extracted evidence claim.
    Requires mandatory justification reason, logs an immutable audit event,
    and recalculates the deterministic fit score.
    """
    candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    claim = (
        db.query(EvidenceClaimModel)
        .filter(EvidenceClaimModel.id == evidence_id, EvidenceClaimModel.candidate_id == candidate_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Evidence claim not found")

    old_status = claim.status
    claim.status = payload.new_status.value
    claim.is_human_overridden = True
    claim.override_reason = payload.override_reason

    # Recalculate deterministic score
    requirements = db.query(RequirementModel).filter(RequirementModel.role_id == candidate.role_id).all()
    all_claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate_id).all()
    claims_by_req = {c.requirement_id: EvidenceStatus(c.status) for c in all_claims}

    role = candidate.role
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
        required_years_exp=role.min_years_experience if role else 0,
        weights={
            "must_have": role.weight_must_have if role else 0.65,
            "nice_to_have": role.weight_nice_to_have if role else 0.20,
            "experience": role.weight_experience if role else 0.15
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

    db.add(AuditEventModel(
        entity_type="EVIDENCE_CLAIM",
        entity_id=claim.id,
        actor=AuditActor.RECRUITER.value,
        action=AuditAction.RECRUITER_OVERRIDE.value,
        details_json=json.dumps({
            "old_status": old_status,
            "new_status": payload.new_status.value,
            "override_reason": payload.override_reason,
            "new_overall_score": score_breakdown.overall_score
        })
    ))

    db.commit()
    db.refresh(claim)

    return OverrideResponse(
        evidence_claim=EvidenceClaimRead.model_validate(claim),
        fit_score=score_breakdown
    )
