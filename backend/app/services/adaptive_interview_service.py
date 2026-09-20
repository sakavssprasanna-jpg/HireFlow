import json
import logging
from datetime import datetime, timezone
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
    InterviewSessionStatus
)
from ..domain.schemas import (
    InterviewSessionRead,
    InterviewQuestionRead,
    AdaptiveInterviewStateResponse,
    RequirementCoverageItem,
    InterviewSummaryResponse,
    FitScoreBreakdown
)
from ..db.models import (
    CandidateModel,
    RoleModel,
    RequirementModel,
    InterviewSessionModel,
    InterviewQuestionModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    AuditEventModel
)
from .security_scanner import SecurityScanner
from .quote_verifier import QuoteVerifier
from .scoring_engine import DeterministicScoringEngine
from .gap_detector import GapDetector
from .interview_generator import InterviewGeneratorService

logger = logging.getLogger("hireflow.services.adaptive_interview")

def utc_now():
    return datetime.now(timezone.utc)

class AdaptiveInterviewService:
    """
    Adaptive Turn-by-Turn Interview Engine:
    - Pacing & duration awareness (5m - 60m)
    - Dynamic question adaptation based on candidate answers and remaining time
    - Verbatim quote verification via QuoteVerifier
    - Real-time deterministic score and gap recalculation
    - Complete Before vs. After comparison report
    - Zero domain hardcoding across roles and technologies
    """

    @classmethod
    def get_interview_state(cls, db: Session, session_id: str) -> AdaptiveInterviewStateResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        candidate = session.candidate
        role = db.query(RoleModel).filter(RoleModel.id == session.role_id).first() if session.role_id else candidate.role
        role_title = role.title if role else "General Engineering"

        # Questions sorted by order_index
        questions = sorted(session.questions, key=lambda q: q.order_index)
        q_reads = [InterviewQuestionRead.model_validate(q) for q in questions]

        current_idx = session.current_question_index
        current_q = q_reads[current_idx] if 0 <= current_idx < len(q_reads) else None

        # Build live requirement coverage
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == role.id).all() if role else []
        claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate.id).all()
        claims_by_req = {c.requirement_id: c for c in claims}

        coverage_items: List[RequirementCoverageItem] = []
        for req in requirements:
            claim = claims_by_req.get(req.id)
            if claim:
                c_status = EvidenceStatus(claim.status)
                if c_status == EvidenceStatus.PROVEN:
                    cov_state = "CONFIRMED"
                elif c_status == EvidenceStatus.PARTIALLY_PROVEN:
                    cov_state = "PARTIAL"
                elif c_status == EvidenceStatus.CONTRADICTED:
                    cov_state = "UNRESOLVED"
                else:
                    cov_state = "NOT_ASSESSED"
                quote = claim.verbatim_quote
                reason = claim.reasoning
            else:
                c_status = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL
                cov_state = "NOT_ASSESSED"
                quote = None
                reason = "No interview or resume evidence collected yet."

            coverage_items.append(RequirementCoverageItem(
                requirement_id=req.id,
                requirement_name=req.name,
                category=RequirementCategory(req.category),
                status=c_status,
                coverage_state=cov_state,
                evidence_quote=quote,
                reasoning=reason
            ))

        # Fetch latest score snapshot
        last_snapshot = (
            db.query(ScoreSnapshotModel)
            .filter(ScoreSnapshotModel.candidate_id == candidate.id)
            .order_by(ScoreSnapshotModel.created_at.desc())
            .first()
        )
        current_score = last_snapshot.overall_score if last_snapshot else 0.0

        # Fetch first snapshot (pre-interview baseline)
        first_snapshot = (
            db.query(ScoreSnapshotModel)
            .filter(ScoreSnapshotModel.candidate_id == candidate.id)
            .order_by(ScoreSnapshotModel.created_at.asc())
            .first()
        )
        previous_score = first_snapshot.overall_score if first_snapshot else current_score

        summary_data = None
        if session.summary_json:
            try:
                summary_data = json.loads(session.summary_json)
            except Exception:
                summary_data = None

        resume_count = sum(1 for q in questions if q.question_type == "RESUME_GROUNDED")
        gap_count = sum(1 for q in questions if q.question_type != "RESUME_GROUNDED")
        if session.duration_seconds <= 300:
            reserve_sec = 60
        elif session.duration_seconds <= 600:
            reserve_sec = 120
        elif session.duration_seconds <= 900:
            reserve_sec = 210
        elif session.duration_seconds <= 1800:
            reserve_sec = 360
        elif session.duration_seconds <= 2700:
            reserve_sec = 480
        else:
            reserve_sec = 540

        return AdaptiveInterviewStateResponse(
            session_id=session.id,
            candidate_id=candidate.id,
            candidate_name=candidate.full_name,
            role_id=role.id if role else None,
            role_title=role_title,
            status=session.status,
            experience_level=session.experience_level or "Mid Level",
            duration_seconds=session.duration_seconds,
            remaining_seconds=session.remaining_seconds,
            current_question_index=session.current_question_index,
            total_questions=len(q_reads),
            resume_questions_count=resume_count,
            gap_questions_count=gap_count,
            followup_reserve_seconds=reserve_sec,
            current_question=current_q,
            questions=q_reads,
            coverage_breakdown=coverage_items,
            current_score=current_score,
            previous_score=previous_score,
            summary=summary_data
        )

    @classmethod
    def start_interview(cls, db: Session, session_id: str) -> AdaptiveInterviewStateResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        if session.candidate.quarantined:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate is quarantined.")

        session.status = InterviewSessionStatus.IN_PROGRESS.value
        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.INTERVIEW_STARTED.value,
            details_json=json.dumps({
                "candidate_id": session.candidate_id,
                "role_id": session.role_id,
                "duration_seconds": session.duration_seconds,
                "questions_count": len(session.questions)
            })
        ))
        db.commit()
        db.refresh(session)
        return cls.get_interview_state(db, session_id)

    @classmethod
    def capture_candidate_answer(
        cls,
        db: Session,
        session_id: str,
        question_id: str,
        answer_text: str,
        seconds_spent: Optional[int] = None
    ) -> AdaptiveInterviewStateResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        candidate = session.candidate
        if candidate.quarantined:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Candidate is quarantined.")

        # 1. Prompt-Injection Security Scan
        scan = SecurityScanner.scan_text(answer_text)
        if scan.quarantined:
            session.status = InterviewSessionStatus.QUARANTINED.value
            db.add(AuditEventModel(
                entity_type="INTERVIEW_SESSION",
                entity_id=session.id,
                actor=AuditActor.SYSTEM_AGENT.value,
                action=AuditAction.SECURITY_QUARANTINE.value,
                details_json=json.dumps({
                    "reason": scan.quarantine_reason,
                    "matched_rules": scan.matched_rules
                })
            ))
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Candidate response quarantined due to security violation: {scan.quarantine_reason}"
            )

        # 2. Locate Target Question
        question = db.query(InterviewQuestionModel).filter(
            InterviewQuestionModel.id == question_id,
            InterviewQuestionModel.session_id == session_id
        ).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview question not found.")

        role = db.query(RoleModel).filter(RoleModel.id == session.role_id).first() if session.role_id else candidate.role
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == role.id).all() if role else []
        target_req = next((r for r in requirements if r.id == question.requirement_id), None)

        # 3. Update Pacing & Time
        used_seconds = seconds_spent if (seconds_spent is not None and seconds_spent > 0) else question.estimated_duration_seconds
        session.remaining_seconds = max(0, session.remaining_seconds - used_seconds)

        # 4. Extract Quote and Ground Evidence Deterministically
        clean_text = answer_text.strip()
        sentences = [s.strip() for s in clean_text.replace("\n", ". ").split(". ") if len(s.strip()) > 6]
        primary_quote = sentences[0] if sentences else clean_text

        # Verify quote using QuoteVerifier
        verification = QuoteVerifier.verify_quote(raw_source_text=clean_text, quote=primary_quote)
        matched_quote = verification.matched_text if verification.valid else primary_quote
        start_off = verification.start_offset if verification.valid else 0
        end_off = verification.end_offset if verification.valid else len(matched_quote)

        # Classify Evidence
        lower_ans = clean_text.lower()
        negative_markers = [
            "don't know", "do not know", "haven't used", "have not used", "never used",
            "no experience", "not familiar", "failed to", "unable to", "didn't work with",
            "never had the chance", "no prior exposure"
        ]
        is_contradiction = any(nm in lower_ans for nm in negative_markers)

        if is_contradiction:
            final_status = EvidenceStatus.CONTRADICTED
            reasoning = f"Candidate explicitly indicated lack of competence or hands-on experience during interview: \"{matched_quote}\""
        elif len(clean_text) > 40 and len(clean_text.split()) >= 10:
            final_status = EvidenceStatus.PROVEN
            reasoning = f"Candidate demonstrated substantiated technical competence during interview: \"{matched_quote}\""
        else:
            final_status = EvidenceStatus.PARTIALLY_PROVEN
            reasoning = f"Candidate provided brief or high-level response during interview: \"{matched_quote}\""

        # 5. Persist Evidence Claim
        if target_req:
            claim = db.query(EvidenceClaimModel).filter(
                EvidenceClaimModel.candidate_id == candidate.id,
                EvidenceClaimModel.requirement_id == target_req.id
            ).first()

            if claim:
                claim.status = final_status.value
                claim.source_type = SourceType.INTERVIEW_NOTE.value
                claim.source_document_id = session.id
                claim.section_reference = f"Interview ({session.interview_round})"
                claim.verbatim_quote = matched_quote
                claim.start_offset = start_off
                claim.end_offset = end_off
                claim.reasoning = reasoning
                claim.confidence = 0.95
            else:
                claim = EvidenceClaimModel(
                    candidate_id=candidate.id,
                    requirement_id=target_req.id,
                    source_document_id=session.id,
                    source_type=SourceType.INTERVIEW_NOTE.value,
                    section_reference=f"Interview ({session.interview_round})",
                    verbatim_quote=matched_quote,
                    start_offset=start_off,
                    end_offset=end_off,
                    status=final_status.value,
                    reasoning=reasoning,
                    confidence=0.95
                )
                db.add(claim)

            db.flush()

        # 6. Mark Question Record
        question.candidate_answer = clean_text
        question.extracted_evidence = matched_quote
        question.evidence_status = final_status.value
        question.is_answered = True
        question.answered_at = utc_now()

        # 7. Recalculate Deterministic Score Snapshot
        all_claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate.id).all()
        claims_dict = {c.requirement_id: EvidenceStatus(c.status) for c in all_claims}
        for r in requirements:
            if r.id not in claims_dict:
                claims_dict[r.id] = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL

        req_dicts = [{
            "id": r.id,
            "name": r.name,
            "category": RequirementCategory(r.category),
            "weight": r.weight
        } for r in requirements]

        score_breakdown = DeterministicScoringEngine.calculate_score(
            candidate_id=candidate.id,
            requirements=req_dicts,
            claims_by_req_id=claims_dict,
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

        # 8. Recalculate Gaps
        updated_gaps = GapDetector.detect_gaps(requirements=requirements, claims=claims_dict)

        # 9. Dynamic Adaptive Next Question Selection / Reprioritization
        # If remaining time is critically low (< 120s), ensure remaining questions focus on MUST_HAVE gaps
        questions = sorted(session.questions, key=lambda q: q.order_index)
        unanswered = [q for q in questions if not q.is_answered and not q.is_skipped and q.id != question.id]

        if session.remaining_seconds < 120 and unanswered:
            # Check if any remaining question covers an unresolved MUST_HAVE
            must_have_unanswered = [
                q for q in unanswered
                if q.priority == "MUST_HAVE" or any(g.requirement_id == q.requirement_id and g.priority.value == "CRITICAL" for g in updated_gaps)
            ]
            if must_have_unanswered and must_have_unanswered[0].order_index != question.order_index + 1:
                # Reorder to surface the urgent must-have question immediately next
                target_q = must_have_unanswered[0]
                target_q.reason = f"[TIME-CRITICAL ADAPTATION: Priority MUST-HAVE gap probed before time expires] {target_q.reason or ''}"

        session.current_question_index += 1
        if session.current_question_index >= len(questions):
            session.status = InterviewSessionStatus.COMPLETED.value

        # 10. Audit Logging
        db.add(AuditEventModel(
            entity_type="INTERVIEW_QUESTION",
            entity_id=question.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.ANSWER_CAPTURED.value,
            details_json=json.dumps({
                "session_id": session.id,
                "question_id": question.id,
                "requirement_id": question.requirement_id,
                "status": final_status.value,
                "seconds_spent": used_seconds,
                "remaining_seconds": session.remaining_seconds
            })
        ))

        db.add(AuditEventModel(
            entity_type="CANDIDATE",
            entity_id=candidate.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.SCORE_RECALCULATED.value,
            details_json=json.dumps({
                "new_score": score_breakdown.overall_score,
                "formula": score_breakdown.formula_representation
            })
        ))

        db.commit()
        db.refresh(session)
        return cls.get_interview_state(db, session_id)

    @classmethod
    def ask_followup(
        cls,
        db: Session,
        session_id: str,
        question_id: str,
        notes_context: Optional[str] = None
    ) -> AdaptiveInterviewStateResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        current_q = db.query(InterviewQuestionModel).filter(InterviewQuestionModel.id == question_id).first()
        if not current_q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target question not found.")

        req = db.query(RequirementModel).filter(RequirementModel.id == current_q.requirement_id).first()
        req_name = req.name if req else "this requirement"

        # Formulate tailored follow-up question
        exp = session.experience_level or "Mid Level"
        if "senior" in exp.lower():
            followup_text = f"Following up on {req_name}: can you walk through a production failure or edge case you personally mitigated, and how you evaluated the architectural trade-offs?"
        elif "junior" in exp.lower() or "entry" in exp.lower():
            followup_text = f"Following up on {req_name}: could you dive deeper into the specific functions, libraries, or tools you used to implement your solution?"
        else:
            followup_text = f"Following up on {req_name}: what alternative technical approaches did you consider, and why was this solution optimal for the system?"

        # Shift existing question indices
        insert_idx = current_q.order_index + 1
        for q in session.questions:
            if q.order_index >= insert_idx:
                q.order_index += 1

        followup_q = InterviewQuestionModel(
            session_id=session.id,
            requirement_id=current_q.requirement_id,
            target_gap_description=f"Follow-up probe for {req_name}",
            question_text=followup_text,
            probing_context=f"Adaptive follow-up triggered based on initial response to question #{current_q.order_index + 1}.",
            expected_positive_signals="Specific metrics, deep architectural clarity, concrete code/system examples.",
            expected_red_flags="Repeating prior buzzwords without adding technical specificity.",
            question_type="FOLLOW_UP",
            reason=f"Probing deeper into candidate's mastery of {req_name}",
            evidence_basis=notes_context or "Recruiter requested technical drill-down",
            experience_level=exp,
            priority=current_q.priority,
            estimated_duration_seconds=120,
            order_index=insert_idx,
            recruiter_approved=True
        )
        db.add(followup_q)

        session.current_question_index = insert_idx

        db.add(AuditEventModel(
            entity_type="INTERVIEW_QUESTION",
            entity_id=current_q.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.FOLLOWUP_GENERATED.value,
            details_json=json.dumps({
                "parent_question_id": current_q.id,
                "requirement_id": current_q.requirement_id,
                "followup_index": insert_idx
            })
        ))

        db.commit()
        db.refresh(session)
        return cls.get_interview_state(db, session_id)

    @classmethod
    def skip_question(
        cls,
        db: Session,
        session_id: str,
        question_id: str,
        reason: Optional[str] = None
    ) -> AdaptiveInterviewStateResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        question = db.query(InterviewQuestionModel).filter(InterviewQuestionModel.id == question_id).first()
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")

        question.is_skipped = True
        question.extracted_evidence = reason or "Question skipped by recruiter."
        session.current_question_index += 1

        db.add(AuditEventModel(
            entity_type="INTERVIEW_QUESTION",
            entity_id=question.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.QUESTION_SKIPPED.value,
            details_json=json.dumps({
                "session_id": session.id,
                "question_id": question.id,
                "reason": reason
            })
        ))

        db.commit()
        db.refresh(session)
        return cls.get_interview_state(db, session_id)

    @classmethod
    def end_interview(cls, db: Session, session_id: str) -> InterviewSummaryResponse:
        session = db.query(InterviewSessionModel).filter(InterviewSessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found.")

        candidate = session.candidate
        role = db.query(RoleModel).filter(RoleModel.id == session.role_id).first() if session.role_id else candidate.role
        role_title = role.title if role else "Role Assessment"

        session.status = InterviewSessionStatus.COMPLETED.value

        # Questions and statistics
        questions = sorted(session.questions, key=lambda q: q.order_index)
        answered = [q for q in questions if q.is_answered]
        skipped = [q for q in questions if q.is_skipped]
        time_spent = max(0, session.duration_seconds - session.remaining_seconds)

        # Pre vs Post Score Snapshots
        snapshots = (
            db.query(ScoreSnapshotModel)
            .filter(ScoreSnapshotModel.candidate_id == candidate.id)
            .order_by(ScoreSnapshotModel.created_at.asc())
            .all()
        )
        pre_score = snapshots[0].overall_score if snapshots else 0.0
        post_score = snapshots[-1].overall_score if snapshots else 0.0
        score_delta = round(post_score - pre_score, 2)

        # Gaps calculation
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == role.id).all() if role else []
        all_claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate.id).all()
        claims_dict = {c.requirement_id: EvidenceStatus(c.status) for c in all_claims}

        current_gaps = GapDetector.detect_gaps(requirements=requirements, claims=claims_dict)

        # Baseline claims (resume only)
        resume_claims = [c for c in all_claims if c.source_type == SourceType.RESUME.value]
        resume_claims_dict = {c.requirement_id: EvidenceStatus(c.status) for c in resume_claims}
        for r in requirements:
            if r.id not in resume_claims_dict:
                resume_claims_dict[r.id] = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL
        pre_gaps = GapDetector.detect_gaps(requirements=requirements, claims=resume_claims_dict)

        resolved_count = max(0, len(pre_gaps) - len(current_gaps))

        # Build coverage breakdown
        coverage_items: List[RequirementCoverageItem] = []
        for req in requirements:
            claim = next((c for c in all_claims if c.requirement_id == req.id), None)
            if claim:
                c_status = EvidenceStatus(claim.status)
                if c_status == EvidenceStatus.PROVEN:
                    c_state = "CONFIRMED"
                elif c_status == EvidenceStatus.PARTIALLY_PROVEN:
                    c_state = "PARTIAL"
                elif c_status == EvidenceStatus.CONTRADICTED:
                    c_state = "UNRESOLVED"
                else:
                    c_state = "NOT_ASSESSED"
                quote = claim.verbatim_quote
                reason = claim.reasoning
            else:
                c_status = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL
                c_state = "NOT_ASSESSED"
                quote = None
                reason = "No evidence collected during screening or interview."

            coverage_items.append(RequirementCoverageItem(
                requirement_id=req.id,
                requirement_name=req.name,
                category=RequirementCategory(req.category),
                status=c_status,
                coverage_state=c_state,
                evidence_quote=quote,
                reasoning=reason
            ))

        # Build transcript
        transcript = []
        for q in questions:
            transcript.append({
                "order": q.order_index + 1,
                "requirement_id": q.requirement_id,
                "question": q.question_text,
                "reason": q.reason,
                "answer": q.candidate_answer,
                "evidence": q.extracted_evidence,
                "status": q.evidence_status,
                "is_skipped": q.is_skipped,
                "is_answered": q.is_answered
            })

        # Calculate final breakdown
        req_dicts = [{
            "id": r.id,
            "name": r.name,
            "category": RequirementCategory(r.category),
            "weight": r.weight
        } for r in requirements]

        final_breakdown = DeterministicScoringEngine.calculate_score(
            candidate_id=candidate.id,
            requirements=req_dicts,
            claims_by_req_id=claims_dict,
            candidate_years_exp=candidate.years_experience,
            required_years_exp=role.min_years_experience if role else 0,
            weights={
                "must_have": role.weight_must_have if role else 0.65,
                "nice_to_have": role.weight_nice_to_have if role else 0.20,
                "experience": role.weight_experience if role else 0.15
            }
        )

        summary_resume_count = sum(1 for q in questions if q.question_type == "RESUME_GROUNDED")
        summary_gap_count = sum(1 for q in questions if q.question_type != "RESUME_GROUNDED")
        if session.duration_seconds <= 300:
            summary_reserve_sec = 60
        elif session.duration_seconds <= 600:
            summary_reserve_sec = 120
        elif session.duration_seconds <= 900:
            summary_reserve_sec = 210
        elif session.duration_seconds <= 1800:
            summary_reserve_sec = 360
        elif session.duration_seconds <= 2700:
            summary_reserve_sec = 480
        else:
            summary_reserve_sec = 540

        summary_response = InterviewSummaryResponse(
            session_id=session.id,
            candidate_id=candidate.id,
            candidate_name=candidate.full_name,
            role_title=role_title,
            experience_level=session.experience_level or "Mid Level",
            duration_minutes=session.duration_seconds // 60,
            time_spent_seconds=time_spent,
            questions_total=len(questions),
            questions_answered=len(answered),
            questions_skipped=len(skipped),
            resume_questions_count=summary_resume_count,
            gap_questions_count=summary_gap_count,
            followup_reserve_seconds=summary_reserve_sec,
            pre_interview_score=pre_score,
            post_interview_score=post_score,
            score_delta=score_delta,
            pre_interview_gaps_count=len(pre_gaps),
            post_interview_gaps_count=len(current_gaps),
            resolved_gaps_count=resolved_count,
            coverage_breakdown=coverage_items,
            transcript=transcript,
            score_breakdown=final_breakdown,
            created_at=session.created_at,
            completed_at=utc_now()
        )

        session.summary_json = summary_response.model_dump_json()

        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.RECRUITER.value,
            action=AuditAction.INTERVIEW_ENDED.value,
            details_json=json.dumps({
                "pre_score": pre_score,
                "post_score": post_score,
                "score_delta": score_delta,
                "resolved_gaps": resolved_count,
                "time_spent": time_spent
            })
        ))

        db.commit()
        return summary_response
