from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from .enums import (
    EvidenceStatus,
    RequirementCategory,
    GapPriority,
    SourceType,
    AuditAction,
    AuditActor,
    AIMode,
    InterviewSessionStatus,
    InterviewProposalStatus
)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# --- Job Requisition & Criteria ---
class RequirementBase(BaseModel):
    name: str = Field(..., min_length=1, description="Name of the skill or requirement")
    category: RequirementCategory = Field(default=RequirementCategory.MUST_HAVE)
    description: Optional[str] = Field(None, description="Detailed context or scope")
    weight: float = Field(default=1.0, ge=0.0, le=5.0)

class RequirementCreate(RequirementBase):
    pass

class RequirementRead(RequirementBase):
    id: str
    role_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RoleCreate(BaseModel):
    title: str = Field(..., min_length=1)
    department: Optional[str] = None
    raw_jd_text: Optional[str] = Field(default="")
    min_years_experience: int = Field(default=0, ge=0)
    weight_must_have: float = Field(default=0.65, ge=0.0, le=1.0)
    weight_nice_to_have: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_experience: float = Field(default=0.15, ge=0.0, le=1.0)

class RoleRead(BaseModel):
    id: str
    title: str
    department: Optional[str]
    raw_jd_text: str
    min_years_experience: int
    weight_must_have: float
    weight_nice_to_have: float
    weight_experience: float
    requirements: List[RequirementRead] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Candidates & Documents ---
class CandidateBase(BaseModel):
    full_name: str = Field(..., min_length=1)
    email: Optional[str] = None
    phone: Optional[str] = None
    anonymous_alias: str = Field(..., min_length=1)
    years_experience: float = Field(default=0.0, ge=0.0)

class CandidateRead(CandidateBase):
    id: str
    role_id: str
    quarantined: bool = False
    quarantine_reason: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CandidateBlindView(BaseModel):
    id: str
    role_id: str
    anonymous_alias: str
    years_experience: float
    quarantined: bool
    quarantine_reason: Optional[str]
    created_at: datetime

# --- Evidence & Provenance ---
class EvidenceClaimBase(BaseModel):
    requirement_id: str = Field(..., min_length=1)
    source_type: SourceType = SourceType.RESUME
    section_reference: Optional[str] = None
    verbatim_quote: Optional[str] = None
    start_offset: Optional[int] = Field(None, ge=0)
    end_offset: Optional[int] = Field(None, ge=0)
    status: EvidenceStatus
    reasoning: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class EvidenceClaimRead(EvidenceClaimBase):
    id: str
    candidate_id: str
    source_document_id: Optional[str] = None
    is_human_overridden: bool = False
    override_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Deterministic Fit Scoring ---
class RequirementScoreDetail(BaseModel):
    requirement_id: str
    requirement_name: str
    category: RequirementCategory
    status: EvidenceStatus
    point_value: float
    weight: float

class FitScoreBreakdown(BaseModel):
    candidate_id: str
    overall_score: float = Field(..., ge=0.0, le=100.0)
    must_have_score: float = Field(..., ge=0.0, le=1.0)
    nice_to_have_score: float = Field(..., ge=0.0, le=1.0)
    experience_score: float = Field(..., ge=0.0, le=1.0)
    formula_representation: str
    details: List[RequirementScoreDetail] = []
    calculation_version: str = "v1.0"
    calculated_at: datetime = Field(default_factory=utc_now)

# --- Candidate Gaps & Deficiencies ---
class CandidateGap(BaseModel):
    requirement_id: str
    requirement_name: str
    category: RequirementCategory
    status: EvidenceStatus
    priority: GapPriority
    reason: str

class CandidateGapsResponse(BaseModel):
    candidate_id: str
    total_gaps: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    gaps: List[CandidateGap]

# --- AI Evidence Analysis Request/Response ---
class EvidenceAnalysisRequest(BaseModel):
    ai_mode: Optional[AIMode] = None

class EvidenceAnalysisResponse(BaseModel):
    candidate_id: str
    claims_analyzed: int
    proven_count: int
    partially_proven_count: int
    unverified_count: int
    not_found_count: int
    provider_metadata: Dict[str, Any]
    fit_score: FitScoreBreakdown

# --- Interview Intelligence ---
class InterviewQuestionBase(BaseModel):
    requirement_id: Optional[str] = None
    target_gap_description: str
    question_text: str
    probing_context: Optional[str] = None
    expected_positive_signals: Optional[str] = None
    expected_red_flags: Optional[str] = None
    question_type: str = "GAP_INVESTIGATION"
    reason: Optional[str] = None
    evidence_basis: Optional[str] = None
    experience_level: Optional[str] = None
    priority: str = "HIGH"
    estimated_duration_seconds: int = 180
    candidate_answer: Optional[str] = None
    extracted_evidence: Optional[str] = None
    evidence_status: Optional[str] = None
    is_skipped: bool = False
    is_answered: bool = False
    answered_at: Optional[datetime] = None
    order_index: int = 0
    recruiter_approved: bool = True

