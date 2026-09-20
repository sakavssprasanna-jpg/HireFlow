import json
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from ..domain.enums import EvidenceStatus, RequirementCategory, SourceType, AuditAction, AuditActor
from ..domain.schemas import (
    CandidateUploadResponse,
    CandidateRead,
    FitScoreBreakdown,
    SecurityScanResult
)
from ..db.models import (
    RoleModel,
    RequirementModel,
    CandidateModel,
    CandidateDocumentModel,
    EvidenceClaimModel,
    ScoreSnapshotModel,
    AuditEventModel
)
from .document_parser import DocumentParser, FileValidationError, DocumentParsingError
from .security_scanner import SecurityScanner
from .pii_anonymizer import PIIAnonymizer
from .quote_verifier import QuoteVerifier
from .scoring_engine import DeterministicScoringEngine

class CandidateIngestionService:
    """
    Orchestrates the secure candidate document ingestion pipeline:
    Validate -> Extract -> Security Scan -> Quarantine Check -> PII Scrub -> Evidence Verify -> Deterministic Score.
    """

    @classmethod
    def ingest_candidate_resume(
        cls,
        db: Session,
        role_id: str,
        filename: str,
        file_bytes: bytes,
        candidate_name_hint: Optional[str] = None
    ) -> CandidateUploadResponse:
        # 1. Verify Role exists in DB
        role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
        if not role:
            raise ValueError(f"Role with ID '{role_id}' not found.")

        # 2. Document Parsing & Validation
        doc_content = DocumentParser.parse_document(filename, file_bytes)

        # 3. Prompt-Injection Security Scan
        scan_result = SecurityScanner.scan_text(doc_content.full_text)

        # Candidate Alias generation (e.g. Candidate #101)
        candidate_count = db.query(CandidateModel).filter(CandidateModel.role_id == role_id).count()
        alias = f"Candidate #{101 + candidate_count}"
        name = candidate_name_hint if candidate_name_hint else f"Applicant {candidate_count + 1}"

        # 4. Handle Quarantine Case (Adversarial Document)
        if scan_result.quarantined:
            candidate = CandidateModel(
                role_id=role_id,
                full_name=name,
                anonymous_alias=alias,
                years_experience=0.0,
                quarantined=True,
                quarantine_reason=scan_result.quarantine_reason
            )
            db.add(candidate)
            db.flush()

            doc_record = CandidateDocumentModel(
                candidate_id=candidate.id,
                filename=filename,
                file_type=doc_content.file_type,
                raw_text=doc_content.full_text,
                sanitized_text=scan_result.sanitized_preview,
                file_hash=doc_content.file_hash
            )
            db.add(doc_record)

            audit_event = AuditEventModel(
                entity_type="CANDIDATE",
                entity_id=candidate.id,
                actor=AuditActor.SYSTEM_AGENT.value,
                action=AuditAction.SECURITY_QUARANTINE.value,
                details_json=json.dumps({
                    "reason": scan_result.quarantine_reason,
                    "matched_rules": scan_result.matched_rules,
                    "severity": scan_result.severity,
                    "filename": filename
                })
            )
            db.add(audit_event)
            db.commit()
            db.refresh(candidate)

            # CRITICAL SECURITY RULE: Quarantined candidate halts immediately.
            # ZERO downstream AI calls, ZERO automated ranking/scoring.
            return CandidateUploadResponse(
                candidate=CandidateRead.model_validate(candidate),
                document_id=doc_record.id,
                security_scan=scan_result,
                blind_preview=scan_result.sanitized_preview,
                fit_score=None
            )

        # 5. Handle Safe Document: PII Anonymization
        pii_result = PIIAnonymizer.anonymize_text(
            text=doc_content.full_text,
            candidate_name=name,
            alias=alias
        )

        candidate = CandidateModel(
            role_id=role_id,
            full_name=name,
            anonymous_alias=alias,
            years_experience=0.0,
            quarantined=False,
            quarantine_reason=None
        )
        db.add(candidate)
        db.flush()

        doc_record = CandidateDocumentModel(
            candidate_id=candidate.id,
            filename=filename,
            file_type=doc_content.file_type,
            raw_text=doc_content.full_text,
            sanitized_text=pii_result.masked_text,
            file_hash=doc_content.file_hash
        )
        db.add(doc_record)

        db.add(AuditEventModel(
            entity_type="CANDIDATE",
            entity_id=candidate.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.CANDIDATE_INGESTED.value,
            details_json=json.dumps({
                "filename": filename,
                "file_type": doc_content.file_type,
                "redacted_counts": pii_result.redacted_counts
            })
        ))

        # 6. Extract Claims & Verify Quotes against Raw Source
        # Fetch requirements for this role
        requirements = db.query(RequirementModel).filter(RequirementModel.role_id == role_id).all()
        claims_by_req: Dict[str, EvidenceStatus] = {}

        for req in requirements:
            # Deterministic initial extraction based on keyword / phrase presence in raw text
            req_name_lower = req.name.lower()
            raw_text_lower = doc_content.full_text.lower()

            if req_name_lower in raw_text_lower:
                # Find an actual sentence excerpt in raw text
                idx = raw_text_lower.find(req_name_lower)
                snippet_start = max(0, idx - 40)
                snippet_end = min(len(doc_content.full_text), idx + len(req.name) + 60)
                extracted_quote = doc_content.full_text[snippet_start:snippet_end].strip()

                # Verify quote via QuoteVerifier
                verification = QuoteVerifier.verify_quote(
                    raw_source_text=doc_content.full_text,
                    quote=extracted_quote,
                    sections=doc_content.sections
                )

                if verification.valid:
                    status = EvidenceStatus.PROVEN
                    warning = None
                else:
                    # Non-verifiable quote forced to UNVERIFIED
                    status = EvidenceStatus.UNVERIFIED
                    warning = "UNVERIFIED_HALLUCINATION_PREVENTED"

                claim = EvidenceClaimModel(
                    candidate_id=candidate.id,
                    requirement_id=req.id,
                    source_document_id=doc_record.id,
                    source_type=SourceType.RESUME.value,
                    section_reference=verification.section_name or "Resume",
                    verbatim_quote=verification.matched_text if verification.valid else extracted_quote,
                    start_offset=verification.start_offset,
                    end_offset=verification.end_offset,
                    status=status.value,
                    reasoning=f"Identified keyword match in candidate resume. ({warning or 'Verified quote'})",
                    confidence=0.9 if verification.valid else 0.4
                )
                db.add(claim)
                claims_by_req[req.id] = status
            else:
                # Not found in document
                claim = EvidenceClaimModel(
                    candidate_id=candidate.id,
                    requirement_id=req.id,
                    source_document_id=doc_record.id,
                    source_type=SourceType.RESUME.value,
                    section_reference="Not Located",
                    verbatim_quote=None,
                    status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL.value,
                    reasoning="No evidence found in candidate documents for this requirement.",
                    confidence=1.0
                )
                db.add(claim)
                claims_by_req[req.id] = EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL

        # 7. Deterministic Scoring Calculation
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
            required_years_exp=role.min_years_experience,
            weights={
                "must_have": role.weight_must_have,
                "nice_to_have": role.weight_nice_to_have,
                "experience": role.weight_experience
            }
        )

        # Persist Score Snapshot
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
            entity_type="CANDIDATE",
            entity_id=candidate.id,
            actor=AuditActor.SYSTEM_AGENT.value,
            action=AuditAction.SCORE_CALCULATED.value,
            details_json=json.dumps({
                "overall_score": score_breakdown.overall_score,
                "formula": score_breakdown.formula_representation
            })
        ))

        db.commit()
        db.refresh(candidate)

        return CandidateUploadResponse(
            candidate=CandidateRead.model_validate(candidate),
            document_id=doc_record.id,
            security_scan=scan_result,
            blind_preview=pii_result.masked_text[:500],
            fit_score=score_breakdown
        )
