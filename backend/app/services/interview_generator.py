import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..domain.enums import AuditAction, AuditActor, AIMode, InterviewSessionStatus
from ..domain.schemas import (
    InterviewQuestionOutput,
    InterviewSessionRead,
    InterviewQuestionRead
)
from ..db.models import (
    CandidateModel,
    CandidateDocumentModel,
    RoleModel,
    RequirementModel,
    EvidenceClaimModel,
    InterviewSessionModel,
    InterviewQuestionModel,
    AuditEventModel
)
from ..ai.factory import get_llm_provider
from ..ai.base import ProviderError
from .gap_detector import GapDetector

logger = logging.getLogger("hireflow.services.interview_generator")

@dataclass
class ResumeEvidenceAnchor:
    evidence_id: str
    candidate_id: str
    source_document: str
    verbatim_quote: str
    related_requirement_id: Optional[str] = None
    related_requirement_name: Optional[str] = None
    evidence_status: str = "EXTRACTED"
    relevance_score: float = 0.5
    importance: str = "MEDIUM"  # HIGH | MEDIUM | LOW
    topic_category: str = "General Experience"

def extract_resume_evidence_pool(
    candidate: CandidateModel,
    role: RoleModel,
    requirements: List[RequirementModel],
    claims: List[EvidenceClaimModel],
    doc_record: Optional[CandidateDocumentModel]
) -> List[ResumeEvidenceAnchor]:
    pool: List[ResumeEvidenceAnchor] = []
    seen_quotes: Set[str] = set()
    candidate_id = candidate.id
    source_doc = doc_record.filename if doc_record and doc_record.filename else "Candidate Resume"

    # Pre-index requirements for quick keyword lookup
    req_by_id = {r.id: r for r in requirements}
    req_keywords = {}
    for r in requirements:
        tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', (r.name + " " + (r.description or "")).lower()))
        req_keywords[r.id] = (r, tokens)

    role_title_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', role.title.lower())) if role.title else set()

    # 1. Ingest verified/partially-verified claims from EvidenceClaimModel
    for idx, c in enumerate(claims):
        if not c.verbatim_quote:
            continue
        clean_q = c.verbatim_quote.strip()
        if len(clean_q) < 15 or c.status == "NOT_FOUND_IN_PROVIDED_MATERIAL":
            continue
        clean_q_lower = clean_q.lower()
        if any(neg in clean_q_lower for neg in [
            "did not document", "does not document", "not documented",
            "no documented", "lacks experience", "no experience",
            "not found in", "missing documentation", "no evidence"
        ]) or any(clean_q_lower.startswith(neg) for neg in [
            "did not ", "does not ", "do not ", "lacks ", "lacking ", "no ", "without "
        ]):
            continue
        if clean_q_lower in seen_quotes:
            continue
        seen_quotes.add(clean_q_lower)

        matched_req = req_by_id.get(c.requirement_id)
        is_must = matched_req.category == "MUST_HAVE" if matched_req else False
        importance = "HIGH" if is_must else "MEDIUM"
        relevance = 1.0 if is_must else 0.85
        category = matched_req.name if matched_req else (c.requirement_name or "Verified Competency")

        pool.append(ResumeEvidenceAnchor(
            evidence_id=f"claim-{c.id or idx}",
            candidate_id=candidate_id,
            source_document=source_doc,
            verbatim_quote=clean_q,
            related_requirement_id=c.requirement_id,
            related_requirement_name=matched_req.name if matched_req else c.requirement_name,
            evidence_status=c.status,
            relevance_score=relevance,
            importance=importance,
            topic_category=category
        ))

    # 2. Extract candidate resume sentences, projects, and bullet points
    raw_text = doc_record.raw_text if doc_record and doc_record.raw_text else ""
    if not raw_text and candidate.documents and len(candidate.documents) > 0:
        raw_text = candidate.documents[0].raw_text or ""

    if raw_text:
        raw_lines = raw_text.splitlines()
        extracted_segments = []
        for line in raw_lines:
            line_str = line.strip()
            if not line_str:
                continue
            # Split line into sentences if multiple exist (preserving decimals like 99.9%)
            sentences = re.split(r'(?<=[.!?;])\s+(?=[A-Z0-9\-\*•])', line_str)
            for s in sentences:
                cleaned = s.strip().lstrip("-*•# \t0123456789.)").strip()
                if len(cleaned) >= 20:
                    extracted_segments.append(cleaned)

        for s_idx, segment in enumerate(extracted_segments):
            seg_lower = segment.lower()
            # Filter contact / boilerplate
            if any(stop in seg_lower for stop in ["http", "www.", "@", "phone:", "email:", "curriculum vitae", "references upon request"]):
                continue
            # Filter negative statements, lack of evidence, or gap phrases
            if any(neg in seg_lower for neg in [
                "did not document", "does not document", "not documented",
                "no documented", "lacks experience", "no experience",
                "not found in", "missing documentation", "no evidence"
            ]) or any(seg_lower.startswith(neg) for neg in [
                "did not ", "does not ", "do not ", "lacks ", "lacking ", "no ", "without "
            ]):
                continue
            # Avoid duplicate quotes
            if any(seg_lower in sq or sq in seg_lower for sq in seen_quotes):
                continue
            seen_quotes.add(seg_lower)

            seg_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', seg_lower))
            if not seg_tokens:
                continue

            # Check relevance against requirements
            best_req = None
            best_overlap = 0
            for r_id, (r_obj, r_tokens) in req_keywords.items():
                overlap = len(seg_tokens & r_tokens)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_req = r_obj

            role_overlap = len(seg_tokens & role_title_tokens)

            if best_req and best_overlap >= 1:
                is_must = best_req.category == "MUST_HAVE"
                rel_score = 0.90 if is_must else 0.75
                imp = "HIGH" if is_must else "MEDIUM"
                cat = best_req.name
                req_id = best_req.id
                req_name = best_req.name
            elif role_overlap >= 1:
                rel_score = 0.70
                imp = "MEDIUM"
                cat = role.title
                req_id = None
                req_name = None
            else:
                rel_score = 0.50
                imp = "LOW"
                cat = "Project Experience"
                req_id = None
                req_name = None

            pool.append(ResumeEvidenceAnchor(
                evidence_id=f"seg-{s_idx}",
                candidate_id=candidate_id,
                source_document=source_doc,
                verbatim_quote=segment,
                related_requirement_id=req_id,
                related_requirement_name=req_name,
                evidence_status="EXTRACTED",
                relevance_score=rel_score,
                importance=imp,
                topic_category=cat
            ))

    # Sort pool: highest relevance and importance first
    pool.sort(key=lambda a: (a.relevance_score, 1 if a.importance == "HIGH" else 0, len(a.verbatim_quote)), reverse=True)
    return pool

