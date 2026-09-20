from typing import List, Dict, Optional, Tuple
from ..domain.enums import EvidenceStatus, RequirementCategory
from ..domain.schemas import FitScoreBreakdown, RequirementScoreDetail

POINT_MAPPING: Dict[EvidenceStatus, float] = {
    EvidenceStatus.PROVEN: 1.0,
    EvidenceStatus.PARTIALLY_PROVEN: 0.5,
    EvidenceStatus.UNVERIFIED: 0.0,
    EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL: 0.0,
    EvidenceStatus.CONTRADICTED: -0.5,
}

class ScoringError(Exception):
    """Raised when score calculation input constraints are violated."""
    pass

class DeterministicScoringEngine:
    """
    100% deterministic mathematical scoring engine.
    Zero LLM involvement, zero random constants, fully explainable and reproducible.
    """

    @classmethod
    def calculate_score(
        cls,
        candidate_id: str,
        requirements: List[dict],  # list of {id, name, category, weight}
        claims_by_req_id: Dict[str, EvidenceStatus],
        candidate_years_exp: float = 0.0,
        required_years_exp: int = 0,
        weights: Optional[Dict[str, float]] = None
    ) -> FitScoreBreakdown:
        """
        Compute transparent weighted fit score from deterministic status points.
        """
        # 1. Normalize weights
        w_must = weights.get("must_have", 0.65) if weights else 0.65
        w_nice = weights.get("nice_to_have", 0.20) if weights else 0.20
        w_exp = weights.get("experience", 0.15) if weights else 0.15

        if w_must < 0 or w_nice < 0 or w_exp < 0:
            raise ScoringError("Weights must be non-negative.")

        total_weight = w_must + w_nice + w_exp
        if total_weight <= 0:
            raise ScoringError("Sum of weights must be positive.")

        # Re-normalize to exactly 1.0
        w_must /= total_weight
        w_nice /= total_weight
        w_exp /= total_weight

        # 2. Categorize and score requirements
        must_haves = [r for r in requirements if r["category"] == RequirementCategory.MUST_HAVE]
        nice_to_haves = [r for r in requirements if r["category"] == RequirementCategory.NICE_TO_HAVE]

        details: List[RequirementScoreDetail] = []
        must_points_sum = 0.0
        nice_points_sum = 0.0

        for r in must_haves:
            req_id = r["id"]
            status = claims_by_req_id.get(req_id, EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL)
            pt = POINT_MAPPING.get(status, 0.0)
            must_points_sum += pt * r.get("weight", 1.0)
            details.append(RequirementScoreDetail(
                requirement_id=req_id,
                requirement_name=r["name"],
                category=RequirementCategory.MUST_HAVE,
                status=status,
                point_value=pt,
                weight=r.get("weight", 1.0)
            ))

        for r in nice_to_haves:
            req_id = r["id"]
            status = claims_by_req_id.get(req_id, EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL)
            pt = POINT_MAPPING.get(status, 0.0)
            nice_points_sum += pt * r.get("weight", 1.0)
            details.append(RequirementScoreDetail(
                requirement_id=req_id,
                requirement_name=r["name"],
                category=RequirementCategory.NICE_TO_HAVE,
                status=status,
                point_value=pt,
                weight=r.get("weight", 1.0)
            ))

        # Calculate category averages
        must_weight_total = sum(r.get("weight", 1.0) for r in must_haves)
        nice_weight_total = sum(r.get("weight", 1.0) for r in nice_to_haves)

        s_must = (must_points_sum / must_weight_total) if must_weight_total > 0 else 1.0
        s_nice = (nice_points_sum / nice_weight_total) if nice_weight_total > 0 else 1.0

        # Clamp category scores between -0.5 and 1.0
        s_must = max(-0.5, min(1.0, s_must))
        s_nice = max(-0.5, min(1.0, s_nice))

        # Experience alignment score
        if required_years_exp <= 0:
            s_exp = 1.0
        else:
            s_exp = max(0.0, min(1.0, candidate_years_exp / float(required_years_exp)))

        # Final raw formula
        raw_final = (s_must * w_must + s_nice * w_nice + s_exp * w_exp) * 100.0
        overall_score = max(0.0, min(100.0, round(raw_final, 2)))

        # Formula string for recruiter explainability
        formula_str = (
            f"({round(s_must, 2)} * {round(w_must, 2)} [Must-Have] + "
            f"{round(s_nice, 2)} * {round(w_nice, 2)} [Nice-to-Have] + "
            f"{round(s_exp, 2)} * {round(w_exp, 2)} [Experience]) * 100 = {overall_score}%"
        )

        return FitScoreBreakdown(
            candidate_id=candidate_id,
            overall_score=overall_score,
            must_have_score=round(max(0.0, s_must), 2),
            nice_to_have_score=round(max(0.0, s_nice), 2),
            experience_score=round(s_exp, 2),
            formula_representation=formula_str,
            details=details,
            calculation_version="v1.0"
        )
