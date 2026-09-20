from typing import List, Dict, Union
from ..domain.enums import EvidenceStatus, RequirementCategory, GapPriority
from ..domain.schemas import CandidateGap, CandidateGapsResponse
from ..db.models import RequirementModel, EvidenceClaimModel

class GapDetector:
    """
    Deterministic rule engine that identifies candidate competency gaps
    and classifies their urgency/priority for interview probing.
    
    Priority Rules:
    - CRITICAL: MUST_HAVE requirement is NOT_FOUND_IN_PROVIDED_MATERIAL, UNVERIFIED, or CONTRADICTED.
    - HIGH:     MUST_HAVE requirement is PARTIALLY_PROVEN.
    - MEDIUM:   NICE_TO_HAVE requirement is NOT_FOUND_IN_PROVIDED_MATERIAL, UNVERIFIED, or CONTRADICTED.
    - LOW:      NICE_TO_HAVE requirement is PARTIALLY_PROVEN.
    - (PROVEN items are validated strengths, not gaps.)
    """

    PRIORITY_ORDER = {
        GapPriority.CRITICAL: 0,
        GapPriority.HIGH: 1,
        GapPriority.MEDIUM: 2,
        GapPriority.LOW: 3
    }

    @classmethod
    def detect_gaps(
        cls,
        requirements: List[RequirementModel],
        claims: Union[List[EvidenceClaimModel], Dict[str, EvidenceStatus]]
    ) -> List[CandidateGap]:
        """
        Evaluate requirements against candidate evidence claims.
        """
        # Index status by requirement_id
        status_by_req: Dict[str, EvidenceStatus] = {}
        if isinstance(claims, dict):
            status_by_req = claims
        else:
            for claim in claims:
                # If multiple claims for same requirement, prefer the most positive status
                # Or keep latest
                current_status = EvidenceStatus(claim.status) if isinstance(claim.status, str) else claim.status
                status_by_req[claim.requirement_id] = current_status

        gaps: List[CandidateGap] = []

        for req in requirements:
            req_cat = RequirementCategory(req.category) if isinstance(req.category, str) else req.category
            status = status_by_req.get(req.id, EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL)

            # Validated strengths are not gaps
            if status == EvidenceStatus.PROVEN:
                continue

            if req_cat == RequirementCategory.MUST_HAVE:
                if status in (EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL, EvidenceStatus.UNVERIFIED, EvidenceStatus.CONTRADICTED):
                    priority = GapPriority.CRITICAL
                    reason = f"Must-have requirement '{req.name}' is {status.value}. Needs direct technical verification."
                elif status == EvidenceStatus.PARTIALLY_PROVEN:
                    priority = GapPriority.HIGH
                    reason = f"Must-have requirement '{req.name}' is PARTIALLY_PROVEN. Depth and ownership must be tested."
                else:
                    priority = GapPriority.HIGH
                    reason = f"Must-have requirement '{req.name}' has unconfirmed status: {status.value}."

            else:  # NICE_TO_HAVE
                if status in (EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL, EvidenceStatus.UNVERIFIED, EvidenceStatus.CONTRADICTED):
                    priority = GapPriority.MEDIUM
                    reason = f"Nice-to-have requirement '{req.name}' is {status.value}."
                elif status == EvidenceStatus.PARTIALLY_PROVEN:
                    priority = GapPriority.LOW
                    reason = f"Nice-to-have requirement '{req.name}' is PARTIALLY_PROVEN."
                else:
                    priority = GapPriority.LOW
                    reason = f"Nice-to-have requirement '{req.name}' has unconfirmed status: {status.value}."

            gaps.append(CandidateGap(
                requirement_id=req.id,
                requirement_name=req.name,
                category=req_cat,
                status=status,
                priority=priority,
                reason=reason
            ))

        # Sort gaps deterministically by priority then requirement name
        gaps.sort(key=lambda g: (cls.PRIORITY_ORDER.get(g.priority, 99), g.requirement_name))
        return gaps

    @classmethod
    def build_response(cls, candidate_id: str, gaps: List[CandidateGap]) -> CandidateGapsResponse:
        critical = sum(1 for g in gaps if g.priority == GapPriority.CRITICAL)
        high = sum(1 for g in gaps if g.priority == GapPriority.HIGH)
        medium = sum(1 for g in gaps if g.priority == GapPriority.MEDIUM)
        low = sum(1 for g in gaps if g.priority == GapPriority.LOW)

        return CandidateGapsResponse(
            candidate_id=candidate_id,
            total_gaps=len(gaps),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            gaps=gaps
        )
