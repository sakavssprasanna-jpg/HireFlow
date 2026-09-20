import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..domain.enums import EvidenceStatus, RequirementCategory, SourceType, AuditAction, AuditActor, AIMode
from ..domain.schemas import (
    EvidenceMatchingOutput,
    EvidenceAnalysisResponse,
    FitScoreBreakdown
)
from ..db.models import (
    CandidateModel,
    CandidateDocumentModel,
    RequirementModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    AuditEventModel
)
from ..ai.factory import get_llm_provider
from ..ai.base import ProviderError
from .quote_verifier import QuoteVerifier
from .scoring_engine import DeterministicScoringEngine

logger = logging.getLogger("hireflow.services.ai_evidence")

class AIEvidenceService:
    """
    Orchestrates AI-driven evidence extraction with strict deterministic verification gating.
    Enforces the core hackathon invariant:
    AI proposes -> Deterministic Code Verifies -> Human Decides.
    """

    @classmethod
    async def analyze_candidate_evidence(
        cls,
        db: Session,
        candidate_id: str,
        ai_mode: Optional[AIMode] = None
    ) -> EvidenceAnalysisResponse:
        # 1. Fetch Candidate
        candidate = db.query(CandidateModel).filter(CandidateModel.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate '{candidate_id}' not found.")

        # SECURITY INVARIANT: Quarantined candidates halt immediately with zero LLM invocations
        if candidate.quarantined:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Candidate document is quarantined ({candidate.quarantine_reason}). Downstream AI analysis is prohibited."
            )

        # 2. Fetch Document & Role Requirements
        doc = db.query(CandidateDocumentModel).filter(CandidateDocumentModel.candidate_id == candidate_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No document found for this candidate.")

        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == candidate.role_id).all()
        if not requirements:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No role requirements configured for this position.")

        # 3. Formulate Prompt
        prompt_reqs = []
        req_map: Dict[str, RequirementModel] = {}
        for r in requirements:
            req_map[r.id] = r
            prompt_reqs.append(f"- REQUIREMENT: {r.name} | CATEGORY: {r.category} | DESCRIPTION: {r.description or 'None'}")

        requirements_block = "\n".join(prompt_reqs)
        full_prompt = (
            f"EVALUATION CRITERIA:\n{requirements_block}\n\n"
            f"CANDIDATE_RESUME_TEXT:\n{doc.sanitized_text}\n"
        )

        system_instruction = (
            "You are an expert technical recruiter and evidence auditor. "
            "Examine the candidate resume against each requirement. "
            "For every requirement, extract verbatim quotes only if they appear in the resume. "
            "If no evidence exists, declare status as NOT_FOUND_IN_PROVIDED_MATERIAL with no quote. "
            "Do NOT invent or embellish claims. Any fabricated quote will be rejected by our deterministic verification engine."
        )

        # 4. Invoke Selected AI Provider (or fallback)
        provider = get_llm_provider(ai_mode)
        try:
            response = await provider.generate_structured(
                prompt=full_prompt,
                schema=EvidenceMatchingOutput,
                system_instruction=system_instruction
            )
            matching_output: EvidenceMatchingOutput = response.data
            meta = response.metadata
        except ProviderError as pe:
            logger.warning(f"AI Provider error ({pe}); retrying with OfflineFallbackProvider.")
            fallback_provider = get_llm_provider(AIMode.OFFLINE_FALLBACK)
            response = await fallback_provider.generate_structured(
                prompt=full_prompt,
                schema=EvidenceMatchingOutput,
                system_instruction=system_instruction
            )
            matching_output = response.data
            meta = response.metadata

        # 5. Deterministic Quote Verification & Reconciliation
        # Map requirement by lowercase name for robust matching
        req_by_name_lower = {r.name.lower(): r for r in requirements}

        claims_by_req_id: Dict[str, EvidenceStatus] = {}
        proven_cnt = 0
        partially_cnt = 0
        unverified_cnt = 0
        not_found_cnt = 0

        # Track requirements matched by AI claims
        matched_req_ids = set()

        for claim_proposal in matching_output.claims:
            # Find requirement
            target_req = req_by_name_lower.get(claim_proposal.requirement_name.lower())
            if not target_req:
                # Fuzzy match: check if substring
                for r_name_lower, r_obj in req_by_name_lower.items():
                    if claim_proposal.requirement_name.lower() in r_name_lower or r_name_lower in claim_proposal.requirement_name.lower():
                        target_req = r_obj
                        break

            if not target_req:
                continue

            matched_req_ids.add(target_req.id)

            # Check if this claim was previously human-overridden
            existing_claim = (
                db.query(EvidenceClaimModel)
                .filter(EvidenceClaimModel.candidate_id == candidate_id, EvidenceClaimModel.requirement_id == target_req.id)
                .first()
            )

            if existing_claim and existing_claim.is_human_overridden:
                # Recruiter decision stands!
                claims_by_req_id[target_req.id] = EvidenceStatus(existing_claim.status)
                continue

            # Deterministic Quote Verification Gate
            final_status = claim_proposal.status
            verified_quote = claim_proposal.verbatim_quote
            start_off = None
            end_off = None
            sec_ref = claim_proposal.section_reference or "Resume"
            warning_note = None

            if final_status in (EvidenceStatus.PROVEN, EvidenceStatus.PARTIALLY_PROVEN):
                if verified_quote:
                    verification = QuoteVerifier.verify_quote(
                        raw_source_text=doc.raw_text,
                        quote=verified_quote
                    )
                    if verification.valid:
                        start_off = verification.start_offset
                        end_off = verification.end_offset
                        sec_ref = verification.section_name or sec_ref
                        verified_quote = verification.matched_text
                    else:
                        # DETERMINISTIC HALLUCINATION PREVENTION
                        final_status = EvidenceStatus.UNVERIFIED
                        warning_note = "UNVERIFIED_HALLUCINATION_PREVENTED: Proposing quote not verified in source text."
                        logger.info(f"Hallucination prevented for requirement {target_req.name}: quote not found.")
                else:
                    final_status = EvidenceStatus.UNVERIFIED
                    warning_note = "UNVERIFIED_HALLUCINATION_PREVENTED: Positive status claimed without verifiable quote."

            # Update counters
            if final_status == EvidenceStatus.PROVEN:
                proven_cnt += 1
            elif final_status == EvidenceStatus.PARTIALLY_PROVEN:
                partially_cnt += 1
            elif final_status == EvidenceStatus.UNVERIFIED:
                unverified_cnt += 1
            elif final_status == EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL:
                not_found_cnt += 1

            claims_by_req_id[target_req.id] = final_status

            reasoning = claim_proposal.reasoning
            if warning_note:
                reasoning = f"[{warning_note}] {reasoning}"

            # Persist or update claim
            if existing_claim:
                existing_claim.status = final_status.value
                existing_claim.verbatim_quote = verified_quote
                existing_claim.start_offset = start_off
                existing_claim.end_offset = end_off
                existing_claim.section_reference = sec_ref
                existing_claim.reasoning = reasoning
                existing_claim.confidence = claim_proposal.confidence
            else:
                new_claim = EvidenceClaimModel(
                    candidate_id=candidate_id,
                    requirement_id=target_req.id,
                    source_document_id=doc.id,
                    source_type=SourceType.RESUME.value,
                    section_reference=sec_ref,
                    verbatim_quote=verified_quote,
                    start_offset=start_off,
                    end_offset=end_off,
                    status=final_status.value,
                    reasoning=reasoning,
                    confidence=claim_proposal.confidence
                )
                db.add(new_claim)

        # For any requirements not returned by AI, ensure NOT_FOUND record exists
        for req in requirements:
            if req.id not in claims_by_req_id:
                existing = (
                    db.query(EvidenceClaimModel)
                    .filter(EvidenceClaimModel.candidate_id == candidate_id, EvidenceClaimModel.requirement_id == req.id)
                    .first()
                )
                if not existing:
                    not_found_claim = EvidenceClaimModel(
                        candidate_id=candidate_id,
                        requirement_id=req.id,
                        source_document_id=doc.id,
                        source_type=SourceType.RESUME.value,
                        section_reference="Not Located",
                        verbatim_quote=None,
                        status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL.value,
                        reasoning="No mention found in candidate material.",
                        confidence=1.0
                    )
                    db.add(not_found_claim)
                    claims_by_req_id[req.id] = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL
                    not_found_cnt += 1
                else:
                    claims_by_req_id[req.id] = EvidenceStatus(existing.status)

        # Update candidate years of experience if extracted and candidate currently has 0
        if matching_output.years_experience > 0 and candidate.years_experience == 0:
            candidate.years_experience = matching_output.years_experience

        # 6. Deterministic Score Recalculation
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
            claims_by_req_id=claims_by_req_id,
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

        # 7. Audit Logging
        db.add(AuditEventModel(
            entity_type="CANDIDATE",
            entity_id=candidate.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.EVIDENCE_MATCHED.value,
            details_json=json.dumps({
                "provider": meta.provider_name,
                "model": meta.model_name,
                "is_fallback": meta.is_fallback,
                "latency_ms": meta.latency_ms,
                "overall_score": score_breakdown.overall_score
            })
        ))

        db.commit()

        return EvidenceAnalysisResponse(
            candidate_id=candidate.id,
            claims_analyzed=len(claims_by_req_id),
            proven_count=proven_cnt,
            partially_proven_count=partially_cnt,
            unverified_count=unverified_cnt,
            not_found_count=not_found_cnt,
            provider_metadata=meta.model_dump(),
            fit_score=score_breakdown
        )
