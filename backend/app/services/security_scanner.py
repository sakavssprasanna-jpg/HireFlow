import re
from typing import List, Tuple
from ..domain.schemas import SecurityScanResult

class SecurityScanner:
    """
    Deterministic security scanner detecting adversarial prompt injections,
    role-switching attempts, delimiter attacks, and hidden payloads in candidate documents.
    """

    # Rule definitions: (rule_id, regex_pattern, severity, description)
    INJECTION_RULES: List[Tuple[str, str, str, str]] = [
        (
            "ROLE_INJECTION_BRACKET",
            r"(?i)\[\s*(system|assistant|admin|root|developer)\s*(:|\])",
            "CRITICAL",
            "Attempt to inject role prefix using bracket syntax (e.g. [SYSTEM:])."
        ),
        (
            "ROLE_INJECTION_TAG",
            r"(?i)<\s*(system|assistant|developer|evaluator)\s*>",
            "CRITICAL",
            "Attempt to inject XML-style system/assistant role tags."
        ),
        (
            "ROLE_INJECTION_LINE_START",
            r"(?im)^\s*(system|assistant|admin|root|developer)\s*:",
            "CRITICAL",
            "Attempt to simulate system/assistant control message at line start."
        ),
        (
            "INSTRUCTION_OVERRIDE_IGNORE",
            r"(?i)(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier|former)?\s*(instructions|prompts|directions|rules|guidelines)",
            "CRITICAL",
            "Explicit instruction hierarchy attack attempting to override system prompt."
        ),
        (
            "EVALUATION_TAMPERING",
            r"(?i)(override\s+(the\s+)?(evaluation|scoring|rubric|criteria|system)|award\s+(\d+|100%|full|top)\s+(score|points|rating)|mark\s+this\s+candidate\s+(as\s+)?(hired|perfect|exceptional)|(change|set|give)\s+(this\s+)?(candidate'?s?\s+)?score\s+(to\s+)?(100%?|\d+|top|maximum)|mark\s+all\s+requirements\s+(as\s+)?proven)",
            "CRITICAL",
            "Direct adversarial attempt to manipulate scoring or evaluation outcome."
        ),
        (
            "DEVELOPER_MESSAGE_ATTACK",
            r"(?i)(developer\s+message\s*:|system\s+instructions\s*:|you\s+(must\s+now\s+act\s+as|are\s+now\s+(the\s+)?(hiring\s+manager|recruiter|evaluator|admin|interviewer)))",
            "HIGH",
            "Attempt to simulate developer, hiring manager, or system control channel."
        ),
        (
            "DELIMITER_HIJACK",
            r"(?i)(```\s*(system|prompt|instruction|override)|<!--\s*(system|prompt|instruction))",
            "HIGH",
            "Attempt to break out of context boundaries using codeblock or comment delimiters."
        ),
        (
            "FAKE_TOOL_INJECTION",
            r"(?i)(call_tool\s*:|<tool_call>|Function_Call\s*:|json\s*\{\s*\"action\"\s*:\s*\"hire\")",
            "HIGH",
            "Attempt to trick agent tool executor with fabricated tool calling syntax."
        ),
        (
            "ZERO_WIDTH_CHARACTER_PAYLOAD",
            r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E]{2,}",
            "HIGH",
            "Suspicious sequence of consecutive zero-width or invisible Unicode characters."
        ),
    ]

    @classmethod
    def scan_text(cls, text: str) -> SecurityScanResult:
        """
        Scan extracted document text against deterministic security rules.
        Returns a structured SecurityScanResult.
        """
        matched_rules: List[str] = []
        highest_severity = "SAFE"
        quarantine_reasons: List[str] = []

        # Strip zero-width characters for de-obfuscated content inspection
        deobfuscated_text = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E]", "", text)

        for rule_id, pattern, severity, description in cls.INJECTION_RULES:
            # Check both raw text (catches zero-width sequence rule) and deobfuscated text (catches hidden keywords)
            if re.search(pattern, text) or re.search(pattern, deobfuscated_text):
                matched_rules.append(f"{rule_id} ({severity}): {description}")
                quarantine_reasons.append(description)
                if severity == "CRITICAL" or highest_severity != "CRITICAL":
                    highest_severity = severity

        is_suspicious = len(matched_rules) > 0
        quarantined = is_suspicious and highest_severity in {"HIGH", "CRITICAL"}

        quarantine_reason_str = "; ".join(quarantine_reasons) if quarantine_reasons else None

        # Build sanitized preview (strip matched adversarial patterns for safe preview)
        sanitized_preview = text[:500]
        if quarantined:
            # Mask out any injection triggers in preview
            for _, pattern, _, _ in cls.INJECTION_RULES:
                sanitized_preview = re.sub(pattern, "[MALICIOUS_INJECTION_REDACTED]", sanitized_preview)

        return SecurityScanResult(
            is_suspicious=is_suspicious,
            quarantined=quarantined,
            severity=highest_severity,
            matched_rules=matched_rules,
            quarantine_reason=quarantine_reason_str,
            sanitized_preview=sanitized_preview.strip()
        )