class InterviewQuestionRead(InterviewQuestionBase):
    id: str
    session_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InterviewGenerationRequest(BaseModel):
    ai_mode: Optional[AIMode] = None
    max_questions: int = Field(default=5, ge=1, le=10)
    focus_gaps_only: bool = True

class InterviewSetupRequest(BaseModel):
    experience_level: str = Field(default="Mid Level", description="Entry Level, Junior, Mid Level, Senior, or Custom")
    duration_minutes: int = Field(default=15, ge=5, le=60, description="Duration in minutes (5-60)")
    ai_mode: Optional[AIMode] = None

class AdaptiveAnswerRequest(BaseModel):
    answer_text: str = Field(..., min_length=2, description="Candidate verbatim answer or recruiter notes")
    seconds_spent: Optional[int] = Field(default=None, ge=0, description="Actual seconds spent on question")

class AdaptiveFollowupRequest(BaseModel):
    notes_context: Optional[str] = None
    ai_mode: Optional[AIMode] = None

class AdaptiveSkipRequest(BaseModel):
    reason: Optional[str] = None

class RequirementCoverageItem(BaseModel):
    requirement_id: str
    requirement_name: str
    category: RequirementCategory
    status: EvidenceStatus
    coverage_state: str  # CONFIRMED | PARTIAL | UNRESOLVED | NOT_ASSESSED
    evidence_quote: Optional[str] = None
    reasoning: Optional[str] = None

class InterviewEvidenceProposal(BaseModel):
    id: str
    session_id: str
    requirement_id: str
    requirement_name: Optional[str] = None
    verbatim_excerpt: str
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    proposed_status: EvidenceStatus
    justification: str
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    review_status: str = "PENDING"  # PENDING | APPROVED | REJECTED
    recruiter_notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InterviewSessionCreate(BaseModel):
    interviewer_name: Optional[str] = "Recruiter"
    interview_round: Optional[str] = "TECHNICAL_SCREEN"

class InterviewSessionRead(BaseModel):
    id: str
    candidate_id: str
    role_id: Optional[str] = None
    interviewer_name: Optional[str] = "Recruiter"
    interview_round: str = "TECHNICAL_SCREEN"
    status: str = "DRAFT"
    experience_level: str = "Mid Level"
    duration_seconds: int = 900
    remaining_seconds: int = 900
    current_question_index: int = 0
    summary_json: Optional[str] = None
    raw_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    questions: List[InterviewQuestionRead] = []
    proposals: List[InterviewEvidenceProposal] = []
    model_config = ConfigDict(from_attributes=True)

class AdaptiveInterviewStateResponse(BaseModel):
    session_id: str
    candidate_id: str
    candidate_name: str
    role_id: Optional[str] = None
    role_title: str
    status: str
    experience_level: str
    duration_seconds: int
    remaining_seconds: int
    current_question_index: int
    total_questions: int
    resume_questions_count: int = 0
    gap_questions_count: int = 0
    followup_reserve_seconds: int = 0
    current_question: Optional[InterviewQuestionRead] = None
    questions: List[InterviewQuestionRead] = []
    coverage_breakdown: List[RequirementCoverageItem] = []
    current_score: float = 0.0
    previous_score: float = 0.0
    summary: Optional[Dict[str, Any]] = None

class InterviewSummaryResponse(BaseModel):
    session_id: str
    candidate_id: str
    candidate_name: str
    role_title: str
    experience_level: str
    duration_minutes: int
    time_spent_seconds: int
    questions_total: int
    questions_answered: int
    questions_skipped: int
    resume_questions_count: int = 0
    gap_questions_count: int = 0
    followup_reserve_seconds: int = 0
    pre_interview_score: float
    post_interview_score: float
    score_delta: float
    pre_interview_gaps_count: int
    post_interview_gaps_count: int
    resolved_gaps_count: int
    coverage_breakdown: List[RequirementCoverageItem]
    transcript: List[Dict[str, Any]]
    score_breakdown: FitScoreBreakdown
    created_at: datetime
    completed_at: datetime

class InterviewNotesSubmitRequest(BaseModel):
    raw_notes: str = Field(..., min_length=5, max_length=50000, description="Recruiter interview notes")
    interviewer_name: Optional[str] = "Recruiter"
    interview_round: Optional[str] = "TECHNICAL_SCREEN"

class InterviewEvidenceConfirmRequest(BaseModel):
    override_status: Optional[EvidenceStatus] = None
    justification: Optional[str] = None

class InterviewEvidenceRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Reason for rejecting proposal")