def compute_interview_question_mix(
    target_count: int,
    duration_minutes: int,
    evidence_pool: List[ResumeEvidenceAnchor],
    gaps_count: int,
) -> Tuple[int, int]:
    """
    Intelligently allocates question count between Resume-Grounded and Gap-Validation.
    Respects evidence density and prevents repetitive questioning on sparse evidence.
    """
    pool_size = len(evidence_pool)
    if pool_size == 0:
        return 0, target_count

    # Determine baseline target resume questions based on duration targets:
    # 5m: 1 resume | 10m: 2 resume | 15m: 3 resume | 30m: 6 resume | 45m: 8 resume
    if duration_minutes <= 5:
        target_resume = 1
    elif duration_minutes <= 10:
        target_resume = 2
    elif duration_minutes <= 15:
        target_resume = 3
    elif duration_minutes <= 30:
        target_resume = 6
    elif duration_minutes <= 45:
        target_resume = 8
    else:
        target_resume = target_count // 2

    # Capacity check: each anchor supports up to 2 distinct dimensions without repetition
    max_resume_capacity = pool_size * 2
    target_resume = min(target_resume, max_resume_capacity)

    # Ensure at least 1 gap question if gaps exist
    if gaps_count > 0:
        target_resume = min(target_resume, target_count - 1)

    target_resume = max(1, target_resume)

    # If gaps are very few (e.g. <= 1) and evidence pool is rich:
    if gaps_count <= 1 and pool_size >= 3 and duration_minutes >= 15:
        target_resume = min(max_resume_capacity, target_count - max(1, gaps_count))

    target_gap = target_count - target_resume
    return target_resume, target_gap

