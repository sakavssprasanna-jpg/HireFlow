import json
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..domain.enums import (
    EvidenceStatus,
    RequirementCategory,
    SourceType,
    AuditAction,
    AuditActor,
    AIMode,
    InterviewSessionStatus,
    InterviewProposalStatus
)
from ..domain.schemas import (
    InterviewSessionRead,
    InterviewEvidenceProposal,
    InterviewEvidenceConfirmResponse,
    InterviewEvidenceAnalysisResponse,
    InterviewEvidenceOutput,
    FitScoreBreakdown,
    CandidateGapsResponse
)
from ..db.models import (
    CandidateModel,
    RequirementModel,
    InterviewSessionModel,
    InterviewEvidenceProposalModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    AuditEventModel
)
from ..ai.factory import get_llm_provider
from ..ai.base import ProviderError
from .security_scanner import SecurityScanner
from .quote_verifier import QuoteVerifier
from .scoring_engine import DeterministicScoringEngine
from .gap_detector import GapDetector

logger = logging.getLogger("hireflow.services.interview_evidence")

class InterviewEvidenceService:
    """
    Orchestrates the post-interview evidence pipeline:
    Notes Ingestion -> Security Scan -> AI Extraction -> Excerpt Verification ->
    Human Confirmation Gate -> Multi-Source Reconciliation -> Deterministic Score & Gap Recalculation.
    """

    @classmethod
    def create_interview_session(
        cls,
        db: Session,
        candidate_id: str,
        interviewer_name: Optional[str] = "Recruiter",
        interview_round: Optional[str] = "TECHNICAL_SCREEN"
    ) -> InterviewSessionModel:
        candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate '{candidate_id}' not found.")

        if candidate.quarantined:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Candidate document is quarantined ({candidate.quarantine_reason}). Interview operations are prohibited."
            )

        session = InterviewSessionModel(
            candidate_id=candidate.id,
            interviewer_name=interviewer_name or "Recruiter",
            interview_round=interview_round or "TECHNICAL_SCREEN",
            status=InterviewSessionStatus.DRAFT.value
        )
        db.add(session)
        db.flush()

        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.INTERVIEW_SESSION_CREATED.value,
            details_json=json.dumps({
                "candidate_id": candidate.id,
                "interviewer": session.interviewer_name,
                "round": session.interview_round
            })
        ))
        db.commit()
        db.refresh(session)
        return session

    @classmethod
    def submit_interview_notes(
        cls,
        db: Session,
        session_id: str,
        raw_notes: str,
        interviewer_name: Optional[str] = None,
        interview_round: Optional[str] = None
    ) -> InterviewSessionModel:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Interview session '{session_id}' not found.")

        candidate = session.candidate
        if candidate.quarantined:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Candidate is quarantined. Notes submission is prohibited."
            )

        # 1. Prompt-Injection Security Scan
        scan_result = SecurityScanner.scan_text(raw_notes)
        if scan_result.quarantined:
            session.status = InterviewSessionStatus.QUARANTINED.value
            db.add(AuditEventModel(
                entity_type="INTERVIEW_SESSION",
                entity_id=session.id,
                actor=AuditActor.SYSTEM_AGENT.value,
                action=AuditAction.SECURITY_QUARANTINE.value,
                details_json=json.dumps({
                    "reason": scan_result.quarantine_reason,
                    "matched_rules": scan_result.matched_rules,
                    "severity": scan_result.severity
                })
            ))
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Interview notes quarantined due to prompt injection: {scan_result.quarantine_reason}. Downstream AI is prohibited."
            )

        # 2. Update Session with Clean Notes
        session.raw_notes = raw_notes
        if interviewer_name:
            session.interviewer_name = interviewer_name
        if interview_round:
            session.interview_round = interview_round
        session.status = InterviewSessionStatus.IN_PROGRESS.value

        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.INTERVIEW_NOTES_ADDED.value,
            details_json=json.dumps({
                "length": len(raw_notes),
                "interviewer": session.interviewer_name,
                "round": session.interview_round
            })
        ))
        db.commit()
        db.refresh(session)
        return session

    @classmethod
    async def analyze_interview_evidence(
        cls,
        db: Session,
        session_id: str,
        ai_mode: Optional[AIMode] = None
    ) -> InterviewEvidenceAnalysisResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        candidate = session.candidate
        if candidate.quarantined:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate is quarantined. AI extraction prohibited.")

        if session.status == InterviewSessionStatus.QUARANTINED.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interview notes are quarantined. AI extraction prohibited.")

        if not session.raw_notes or len(session.raw_notes.strip()) < 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview notes are empty or too short for extraction.")

        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == candidate.role_id).all()
        if not requirements:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No requirements configured for this role.")

        # 1. Construct Prompt
        req_lines = [f"- REQUIREMENT: {r.name} | CATEGORY: {r.category} | DESCRIPTION: {r.description or 'None'}" for r in requirements]
        requirements_block = "\n".join(req_lines)

        full_prompt = (
            f"ROLE REQUIREMENTS TO ASSESS:\n{requirements_block}\n\n"
            f"INTERVIEW_NOTES:\n{session.raw_notes}\n"
        )

        system_instruction = (
            "You are an objective interview evidence auditor. "
            "Extract candidate evidence from the supplied interview notes for the specified requirements. "
            "Every proposed evidence item must include an exact, verbatim excerpt from the interview notes. "
            "If candidate demonstrated skill in production, propose PROVEN. "
            "If candidate admitted lack of skill or failed technical scenario, propose CONTRADICTED. "
            "If uncertain or evidence is weak, return UNVERIFIED. "
            "Never invent candidate statements or scores. Fabricated excerpts will be rejected by our deterministic verification engine."
        )

        # 2. Invoke AI Provider
        provider = get_llm_provider(ai_mode)
        try:
            response = await provider.generate_structured(
                prompt=full_prompt,
                schema=InterviewEvidenceOutput,
                system_instruction=system_instruction
            )
            output: InterviewEvidenceOutput = response.data
            meta = response.metadata
        except ProviderError as pe:
            logger.warning(f"AI Provider error ({pe}); using OfflineFallbackProvider for interview notes.")
            fallback_provider = get_llm_provider(AIMode.OFFLINE_FALLBACK)
            response = await fallback_provider.generate_structured(
                prompt=full_prompt,
                schema=InterviewEvidenceOutput,
                system_instruction=system_instruction
            )
            output = response.data
            meta = response.metadata

        # 3. Deterministic Excerpt Verification Gate
        req_by_name_lower = {r.name.lower(): r for r in requirements}

        # Clear existing PENDING proposals for this session to avoid duplicate proposals
        db.query(InterviewEvidenceProposalModel).filter(
            InterviewEvidenceProposalModel.session_id == session.id,
            InterviewEvidenceProposalModel.review_status == InterviewProposalStatus.PENDING.value
        ).delete()

        proposals_created: List[InterviewEvidenceProposalModel] = []

        for item in output.evidence_items:
            # Map requirement
            target_req = req_by_name_lower.get(item.requirement_name.lower())
            if not target_req:
                for r_name_lower, r_obj in req_by_name_lower.items():
                    if item.requirement_name.lower() in r_name_lower or r_name_lower in item.requirement_name.lower():
                        target_req = r_obj
                        break
            if not target_req:
                continue

            # Deterministic Excerpt Verification against raw notes
            final_status = item.updated_status
            verbatim = item.verbatim_quote
            start_off = None
            end_off = None
            justification = item.reasoning

            if verbatim and verbatim.strip():
                verification = QuoteVerifier.verify_quote(
                    raw_source_text=session.raw_notes,
                    quote=verbatim
                )
                if verification.valid:
                    start_off = verification.start_offset
                    end_off = verification.end_offset
                    verbatim = verification.matched_text
                else:
                    # DETERMINISTIC HALLUCINATION PREVENTION
                    final_status = EvidenceStatus.UNVERIFIED
                    justification = f"[UNVERIFIED_HALLUCINATION_PREVENTED: Excerpt was not verified in interview notes] {justification}"
                    conf_score = 0.1
            else:
                final_status = EvidenceStatus.UNVERIFIED
                justification = f"[UNVERIFIED_HALLUCINATION_PREVENTED: Missing verbatim excerpt] {justification}"
                conf_score = 0.0

            proposal = InterviewEvidenceProposalModel(
                session_id=session.id,
                requirement_id=target_req.id,
                verbatim_excerpt=verbatim,
                start_offset=start_off,
                end_offset=end_off,
                proposed_status=final_status.value,
                justification=justification,
                confidence_score=conf_score if final_status == EvidenceStatus.UNVERIFIED and "[UNVERIFIED_HALLUCINATION_PREVENTED" in justification else item.confidence_score,
                review_status=InterviewProposalStatus.PENDING.value
            )
            db.add(proposal)
            proposals_created.append(proposal)

        session.status = InterviewSessionStatus.COMPLETED.value

        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.INTERVIEW_EVIDENCE_PROPOSED.value,
            details_json=json.dumps({
                "proposals_count": len(proposals_created),
                "provider": meta.provider_name,
                "is_fallback": meta.is_fallback
            })
        ))
        db.commit()

        # Build schema items
        p_schemas = []
        for p in proposals_created:
            req_name = next((r.name for r in requirements if r.id == p.requirement_id), "Unknown")
            p_schemas.append(InterviewEvidenceProposal(
                id=p.id,
                session_id=p.session_id,
                requirement_id=p.requirement_id,
                requirement_name=req_name,
                verbatim_excerpt=p.verbatim_excerpt,
                start_offset=p.start_offset,
                end_offset=p.end_offset,
                proposed_status=EvidenceStatus(p.proposed_status),
                justification=p.justification,
                confidence_score=p.confidence_score,
                review_status=p.review_status,
                recruiter_notes=p.recruiter_notes,
                created_at=p.created_at
            ))

        return InterviewEvidenceAnalysisResponse(
            session_id=session.id,
            proposals=p_schemas,
            proposals_count=len(p_schemas),
            provider_metadata=meta.model_dump()
        )

    @classmethod
    def reconcile_and_approve_evidence(
        cls,
        db: Session,
        session_id: str,
        proposal_id: str,
        override_status: Optional[EvidenceStatus] = None,
        justification: Optional[str] = None
    ) -> InterviewEvidenceConfirmResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        candidate = session.candidate
        if candidate.quarantined:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate is quarantined.")

        proposal = db.query(InterviewEvidenceProposalModel).filter(
            InterviewEvidenceProposalModel.id == proposal_id,
            InterviewEvidenceProposalModel.session_id == session_id
        ).first()
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence proposal not found.")

        # Determine effective status and validate justification if overridden
        proposed_enum = EvidenceStatus(proposal.proposed_status)
        is_overridden = override_status is not None and override_status != proposed_enum

        if is_overridden:
            if not justification or len(justification.strip()) < 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mandatory justification of at least 5 characters required when overriding proposed evidence status."
                )
            final_status = override_status
            final_reason = f"[Recruiter Override: {justification}] {proposal.justification}"
        else:
            final_status = override_status or proposed_enum
            final_reason = justification or proposal.justification

        # 1. Update proposal record
        proposal.review_status = InterviewProposalStatus.APPROVED.value
        proposal.recruiter_notes = final_reason

        # 2. Reconcile and update Candidate Evidence Claim for this requirement
        active_claim = db.query(EvidenceClaimModel).filter(
            EvidenceClaimModel.candidate_id == candidate.id,
            EvidenceClaimModel.requirement_id == proposal.requirement_id
        ).first()

        effective_source = SourceType.RECRUITER_OVERRIDE.value if is_overridden else SourceType.INTERVIEW_NOTE.value

        if active_claim:
            active_claim.status = final_status.value
            active_claim.source_type = effective_source
            active_claim.source_document_id = session.id
            active_claim.section_reference = f"Interview ({session.interview_round})"
            active_claim.verbatim_quote = proposal.verbatim_excerpt
            active_claim.start_offset = proposal.start_offset
            active_claim.end_offset = proposal.end_offset
            active_claim.reasoning = final_reason
            active_claim.confidence = proposal.confidence_score
            active_claim.is_human_overridden = is_overridden
            active_claim.override_reason = justification if is_overridden else None
        else:
            active_claim = EvidenceClaimModel(
                candidate_id=candidate.id,
                requirement_id=proposal.requirement_id,
                source_document_id=session.id,
                source_type=effective_source,
                section_reference=f"Interview ({session.interview_round})",
                verbatim_quote=proposal.verbatim_excerpt,
                start_offset=proposal.start_offset,
                end_offset=proposal.end_offset,
                status=final_status.value,
                reasoning=final_reason,
                confidence=proposal.confidence_score,
                is_human_overridden=is_overridden,
                override_reason=justification if is_overridden else None
            )
            db.add(active_claim)

        db.flush()

        # 3. Multi-Source Evidence Reconciliation for Scoring & Gaps
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == candidate.role_id).all()
        all_candidate_claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate.id).all()

        reconciled_status_by_req: Dict[str, EvidenceStatus] = {
            c.requirement_id: EvidenceStatus(c.status) for c in all_candidate_claims
        }

        for req in requirements:
            if req.id not in reconciled_status_by_req:
                reconciled_status_by_req[req.id] = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL

        # 4. Fetch Previous Score
        last_snapshot = (
            db.query(ScoreSnapshotModel)
            .filter(ScoreSnapshotModel.candidate_id == candidate.id)
            .order_by(ScoreSnapshotModel.created_at.desc())
            .first()
        )
        previous_score = last_snapshot.overall_score if last_snapshot else 0.0

        # 5. Deterministic Score Recalculation
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
            claims_by_req_id=reconciled_status_by_req,
            candidate_years_exp=candidate.years_experience,
            required_years_exp=role.min_years_experience if role else 0,
            weights={
                "must_have": role.weight_must_have if role else 0.65,
                "nice_to_have": role.weight_nice_to_have if role else 0.20,
                "experience": role.weight_experience if role else 0.15
            }
        )

        new_snapshot = ScoreSnapshotModel(
            candidate_id=candidate.id,
            overall_score=score_breakdown.overall_score,
            must_have_score=score_breakdown.must_have_score,
            nice_to_have_score=score_breakdown.nice_to_have_score,
            experience_score=score_breakdown.experience_score,
            formula_representation=score_breakdown.formula_representation,
            breakdown_json=score_breakdown.model_dump_json()
        )
        db.add(new_snapshot)

        # 6. Deterministic Gap Recalculation
        updated_gaps = GapDetector.detect_gaps(requirements=requirements, claims=reconciled_status_by_req)
        gaps_response = GapDetector.build_response(candidate_id=candidate.id, gaps=updated_gaps)

        # 7. Audit Logging
        session.status = InterviewSessionStatus.REVIEWED.value

        db.add(AuditEventModel(
            entity_type="INTERVIEW_EVIDENCE",
            entity_id=proposal.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.INTERVIEW_EVIDENCE_APPROVED.value,
            details_json=json.dumps({
                "session_id": session.id,
                "proposal_id": proposal.id,
                "requirement_id": proposal.requirement_id,
                "final_status": final_status.value,
                "is_overridden": is_overridden,
                "reason": final_reason
            })
        ))

        db.add(AuditEventModel(
            entity_type="CANDIDATE",
            entity_id=candidate.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.SCORE_RECALCULATED.value,
            details_json=json.dumps({
                "previous_score": previous_score,
                "new_score": score_breakdown.overall_score,
                "formula": score_breakdown.formula_representation
            })
        ))

        db.add(AuditEventModel(
            entity_type="CANDIDATE",
            entity_id=candidate.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.GAPS_RECALCULATED.value,
            details_json=json.dumps({
                "total_gaps": gaps_response.total_gaps,
                "critical_count": gaps_response.critical_count
            })
        ))

        db.commit()

        req_name = next((r.name for r in requirements if r.id == proposal.requirement_id), "Unknown")
        proposal_schema = InterviewEvidenceProposal(
            id=proposal.id,
            session_id=proposal.session_id,
            requirement_id=proposal.requirement_id,
            requirement_name=req_name,
            verbatim_excerpt=proposal.verbatim_excerpt,
            start_offset=proposal.start_offset,
            end_offset=proposal.end_offset,
            proposed_status=EvidenceStatus(proposal.proposed_status),
            justification=proposal.justification,
            confidence_score=proposal.confidence_score,
            review_status=proposal.review_status,
            recruiter_notes=proposal.recruiter_notes,
            created_at=proposal.created_at
        )

        return InterviewEvidenceConfirmResponse(
            proposal=proposal_schema,
            previous_score=previous_score,
            new_score=score_breakdown.overall_score,
            score_breakdown=score_breakdown,
            gaps_response=gaps_response,
            changed_requirement_id=proposal.requirement_id
        )

    @classmethod
    def reject_evidence_proposal(
        cls,
        db: Session,
        session_id: str,
        proposal_id: str,
        rejection_reason: str
    ) -> InterviewEvidenceProposal:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        proposal = db.query(InterviewEvidenceProposalModel).filter(
            InterviewEvidenceProposalModel.id == proposal_id,
            InterviewEvidenceProposalModel.session_id == session_id
        ).first()
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence proposal not found.")

        if not rejection_reason or len(rejection_reason.strip()) < 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection reason of at least 3 characters is required.")

        proposal.review_status = InterviewProposalStatus.REJECTED.value
        proposal.recruiter_notes = rejection_reason

        db.add(AuditEventModel(
            entity_type="INTERVIEW_EVIDENCE",
            entity_id=proposal.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.INTERVIEW_EVIDENCE_REJECTED.value,
            details_json=json.dumps({
                "session_id": session.id,
                "proposal_id": proposal.id,
                "reason": rejection_reason
            })
        ))
        db.commit()
        db.refresh(proposal)

        req_name = "Unknown"
        req = db.query(RequirementModel).filter(RequirementModel.id == proposal.requirement_id).first()
        if req:
            req_name = req.name

        return InterviewEvidenceProposal(
            id=proposal.id,
            session_id=proposal.session_id,
            requirement_id=proposal.requirement_id,
            requirement_name=req_name,
            verbatim_excerpt=proposal.verbatim_excerpt,
            start_offset=proposal.start_offset,
            end_offset=proposal.end_offset,
            proposed_status=EvidenceStatus(proposal.proposed_status),
            justification=proposal.justification,
            confidence_score=proposal.confidence_score,
            review_status=proposal.review_status,
            recruiter_notes=proposal.recruiter_notes,
            created_at=proposal.created_at
        )