class InterviewEvidenceConfirmResponse(BaseModel):
    proposal: InterviewEvidenceProposal
    previous_score: float
    new_score: float
    score_breakdown: FitScoreBreakdown
    gaps_response: CandidateGapsResponse
    changed_requirement_id: str

class InterviewEvidenceAnalysisRequest(BaseModel):
    ai_mode: Optional[AIMode] = None

class InterviewEvidenceAnalysisResponse(BaseModel):
    session_id: str
    proposals: List[InterviewEvidenceProposal]
    proposals_count: int
    provider_metadata: Dict[str, Any]

class InterviewNotesInput(BaseModel):
    candidate_id: str
    interviewer_name: Optional[str] = "Recruiter"
    interview_round: str = "TECHNICAL_SCREEN"
    raw_notes: str

# --- Human Recruiter Overrides ---
class OverrideCreate(BaseModel):
    candidate_id: str
    evidence_id: str
    new_status: EvidenceStatus
    override_reason: str = Field(..., min_length=5, description="Mandatory justification")

class OverrideResponse(BaseModel):
    evidence_claim: EvidenceClaimRead
    fit_score: FitScoreBreakdown

# --- Audit Logging ---
class AuditEventRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    actor: AuditActor
    action: AuditAction
    details: Dict[str, Any]
    created_at: datetime

# --- AI Output Contracts (Strict Model Schemas) ---
class JDAnalysisRequirement(BaseModel):
    name: str
    category: RequirementCategory
    description: str
    weight: float = 1.0

class JDAnalysisOutput(BaseModel):
    role_title: str
    department: Optional[str] = None
    min_years_experience: int = 0
    requirements: List[JDAnalysisRequirement]

class ExtractedCandidateClaim(BaseModel):
    requirement_name: str
    status: EvidenceStatus
    verbatim_quote: Optional[str] = None
    section_reference: Optional[str] = None
    reasoning: str
    confidence: float = 1.0

class EvidenceMatchingOutput(BaseModel):
    candidate_name: str
    years_experience: float
    claims: List[ExtractedCandidateClaim]

class GeneratedQuestion(BaseModel):
    requirement_name: str
    target_gap: str
    question: str
    probing_context: str
    positive_signals: str
    red_flags: str
    question_type: str = "GAP_VALIDATION"  # RESUME_GROUNDED | GAP_VALIDATION | FOLLOW_UP
    reason: Optional[str] = None
    evidence_basis: Optional[str] = None
    estimated_duration_seconds: int = 120

class InterviewQuestionOutput(BaseModel):
    questions: List[GeneratedQuestion]

class InterviewEvidenceItem(BaseModel):
    requirement_name: str
    updated_status: EvidenceStatus
    verbatim_quote: str
    reasoning: str
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)

class InterviewEvidenceOutput(BaseModel):
    evidence_items: List[InterviewEvidenceItem]

# --- System & Health Schemas ---
class HealthCheckResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    database_connected: bool
    ai_mode: AIMode
    timestamp: datetime = Field(default_factory=utc_now)

# --- Document Extraction & Security Contracts ---
class DocumentSection(BaseModel):
    section_name: str
    page_number: Optional[int] = None
    text: str
    start_offset: int
    end_offset: int

class DocumentContent(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_hash: str
    sections: List[DocumentSection] = []
    full_text: str
    warnings: List[str] = []
    total_pages: int = 1

class SecurityScanResult(BaseModel):
    is_suspicious: bool
    quarantined: bool
    severity: str  # SAFE | LOW | MEDIUM | HIGH | CRITICAL
    matched_rules: List[str] = []
    quarantine_reason: Optional[str] = None
    sanitized_preview: str

class QuoteVerificationResult(BaseModel):
    valid: bool
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    matched_text: Optional[str] = None
    warning: Optional[str] = None

class CandidateUploadResponse(BaseModel):
    candidate: CandidateRead
    document_id: str
    security_scan: SecurityScanResult
    blind_preview: Optional[str] = None
    fit_score: Optional[FitScoreBreakdown] = None

# --- Candidate Comparison Matrix Contracts ---
class CandidateMatrixCell(BaseModel):
    requirement_id: str
    requirement_name: str
    status: EvidenceStatus
    confidence: float
    source_type: str
    verbatim_quote: Optional[str] = None
    is_human_overridden: bool = False

class CandidateMatrixRow(BaseModel):
    candidate_id: str
    full_name: str
    anonymous_alias: str
    years_experience: float
    quarantined: bool
    quarantine_reason: Optional[str] = None
    overall_score: Optional[float] = None
    cells: Dict[str, CandidateMatrixCell] = {}

class CandidateMatrixResponse(BaseModel):
    role_id: str
    role_title: str
    requirements: List[RequirementRead]
    candidates: List[CandidateMatrixRow]

