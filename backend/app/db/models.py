import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class RoleModel(Base):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    raw_jd_text = Column(Text, nullable=False)
    min_years_experience = Column(Integer, default=0)
    weight_must_have = Column(Float, default=0.65)
    weight_nice_to_have = Column(Float, default=0.20)
    weight_experience = Column(Float, default=0.15)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    requirements = relationship("RequirementModel", back_populates="role", cascade="all, delete-orphan")
    candidates = relationship("CandidateModel", back_populates="role", cascade="all, delete-orphan")

class RequirementModel(Base):
    __tablename__ = "requirements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(32), nullable=False)  # MUST_HAVE | NICE_TO_HAVE
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=utc_now)

    role = relationship("RoleModel", back_populates="requirements")
    evidence_claims = relationship("EvidenceClaimModel", back_populates="requirement", cascade="all, delete-orphan")

class CandidateModel(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)
    anonymous_alias = Column(String(64), nullable=False)
    years_experience = Column(Float, default=0.0)
    quarantined = Column(Boolean, default=False)
    quarantine_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    role = relationship("RoleModel", back_populates="candidates")
    documents = relationship("CandidateDocumentModel", back_populates="candidate", cascade="all, delete-orphan")
    evidence_claims = relationship("EvidenceClaimModel", back_populates="candidate", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSessionModel", back_populates="candidate", cascade="all, delete-orphan")
    score_snapshots = relationship("ScoreSnapshotModel", back_populates="candidate", cascade="all, delete-orphan")

class CandidateDocumentModel(Base):
    __tablename__ = "candidate_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(16), nullable=False)
    raw_text = Column(Text, nullable=False)
    sanitized_text = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    candidate = relationship("CandidateModel", back_populates="documents")

class EvidenceClaimModel(Base):
    __tablename__ = "evidence_claims"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id = Column(String(36), nullable=True)
    source_type = Column(String(32), default="RESUME")  # RESUME | INTERVIEW_NOTE
    section_reference = Column(String(255), nullable=True)
    verbatim_quote = Column(Text, nullable=True)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)  # PROVEN | PARTIALLY_PROVEN | UNVERIFIED | CONTRADICTED | NOT_FOUND_IN_PROVIDED_MATERIAL
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    is_human_overridden = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    candidate = relationship("CandidateModel", back_populates="evidence_claims")
    requirement = relationship("RequirementModel", back_populates="evidence_claims")

class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), nullable=True)
    interviewer_name = Column(String(255), default="Recruiter")
    interview_round = Column(String(64), default="TECHNICAL_SCREEN")
    status = Column(String(32), default="DRAFT")
    experience_level = Column(String(32), default="Mid Level")
    duration_seconds = Column(Integer, default=900)
    remaining_seconds = Column(Integer, default=900)
    current_question_index = Column(Integer, default=0)
    summary_json = Column(Text, nullable=True)
    raw_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    candidate = relationship("CandidateModel", back_populates="interview_sessions")
    questions = relationship("InterviewQuestionModel", back_populates="session", cascade="all, delete-orphan", order_by="InterviewQuestionModel.order_index")
    proposals = relationship("InterviewEvidenceProposalModel", back_populates="session", cascade="all, delete-orphan")

class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(36), nullable=True)
    target_gap_description = Column(Text, nullable=False)
    question_text = Column(Text, nullable=False)
    probing_context = Column(Text, nullable=True)
    expected_positive_signals = Column(Text, nullable=True)
    expected_red_flags = Column(Text, nullable=True)
    question_type = Column(String(32), default="GAP_INVESTIGATION")
    reason = Column(Text, nullable=True)
    evidence_basis = Column(Text, nullable=True)
    experience_level = Column(String(32), nullable=True)
    priority = Column(String(16), default="HIGH")
    estimated_duration_seconds = Column(Integer, default=180)
    candidate_answer = Column(Text, nullable=True)
    extracted_evidence = Column(Text, nullable=True)
    evidence_status = Column(String(32), nullable=True)
    is_skipped = Column(Boolean, default=False)
    is_answered = Column(Boolean, default=False)
    answered_at = Column(DateTime, nullable=True)
    order_index = Column(Integer, default=0)
    recruiter_approved = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    session = relationship("InterviewSessionModel", back_populates="questions")

class InterviewEvidenceProposalModel(Base):
    __tablename__ = "interview_evidence_proposals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    verbatim_excerpt = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    proposed_status = Column(String(32), nullable=False)
    justification = Column(Text, nullable=False)
    confidence_score = Column(Float, default=1.0)
    review_status = Column(String(32), default="PENDING")  # PENDING | APPROVED | REJECTED
    recruiter_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    session = relationship("InterviewSessionModel", back_populates="proposals")
    requirement = relationship("RequirementModel")

class ScoreSnapshotModel(Base):
    __tablename__ = "score_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    overall_score = Column(Float, nullable=False)
    must_have_score = Column(Float, nullable=False)
    nice_to_have_score = Column(Float, nullable=False)
    experience_score = Column(Float, nullable=False)
    formula_representation = Column(Text, nullable=False)
    breakdown_json = Column(Text, nullable=False)
    calculation_version = Column(String(16), default="v1.0")
    created_at = Column(DateTime, default=utc_now)

    candidate = relationship("CandidateModel", back_populates="score_snapshots")

class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(36), nullable=False)
    actor = Column(String(64), nullable=False)  # SYSTEM_AGENT | RECRUITER
    action = Column(String(64), nullable=False)  # ROLE_CREATED | CANDIDATE_INGESTED | ...
    details_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)