class InterviewGeneratorService:
    """
    AI-driven interview question generator strictly conditioned on candidate competency gaps.
    Enforces the grounding invariant: every question must link directly to a role requirement.
    """

    @classmethod
    async def generate_interview_questions(
        cls,
        db: Session,
        candidate_id: str,
        ai_mode: Optional[AIMode] = None,
        max_questions: int = 5,
        focus_gaps_only: bool = True
    ) -> InterviewSessionRead:
        # 1. Fetch Candidate
        candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate '{candidate_id}' not found.")

        # SECURITY INVARIANT: Quarantined candidates cannot generate interview sessions
        if candidate.quarantined:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Candidate document is quarantined ({candidate.quarantine_reason}). Interview generation is prohibited."
            )

        # 2. Fetch Requirements and Existing Claims
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == candidate.role_id).all()
        if not requirements:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No requirements configured for this role.")

        claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate_id).all()

        # 3. Detect Gaps using Deterministic GapDetector
        gaps = GapDetector.detect_gaps(requirements=requirements, claims=claims)

        # Build prompt listing specific gaps to probe
        req_by_id = {r.id: r for r in requirements}
        req_by_name_lower = {r.name.lower(): r for r in requirements}

        if gaps:
            gap_lines = []
            for g in gaps[:max_questions]:
                gap_lines.append(f"- GAP: {g.requirement_name} | PRIORITY: {g.priority.value} | REASON: {g.reason}")
            gaps_block = "\n".join(gap_lines)
            criteria_prompt = f"TARGET CANDIDATE GAPS TO PROBE:\n{gaps_block}\n"
        else:
            # Candidate has zero gaps! Probe top requirements for technical depth
            req_lines = [f"- REQUIREMENT: {r.name} | DESCRIPTION: {r.description}" for r in requirements[:max_questions]]
            criteria_prompt = f"CANDIDATE MET MINIMUM REQUIREMENTS. PROBE ARCHITECTURAL DEPTH FOR:\n" + "\n".join(req_lines)

        full_prompt = (
            f"{criteria_prompt}\n"
            f"Generate up to {max_questions} targeted, high-signal technical interview questions. "
            f"Each question must probe real candidate depth, design choices, and failure modes."
        )

        system_instruction = (
            "You are a principal technical interviewer at a top technology company. "
            "Formulate deep, behaviorally-anchored, and technically specific interview questions. "
            "For each question, specify the target gap, the question text, the probing context, "
            "expected positive signals (strong candidate indicators), and expected red flags (concerning candidate indicators). "
            "Never ask generic trivia. Ground every question in real engineering trade-offs."
        )

        # 4. Invoke AI Provider
        provider = get_llm_provider(ai_mode)
        try:
            response = await provider.generate_structured(
                prompt=full_prompt,
                schema=InterviewQuestionOutput,
                system_instruction=system_instruction
            )
            output: InterviewQuestionOutput = response.data
            meta = response.metadata
        except ProviderError as pe:
            logger.warning(f"AI Provider error ({pe}); falling back to deterministic offline question generator.")
            fallback_provider = get_llm_provider(AIMode.OFFLINE_FALLBACK)
            response = await fallback_provider.generate_structured(
                prompt=full_prompt,
                schema=InterviewQuestionOutput,
                system_instruction=system_instruction
            )
            output = response.data
            meta = response.metadata

        # 5. Persist Session & Questions with Grounding Enforcement
        session = InterviewSessionModel(
            candidate_id=candidate.id,
            interviewer_name="Recruiter",
            interview_round="TECHNICAL_SCREEN",
            raw_notes=f"Generated via {meta.provider_name} ({meta.model_name})"
        )
        db.add(session)
        db.flush()

        question_records: List[InterviewQuestionModel] = []

        for q in output.questions[:max_questions]:
            # Link to requirement
            matched_req = req_by_name_lower.get(q.requirement_name.lower())
            if not matched_req:
                # Substring match
                for r_name_lower, r_obj in req_by_name_lower.items():
                    if q.requirement_name.lower() in r_name_lower or r_name_lower in q.requirement_name.lower():
                        matched_req = r_obj
                        break

            # Fallback grounding: ensure requirement_id is NEVER null/orphan
            req_id = matched_req.id if matched_req else (gaps[0].requirement_id if gaps else requirements[0].id)

            q_record = InterviewQuestionModel(
                session_id=session.id,
                requirement_id=req_id,
                target_gap_description=q.target_gap,
                question_text=q.question,
                probing_context=q.probing_context,
                expected_positive_signals=q.positive_signals,
                expected_red_flags=q.red_flags,
                recruiter_approved=True
            )
            db.add(q_record)
            question_records.append(q_record)

        # 6. Audit Logging
        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.INTERVIEW_GENERATED.value,
            details_json=json.dumps({
                "candidate_id": candidate.id,
                "questions_count": len(question_records),
                "provider": meta.provider_name,
                "is_fallback": meta.is_fallback
            })
        ))

        db.commit()
        db.refresh(session)

        return InterviewSessionRead(
            id=session.id,
            candidate_id=session.candidate_id,
            interviewer_name=session.interviewer_name,
            interview_round=session.interview_round,
            raw_notes=session.raw_notes,
            created_at=session.created_at,
            questions=[InterviewQuestionRead.model_validate(qr) for qr in question_records]
        )

    @classmethod
    async def generate_adaptive_interview_plan(
        cls,
        db: Session,
        candidate_id: str,
        role_id: Optional[str] = None,
        experience_level: str = "Mid Level",
        duration_minutes: int = 15,
        ai_mode: Optional[AIMode] = None
    ) -> InterviewSessionModel:
        """
        Generates a personalized, time-aware interview plan conditioned on:
        1. Candidate's actual resume (CandidateDocumentModel.raw_text)
        2. Role's actual Job Description (RoleModel.raw_jd_text)
        3. Configured Role Criteria (RoleModel.requirements)
        4. Selected Experience Level (Entry, Junior, Mid, Senior, Custom)
        5. Selected Duration (5 - 60 minutes)
        
        Guarantees zero domain hardcoding across roles and technologies.
        """
        # 1. Fetch Candidate
        candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate '{candidate_id}' not found.")

        # SECURITY INVARIANT: Quarantined candidates cannot generate interview sessions
        if candidate.quarantined:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Candidate document is quarantined ({candidate.quarantine_reason}). Interview generation is prohibited."
            )

        # 2. Determine Role
        effective_role_id = role_id or candidate.role_id
        role = db.query(RoleModel).filter(RoleModel.id == effective_role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{effective_role_id}' not found.")

        # 3. Fetch Requirements and Existing Claims
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == role.id).all()
        if not requirements:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No evaluation criteria configured for this role.")

        claims = db.query(EvidenceClaimModel).filter(EvidenceClaimModel.candidate_id == candidate.id).all()

        # 4. Detect Gaps using Deterministic GapDetector
        gaps = GapDetector.detect_gaps(requirements=requirements, claims=claims)
        req_by_id = {r.id: r for r in requirements}
        req_by_name_lower = {r.name.lower(): r for r in requirements}

        # 5. Question Pacing & Time Allocation
        duration_minutes = max(5, min(60, duration_minutes))
        planned_duration_seconds = duration_minutes * 60

        # Reserve follow-up buffer (~15-20% of duration)
        if duration_minutes <= 5:
            followup_reserve_seconds = 60
            target_question_count = 2
        elif duration_minutes <= 10:
            followup_reserve_seconds = 120
            target_question_count = 4
        elif duration_minutes <= 15:
            followup_reserve_seconds = 210
            target_question_count = 7
        elif duration_minutes <= 30:
            followup_reserve_seconds = 360
            target_question_count = 12
        elif duration_minutes <= 45:
            followup_reserve_seconds = 480
            target_question_count = 16
        else:
            followup_reserve_seconds = 540
            target_question_count = min(20, max(16, int(duration_minutes / 2.5)))

        # Effective seconds for questions
        effective_seconds = max(180, planned_duration_seconds - followup_reserve_seconds)
        base_estimated_duration = max(60, effective_seconds // target_question_count)
        if duration_minutes <= 5:
            base_estimated_duration = planned_duration_seconds // target_question_count  # 150s

        # 6. Extract Candidate Resume Grounding Material & Role JD
        doc_record = (
            db.query(CandidateDocumentModel)
            .filter(CandidateDocumentModel.candidate_id == candidate.id)
            .order_by(CandidateDocumentModel.created_at.desc())
            .first()
        )
        resume_raw = doc_record.raw_text if doc_record and doc_record.raw_text else ""
        if not resume_raw and candidate.documents and len(candidate.documents) > 0:
            resume_raw = candidate.documents[0].raw_text or ""

        # Build internal resume evidence pool
        resume_evidence_pool = extract_resume_evidence_pool(
            candidate=candidate,
            role=role,
            requirements=requirements,
            claims=claims,
            doc_record=doc_record
        )

        # Dynamic allocation based on duration, pool size, and gaps
        target_resume_count, target_gap_count = compute_interview_question_mix(
            target_count=target_question_count,
            duration_minutes=duration_minutes,
            evidence_pool=resume_evidence_pool,
            gaps_count=len(gaps)
        )

        anchor_lines = []
        for a in resume_evidence_pool[:12]:
            anchor_lines.append(f"- ANCHOR [{a.importance} | {a.topic_category}]: \"{a.verbatim_quote}\"")
        anchors_display = "\n".join(anchor_lines) if anchor_lines else (resume_raw[:1500] if resume_raw else "No explicit candidate resume anchors found.")

        jd_excerpt = role.raw_jd_text[:1500] if role.raw_jd_text else f"Role: {role.title} in {role.department or 'Engineering'}"

        gap_lines = []
        for g in gaps:
            gap_lines.append(f"- GAP: {g.requirement_name} | PRIORITY: {g.priority.value} | REASON: {g.reason}")

        req_lines = []
        for r in requirements:
            req_lines.append(f"- REQUIREMENT: {r.name} | CATEGORY: {r.category} | DESCRIPTION: {r.description or 'None'}")

        exp_instructions = {
            "entry level": "Focus on foundational concepts, syntax, basic problem-solving, coursework/internship projects, and theoretical clarity. Probe enthusiasm and ability to learn.",
            "junior": "Focus on hands-on implementation, debugging runtime errors, working within established codebases, and writing maintainable code.",
            "mid level": "Focus on technical trade-offs, architecture decisions, edge cases, failure scenarios, and independent ownership of production services.",
            "senior": "Focus on high-scale distributed architecture, resilience, high availability, performance bottlenecks, technical leadership, and organizational business impact."
        }
        exp_guide = exp_instructions.get(experience_level.lower(), f"Target technical depth suitable for {experience_level} candidate.")

        full_prompt = (
            f"ROLE TITLE: {role.title}\n"
            f"EXPERIENCE LEVEL: {experience_level}\n"
            f"INTERVIEW DURATION: {duration_minutes} minutes (Reserve: {followup_reserve_seconds}s for adaptive follow-ups)\n"
            f"TARGET QUESTION COUNT: {target_question_count}\n"
            f"REQUIRED MIX: Exactly {target_resume_count} RESUME_GROUNDED questions and {target_gap_count} GAP_VALIDATION questions.\n\n"
            f"ROLE EVALUATION CRITERIA:\n" + "\n".join(req_lines) + "\n\n"
            f"IDENTIFIED CANDIDATE GAPS TO INVESTIGATE:\n" + ("\n".join(gap_lines) if gap_lines else "None documented - probe architectural depth.") + "\n\n"
            f"CANDIDATE RESUME EVIDENCE POOL (IDENTIFIED ANCHORS):\n{anchors_display}\n\n"
            f"JOB DESCRIPTION SUMMARY:\n{jd_excerpt}\n\n"
            f"INSTRUCTIONS:\n"
            f"Generate exactly {target_question_count} targeted, behaviorally-anchored technical questions with the REQUIRED MIX.\n"
            f"1. RESUME_GROUNDED questions ({target_resume_count} total): Formulate across the identified resume anchors and vary the question dimensions (Ownership, Implementation, Trade-offs, Scale, Metrics). Set evidence_basis to the exact anchor quote.\n"
            f"2. GAP_VALIDATION questions ({target_gap_count} total): Target missing criteria or unverified areas. Set evidence_basis='Role Requirement Gap' and probe hands-on ability.\n"
            f"3. Tailor technical depth specifically for {experience_level}: {exp_guide}\n"
            f"4. Assign variable estimated_duration_seconds to each question (e.g. 60s for short validation, 90-120s for standard, 150-180s for deep technical trade-offs).\n"
            f"5. Under no circumstances inject hardcoded technology names not present in the role criteria or resume."
        )

        system_instruction = (
            "You are an expert technical interviewer and talent architect. "
            "Formulate deep, highly relevant, personalized interview questions grounded in both the candidate's resume accomplishments and the role requirements/gaps. "
            "You must generate both RESUME_GROUNDED questions (probing real achievements from the resume) and GAP_VALIDATION questions (probing unverified criteria). "
            "Never ask generic trivia. For each question, specify requirement_name, target_gap, question, probing_context, positive_signals, red_flags, "
            "question_type ('RESUME_GROUNDED' or 'GAP_VALIDATION'), reason, evidence_basis, and estimated_duration_seconds. Strictly conform to the schema."
        )

        # 7. Invoke AI Provider with Fallback
        provider = get_llm_provider(ai_mode)
        try:
            response = await provider.generate_structured(
                prompt=full_prompt,
                schema=InterviewQuestionOutput,
                system_instruction=system_instruction
            )
            output: InterviewQuestionOutput = response.data
            meta = response.metadata
        except ProviderError as pe:
            logger.warning(f"AI Provider error ({pe}); utilizing deterministic fallback for adaptive plan.")
            fallback_provider = get_llm_provider(AIMode.OFFLINE_FALLBACK)
            response = await fallback_provider.generate_structured(
                prompt=full_prompt,
                schema=InterviewQuestionOutput,
                system_instruction=system_instruction
            )
            output = response.data
            meta = response.metadata

        # 8. Persist Interview Session & Questions in SQLite
        session = InterviewSessionModel(
            candidate_id=candidate.id,
            role_id=role.id,
            interviewer_name="Recruiter",
            interview_round=f"ADAPTIVE_{experience_level.upper().replace(' ', '_')}",
            status=InterviewSessionStatus.DRAFT.value,
            experience_level=experience_level,
            duration_seconds=planned_duration_seconds,
            remaining_seconds=planned_duration_seconds,
            current_question_index=0,
            raw_notes=f"Personalized plan generated via {meta.provider_name} ({meta.model_name}) for {experience_level} ({duration_minutes}m)"
        )
        db.add(session)
        db.flush()

        question_records: List[InterviewQuestionModel] = []
        ordered_questions = output.questions[:target_question_count]

        for idx, q in enumerate(ordered_questions):
            # Match to requirement
            matched_req = req_by_name_lower.get(q.requirement_name.lower())
            if not matched_req:
                for r_name_lower, r_obj in req_by_name_lower.items():
                    if q.requirement_name.lower() in r_name_lower or r_name_lower in q.requirement_name.lower():
                        matched_req = r_obj
                        break

            req_id = matched_req.id if matched_req else (gaps[0].requirement_id if gaps else requirements[0].id)
            priority_val = "MUST_HAVE" if (matched_req and matched_req.category == "MUST_HAVE") else "HIGH"

            # Normalize question type
            raw_type = (q.question_type or "").upper()
            is_resume_probe = "RESUME" in raw_type or (q.evidence_basis and any(a.verbatim_quote in q.evidence_basis for a in resume_evidence_pool))

            if is_resume_probe and resume_evidence_pool:
                final_q_type = "RESUME_GROUNDED"
                final_basis = q.evidence_basis or resume_evidence_pool[idx % len(resume_evidence_pool)].verbatim_quote
                final_reason = q.reason or f"Verifying candidate's documented achievement in resume: '{final_basis[:60]}...'"
            else:
                final_q_type = "GAP_VALIDATION"
                final_basis = q.evidence_basis or "Role Requirement Gap / Missing Documentation in Resume"
                final_reason = q.reason or q.target_gap or f"Probing competency in {matched_req.name if matched_req else 'Role Requirement'}"

            # Variable duration pacing
            if q.estimated_duration_seconds and q.estimated_duration_seconds > 0:
                dur_sec = q.estimated_duration_seconds
            else:
                dur_sec = base_estimated_duration

            q_record = InterviewQuestionModel(
                session_id=session.id,
                requirement_id=req_id,
                target_gap_description=q.target_gap,
                question_text=q.question,
                probing_context=q.probing_context,
                expected_positive_signals=q.positive_signals,
                expected_red_flags=q.red_flags,
                question_type=final_q_type,
                reason=final_reason,
                evidence_basis=final_basis,
                experience_level=experience_level,
                priority=priority_val,
                estimated_duration_seconds=dur_sec,
                order_index=idx,
                recruiter_approved=True
            )
            db.add(q_record)
            question_records.append(q_record)

        # 9. Audit Logging
        db.add(AuditEventModel(
            entity_type="INTERVIEW_SESSION",
            entity_id=session.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.INTERVIEW_GENERATED.value,
            details_json=json.dumps({
                "candidate_id": candidate.id,
                "role_id": role.id,
                "experience_level": experience_level,
                "duration_minutes": duration_minutes,
                "questions_count": len(question_records),
                "resume_questions_count": sum(1 for q in question_records if q.question_type == "RESUME_GROUNDED"),
                "gap_questions_count": sum(1 for q in question_records if q.question_type != "RESUME_GROUNDED"),
                "provider": meta.provider_name,
                "is_fallback": meta.is_fallback
            })
        ))

        db.commit()
        db.refresh(session)
        return session
