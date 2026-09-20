from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db.base import get_db
from ...db.models import InterviewSessionModel, InterviewEvidenceProposalModel, RequirementModel
from ...domain.enums import AIMode
from ...domain.schemas import (
    InterviewSessionRead,
    InterviewNotesSubmitRequest,
    InterviewEvidenceProposal,
    InterviewEvidenceConfirmRequest,
    InterviewEvidenceRejectRequest,
    InterviewEvidenceConfirmResponse,
    InterviewEvidenceAnalysisRequest,
    InterviewEvidenceAnalysisResponse,
    InterviewQuestionRead,
    AdaptiveInterviewStateResponse,
    AdaptiveAnswerRequest,
    AdaptiveFollowupRequest,
    AdaptiveSkipRequest,
    InterviewSummaryResponse
)
from ...services.interview_evidence_service import InterviewEvidenceService
from ...services.adaptive_interview_service import AdaptiveInterviewService

router = APIRouter(prefix="/interviews", tags=["Interviews"])

def _serialize_session(session: InterviewSessionModel, db: Session) -> InterviewSessionRead:
    # Build proposals schemas
    proposals_data = []
    for p in session.proposals:
        req_name = "Unknown"
        req = db.query(RequirementModel).filter(RequirementModel.id == p.requirement_id).first()
        if req:
            req_name = req.name

        proposals_data.append(InterviewEvidenceProposal(
            id=p.id,
            session_id=p.session_id,
            requirement_id=p.requirement_id,
            requirement_name=req_name,
            verbatim_excerpt=p.verbatim_excerpt,
            start_offset=p.start_offset,
            end_offset=p.end_offset,
            proposed_status=p.proposed_status,
            justification=p.justification,
            confidence_score=p.confidence_score,
            review_status=p.review_status,
            recruiter_notes=p.recruiter_notes,
            created_at=p.created_at
        ))

    return InterviewSessionRead(
        id=session.id,
        candidate_id=session.candidate_id,
        interviewer_name=session.interviewer_name,
        interview_round=session.interview_round,
        status=session.status,
        raw_notes=session.raw_notes,
        created_at=session.created_at,
        updated_at=session.updated_at,
        questions=[InterviewQuestionRead.model_validate(q) for q in session.questions],
        proposals=proposals_data
    )

@router.get("/{session_id}", response_model=InterviewSessionRead)
def get_interview_session(session_id: str, db: Session = Depends(get_db)):
    """Retrieve an interview session with its questions and evidence proposals."""
    session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return _serialize_session(session, db)

