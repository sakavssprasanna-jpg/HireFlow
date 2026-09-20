import re
from typing import Dict, List, Tuple
from pydantic import BaseModel

class PIIAnonymizationResult(BaseModel):
    original_text: str
    masked_text: str
    anonymized_alias: str
    redacted_counts: Dict[str, int]

class PIIAnonymizer:
    """
    Deterministic PII scrubbing service for Blind Screening Mode.
    Masks personal demographic identifiers while preserving original source text
    for authoritative citation verification.
    """

    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
    PHONE_PATTERN = r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    LINK_PATTERN = r"\b(https?://)?(www\.)?(linkedin\.com/in/[A-Za-z0-9_-]+|github\.com/[A-Za-z0-9_-]+)\b"
    GRAD_YEAR_PATTERN = r"\b(Graduated|Class of|B\.?S\.?|M\.?S\.?|B\.?Tech|B\.?E\.?|Degree|Graduation|Completed)\s*[:\-\s]?\s*(19\d{2}|20\d{2})\b"

    @classmethod
    def anonymize_text(cls, text: str, candidate_name: str, alias: str) -> PIIAnonymizationResult:
        """
        Produce an anonymized presentation text replacing candidate name, contact info,
        and demographic markers with neutral tokens.
        """
        masked = text
        redacted_counts: Dict[str, int] = {
            "name": 0,
            "email": 0,
            "phone": 0,
            "links": 0,
            "graduation_year": 0
        }

        # 1. Mask Candidate Name (if provided)
        if candidate_name and len(candidate_name.strip()) > 1:
            name_pattern = rf"\b{re.escape(candidate_name.strip())}\b"
            matches = len(re.findall(name_pattern, masked, flags=re.IGNORECASE))
            if matches > 0:
                masked = re.sub(name_pattern, alias, masked, flags=re.IGNORECASE)
                redacted_counts["name"] = matches

        # 2. Mask Emails
        email_matches = len(re.findall(cls.EMAIL_PATTERN, masked))
        if email_matches > 0:
            masked = re.sub(cls.EMAIL_PATTERN, "[EMAIL_REDACTED]", masked)
            redacted_counts["email"] = email_matches

        # 3. Mask Phone Numbers
        phone_matches = len(re.findall(cls.PHONE_PATTERN, masked))
        if phone_matches > 0:
            masked = re.sub(cls.PHONE_PATTERN, "[PHONE_REDACTED]", masked)
            redacted_counts["phone"] = phone_matches

        # 4. Mask Links (LinkedIn, GitHub)
        link_matches = len(re.findall(cls.LINK_PATTERN, masked, flags=re.IGNORECASE))
        if link_matches > 0:
            masked = re.sub(cls.LINK_PATTERN, "[LINK_REDACTED]", masked, flags=re.IGNORECASE)
            redacted_counts["links"] = link_matches

        # 5. Mask Graduation Years (prevents age bias)
        def replace_year(m):
            return f"{m.group(1)} [YEAR_REDACTED]"

        grad_matches = len(re.findall(cls.GRAD_YEAR_PATTERN, masked, flags=re.IGNORECASE))
        if grad_matches > 0:
            masked = re.sub(cls.GRAD_YEAR_PATTERN, replace_year, masked, flags=re.IGNORECASE)
            redacted_counts["graduation_year"] = grad_matches

        return PIIAnonymizationResult(
            original_text=text,
            masked_text=masked,
            anonymized_alias=alias,
            redacted_counts=redacted_counts
        )