@router.post("/{session_id}/notes", response_model=InterviewSessionRead)
def submit_interview_notes(
    session_id: str,
    payload: InterviewNotesSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    Submit raw recruiter notes for an interview session.
    Runs prompt-injection security scan. Quarantines session if malicious.
    """
    session = InterviewEvidenceService.submit_interview_notes(
        db=db,
        session_id=session_id,
        raw_notes=payload.raw_notes,
        interviewer_name=payload.interviewer_name,
        interview_round=payload.interview_round
    )
    return _serialize_session(session, db)

@router.post("/{session_id}/evidence/analyze", response_model=InterviewEvidenceAnalysisResponse)
async def analyze_interview_evidence(
    session_id: str,
    payload: Optional[InterviewEvidenceAnalysisRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Trigger AI evidence extraction from interview notes with deterministic quote verification gating.
    Proposes evidence updates; requires recruiter confirmation before applying.
    """
    ai_mode = payload.ai_mode if payload else None
    return await InterviewEvidenceService.analyze_interview_evidence(
        db=db,
        session_id=session_id,
        ai_mode=ai_mode
    )

@router.get("/{session_id}/evidence", response_model=List[InterviewEvidenceProposal])
def get_interview_evidence_proposals(session_id: str, db: Session = Depends(get_db)):
    """Retrieve all evidence proposals extracted from this interview session."""
    session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    proposals = db.query(InterviewEvidenceProposalModel).filter(
        InterviewEvidenceProposalModel.session_id == session_id
    ).all()

    result = []
    for p in proposals:
        req_name = "Unknown"
        req = db.query(RequirementModel).filter(RequirementModel.id == p.requirement_id).first()
        if req:
            req_name = req.name

        result.append(InterviewEvidenceProposal(
            id=p.id,
            session_id=p.session_id,
            requirement_id=p.requirement_id,
            requirement_name=req_name,
            verbatim_excerpt=p.verbatim_excerpt,
            start_offset=p.start_offset,
            end_offset=p.end_offset,
            proposed_status=p.proposed_status,
            justification=p.justification,
            confidence_score=p.confidence_score,
            review_status=p.review_status,
            recruiter_notes=p.recruiter_notes,
            created_at=p.created_at
        ))
    return result

@router.post("/{session_id}/evidence/{proposal_id}/approve", response_model=InterviewEvidenceConfirmResponse)
def approve_interview_evidence(
    session_id: str,
    proposal_id: str,
    payload: Optional[InterviewEvidenceConfirmRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Human recruiter approval gate. Confirms evidence proposal and reconciles candidate claims.
    Deterministically recalculates candidate score and competency gaps.
    """
    override_status = payload.override_status if payload else None
    justification = payload.justification if payload else None

    return InterviewEvidenceService.reconcile_and_approve_evidence(
        db=db,
        session_id=session_id,
        proposal_id=proposal_id,
        override_status=override_status,
        justification=justification
    )

@router.post("/{session_id}/evidence/{proposal_id}/reject", response_model=InterviewEvidenceProposal)
def reject_interview_evidence(
    session_id: str,
    proposal_id: str,
    payload: InterviewEvidenceRejectRequest,
    db: Session = Depends(get_db)
):
    """
    Human recruiter rejection of an AI evidence proposal.
    Records audit event. Candidate evidence and scores remain unchanged.
    """
    return InterviewEvidenceService.reject_evidence_proposal(
        db=db,
        session_id=session_id,
        proposal_id=proposal_id,
        rejection_reason=payload.rejection_reason
    )

# --- Adaptive Live Interview Endpoints ---

@router.get("/{session_id}/state", response_model=AdaptiveInterviewStateResponse)
def get_adaptive_interview_state(session_id: str, db: Session = Depends(get_db)):
    """Retrieve complete live state of the adaptive interview session."""
    return AdaptiveInterviewService.get_interview_state(db=db, session_id=session_id)

@router.post("/{session_id}/start", response_model=AdaptiveInterviewStateResponse)
def start_adaptive_interview(session_id: str, db: Session = Depends(get_db)):
    """Start or resume active conducting of the interview session."""
    return AdaptiveInterviewService.start_interview(db=db, session_id=session_id)

@router.post("/{session_id}/questions/{question_id}/answer", response_model=AdaptiveInterviewStateResponse)
def capture_candidate_answer(
    session_id: str,
    question_id: str,
    payload: AdaptiveAnswerRequest,
    db: Session = Depends(get_db)
):
    """
    Capture candidate answer for the active question:
    - Scans for security violations / prompt-injection
    - Extracts & verifies verbatim quote via QuoteVerifier
    - Reconciles candidate evidence claim
    - Recalculates deterministic fit score and competency gaps
    - Updates remaining interview time and advances to next question
    """
    return AdaptiveInterviewService.capture_candidate_answer(
        db=db,
        session_id=session_id,
        question_id=question_id,
        answer_text=payload.answer_text,
        seconds_spent=payload.seconds_spent
    )

@router.post("/{session_id}/questions/{question_id}/followup", response_model=AdaptiveInterviewStateResponse)
def ask_adaptive_followup(
    session_id: str,
    question_id: str,
    payload: Optional[AdaptiveFollowupRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Generate an adaptive follow-up question for the target requirement,
    probing deeper into candidate implementation or architectural choices.
    """
    notes = payload.notes_context if payload else None
    return AdaptiveInterviewService.ask_followup(
        db=db,
        session_id=session_id,
        question_id=question_id,
        notes_context=notes
    )

@router.post("/{session_id}/questions/{question_id}/skip", response_model=AdaptiveInterviewStateResponse)
def skip_adaptive_question(
    session_id: str,
    question_id: str,
    payload: Optional[AdaptiveSkipRequest] = None,
    db: Session = Depends(get_db)
):
    """Skip current question and advance to the next priority requirement."""
    reason = payload.reason if payload else None
    return AdaptiveInterviewService.skip_question(
        db=db,
        session_id=session_id,
        question_id=question_id,
        reason=reason
    )

@router.post("/{session_id}/end", response_model=InterviewSummaryResponse)
def end_adaptive_interview(session_id: str, db: Session = Depends(get_db)):
    """
    Conclude the interview session early or at completion:
    - Computes pre vs. post interview score delta
    - Resolves gaps and produces full coverage matrix
    - Compiles verified transcript
    """
    return AdaptiveInterviewService.end_interview(db=db, session_id=session_id)

