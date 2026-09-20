import re
import time
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from .base import BaseLLMProvider, ProviderMetadata, ProviderResponse
from ..domain.enums import AIMode, RequirementCategory, EvidenceStatus
from ..domain.schemas import (
    JDAnalysisOutput,
    JDAnalysisRequirement,
    EvidenceMatchingOutput,
    ExtractedCandidateClaim,
    InterviewQuestionOutput,
    GeneratedQuestion,
    InterviewEvidenceOutput,
    InterviewEvidenceItem
)

T = TypeVar("T", bound=BaseModel)

class OfflineFallbackProvider(BaseLLMProvider):
    """
    Deterministic offline fallback provider.
    NOTE: This is NOT an AI model.
    It executes deterministic rule-based pattern matching to guarantee system operation
    during network disconnection, testing, or API rate-limiting.
    """

    def __init__(self):
        self.provider_name = "OfflineFallbackEngine"
        self.model_name = "DeterministicRuleEngine-v1"

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.model_name,
            ai_mode=AIMode.OFFLINE_FALLBACK,
            is_fallback=True,
            tokens_prompt=0,
            tokens_completion=0,
            latency_ms=0.5
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None
    ) -> ProviderResponse:
        start_time = time.perf_counter()

        # Deterministic extraction logic based on target schema
        if schema == JDAnalysisOutput:
            data = self._fallback_jd_analysis(prompt)
        elif schema == EvidenceMatchingOutput:
            data = self._fallback_evidence_matching(prompt)
        elif schema == InterviewQuestionOutput:
            data = self._fallback_interview_questions(prompt)
        elif schema == InterviewEvidenceOutput:
            data = self._fallback_interview_evidence(prompt)
        else:
            raise ValueError(f"Schema {schema.__name__} not supported by OfflineFallbackProvider")

        duration_ms = (time.perf_counter() - start_time) * 1000

        metadata = ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.model_name,
            ai_mode=AIMode.OFFLINE_FALLBACK,
            is_fallback=True,
            tokens_prompt=0,
            tokens_completion=0,
            latency_ms=round(duration_ms, 2)
        )

        return ProviderResponse(
            data=data,
            metadata=metadata,
            raw_output="[Deterministic Fallback Output]"
        )

    def _fallback_jd_analysis(self, prompt: str) -> JDAnalysisOutput:
        """Deterministic keyword-based JD criteria extractor."""
        lines = [line.strip() for line in prompt.splitlines() if line.strip()]
        role_title = lines[0] if lines else "Software Engineer"
        
        # Rule-based common technical criteria detection
        criteria = []
        lower_text = prompt.lower()
        
        keywords_map = {
            "python": ("Python Programming", RequirementCategory.MUST_HAVE, "Core backend development with Python"),
            "kubernetes": ("Kubernetes & Container Orchestration", RequirementCategory.MUST_HAVE, "Production container lifecycle and cluster management"),
            "terraform": ("Terraform & Infrastructure as Code", RequirementCategory.MUST_HAVE, "Automated infrastructure provisioning"),
            "aws": ("AWS Cloud Infrastructure", RequirementCategory.MUST_HAVE, "Managing cloud services and distributed architectures"),
            "ci/cd": ("CI/CD Automation", RequirementCategory.NICE_TO_HAVE, "Continuous integration and delivery pipelines"),
            "docker": ("Docker Containerization", RequirementCategory.MUST_HAVE, "Container packaging and microservices"),
            "go": ("Golang Microservices", RequirementCategory.NICE_TO_HAVE, "High performance systems programming"),
        }

        for kw, (name, cat, desc) in keywords_map.items():
            if kw in lower_text:
                criteria.append(JDAnalysisRequirement(name=name, category=cat, description=desc, weight=1.0))

        if not criteria:
            criteria.append(JDAnalysisRequirement(
                name="Core Technical Competency",
                category=RequirementCategory.MUST_HAVE,
                description="Demonstrated technical execution",
                weight=1.0
            ))

        return JDAnalysisOutput(
            role_title=role_title[:100],
            department="Engineering",
            min_years_experience=3,
            requirements=criteria
        )

    def _fallback_evidence_matching(self, prompt: str) -> EvidenceMatchingOutput:
        """Deterministic candidate claim extractor parsing requirements and resume text from prompt."""
        # Check if prompt contains structured sections
        requirements = []
        candidate_text = prompt
        
        # Parse requirement lines if present
        for line in prompt.splitlines():
            line_str = line.strip()
            if line_str.startswith("REQUIREMENT:") or line_str.startswith("- REQUIREMENT:"):
                # Format: REQUIREMENT: <name> | CATEGORY: <cat>
                parts = line_str.split("|")
                name_part = parts[0].replace("- REQUIREMENT:", "").replace("REQUIREMENT:", "").strip()
                if name_part:
                    requirements.append(name_part)

        # Extract resume text if separated by header
        if "CANDIDATE_RESUME_TEXT:" in prompt:
            candidate_text = prompt.split("CANDIDATE_RESUME_TEXT:", 1)[1]

        claims = []
        if requirements:
            lower_candidate_text = candidate_text.lower()
            sentences = [s.strip() for s in candidate_text.replace("\n", ". ").split(". ") if len(s.strip()) > 5]

            GENERIC_WORDS = {"engineering", "engineer", "software", "developer", "development", "systems", "system", "testing", "management", "experience"}

            for req_name in requirements:
                keywords = [w.lower() for w in req_name.split() if len(w) > 3 and w.lower() not in GENERIC_WORDS]
                if not keywords:
                    keywords = [req_name.lower()]

                matched_sentence = None
                for sentence in sentences:
                    s_low = sentence.lower()
                    if req_name.lower() in s_low or any(kw in s_low for kw in keywords):
                        matched_sentence = sentence
                        break

                if matched_sentence:
                    claims.append(ExtractedCandidateClaim(
                        requirement_name=req_name,
                        status=EvidenceStatus.PROVEN,
                        verbatim_quote=matched_sentence,
                        section_reference="Experience",
                        reasoning=f"Found explicit mention of '{req_name}' in candidate material.",
                        confidence=0.9
                    ))
                else:
                    claims.append(ExtractedCandidateClaim(
                        requirement_name=req_name,
                        status=EvidenceStatus.NOT_FOUND_IN_PROVIDED_MATERIAL,
                        verbatim_quote=None,
                        section_reference="Not Located",
                        reasoning=f"No direct evidence found in candidate document for '{req_name}'.",
                        confidence=1.0
                    ))
        else:
            # Legacy/default fallback
            claims.append(ExtractedCandidateClaim(
                requirement_name="Core Technical Competency",
                status=EvidenceStatus.PARTIALLY_PROVEN,
                verbatim_quote="Experience in cloud computing and software delivery.",
                section_reference="Experience",
                reasoning="Keyword match found in experience section.",
                confidence=0.7
            ))

        return EvidenceMatchingOutput(
            candidate_name="Candidate (Offline Parsed)",
            years_experience=3.5,
            claims=claims
        )

    def _fallback_interview_questions(self, prompt: str) -> InterviewQuestionOutput:
        """Deterministic question generator dynamically conditioned on resume anchors, gaps, requirements, and experience level."""
        parsed_gaps = []
        parsed_requirements = []
        parsed_resume_highlights = []
        exp_level = "Mid Level"
        is_5min = False
        parsed_req_resume = None
        parsed_req_gap = None

        in_reqs_section = False
        in_gaps_section = False
        in_resume_section = False

        for line in prompt.splitlines():
            line_str = line.strip()
            if "EXPERIENCE LEVEL:" in line_str.upper():
                parts = line_str.split(":", 1)
                if len(parts) > 1:
                    exp_level = parts[1].strip()
            elif "INTERVIEW DURATION:" in line_str.upper():
                if "5 MINUTES" in line_str.upper() or "5 MIN" in line_str.upper():
                    is_5min = True
            elif "REQUIRED MIX:" in line_str.upper():
                mix_match = re.search(r'(\d+)\s+RESUME_GROUNDED.*?(\d+)\s+GAP_VALIDATION', line_str, re.IGNORECASE)
                if mix_match:
                    parsed_req_resume = int(mix_match.group(1))
                    parsed_req_gap = int(mix_match.group(2))
            elif "ROLE EVALUATION CRITERIA:" in line_str.upper():
                in_reqs_section = True
                in_gaps_section = False
                in_resume_section = False
            elif "IDENTIFIED CANDIDATE GAPS" in line_str.upper():
                in_reqs_section = False
                in_gaps_section = True
                in_resume_section = False
            elif "CANDIDATE RESUME" in line_str.upper() or "RESUME EVIDENCE POOL" in line_str.upper():
                in_reqs_section = False
                in_gaps_section = False
                in_resume_section = True
            elif "JOB DESCRIPTION" in line_str.upper() or "INSTRUCTIONS:" in line_str.upper():
                in_reqs_section = False
                in_gaps_section = False
                in_resume_section = False
            elif in_gaps_section and (line_str.startswith("GAP:") or line_str.startswith("- GAP:")):
                parts = line_str.split("|")
                req_name = parts[0].replace("- GAP:", "").replace("GAP:", "").strip()
                priority = parts[1].replace("PRIORITY:", "").strip() if len(parts) > 1 else "CRITICAL"
                reason = parts[2].replace("REASON:", "").strip() if len(parts) > 2 else "Candidate lacked documented evidence."
                parsed_gaps.append((req_name, priority, reason))
            elif in_reqs_section and (line_str.startswith("REQUIREMENT:") or line_str.startswith("- REQUIREMENT:")):
                parts = line_str.split("|")
                req_name = parts[0].replace("- REQUIREMENT:", "").replace("REQUIREMENT:", "").strip()
                desc = parts[1].replace("DESCRIPTION:", "").strip() if len(parts) > 1 else ""
                parsed_requirements.append((req_name, desc))
            elif in_resume_section and line_str:
                # Handle "- ANCHOR [HIGH | ...]: "quote"" or bullet quotes
                if '"' in line_str:
                    first_q = line_str.find('"')
                    last_q = line_str.rfind('"')
                    if first_q != -1 and last_q != -1 and last_q > first_q:
                        extracted_quote = line_str[first_q + 1 : last_q].strip()
                        extracted_lower = extracted_quote.lower()
                        if (
                            len(extracted_quote) >= 15
                            and not any(neg in extracted_lower for neg in ["did not document", "does not document", "not documented", "no documented", "lacks experience", "no experience", "missing documentation", "no evidence"])
                            and not any(extracted_lower.startswith(neg) for neg in ["did not ", "does not ", "do not ", "lacks ", "lacking ", "no ", "without "])
                            and extracted_quote not in parsed_resume_highlights
                        ):
                            parsed_resume_highlights.append(extracted_quote)
                else:
                    clean = line_str.lstrip("-*•# \t0123456789.)").strip()
                    clean_lower = clean.lower()
                    if (
                        len(clean) >= 20
                        and not clean_lower.startswith(("http", "www", "email", "phone", "resume", "curriculum"))
                        and not any(neg in clean_lower for neg in ["did not document", "does not document", "not documented", "no documented", "lacks experience", "no experience", "missing documentation", "no evidence"])
                        and not any(clean_lower.startswith(neg) for neg in ["did not ", "does not ", "do not ", "lacks ", "lacking ", "no ", "without "])
                    ):
                        if clean not in parsed_resume_highlights:
                            parsed_resume_highlights.append(clean)

        exp_lower = exp_level.lower()
        is_entry = "entry" in exp_lower or "0" in exp_lower
        is_junior = "junior" in exp_lower or "1" in exp_lower
        is_senior = "senior" in exp_lower or "5" in exp_lower

        target_count = len(parsed_gaps) if parsed_gaps else (len(parsed_requirements) if parsed_requirements else 2)
        for line in prompt.splitlines():
            line_str = line.strip()
            if "TARGET QUESTION COUNT:" in line_str.upper():
                try:
                    target_count = int(line_str.split(":", 1)[1].strip())
                except Exception:
                    pass

        # Use parsed mix if explicitly given, otherwise compute
        if parsed_req_resume is not None and parsed_req_gap is not None:
            target_resume_count = parsed_req_resume
            target_gap_count = parsed_req_gap
        else:
            pool_size = len(parsed_resume_highlights)
            if pool_size == 0:
                target_resume_count = 0
            else:
                if is_5min:
                    base_res = 1
                elif target_count <= 4:
                    base_res = 2
                elif target_count <= 7:
                    base_res = 3
                elif target_count <= 12:
                    base_res = 6
                elif target_count <= 16:
                    base_res = 8
                else:
                    base_res = target_count // 2
                max_cap = pool_size * 2
                target_resume_count = max(1, min(base_res, max_cap))
                if parsed_gaps:
                    target_resume_count = min(target_resume_count, target_count - 1)
            target_gap_count = target_count - target_resume_count

        resume_questions: List[GeneratedQuestion] = []
        gap_questions: List[GeneratedQuestion] = []

        # 1. Generate RESUME_GROUNDED questions distributed across anchors and dimensions
        if parsed_resume_highlights:
            for r_idx in range(target_resume_count):
                anchor_idx = r_idx % len(parsed_resume_highlights)
                highlight = parsed_resume_highlights[anchor_idx]
                dim_idx = (r_idx // len(parsed_resume_highlights) + r_idx) % 5

                # Match requirement by keyword overlap
                matched_req_name = parsed_requirements[r_idx % len(parsed_requirements)][0] if parsed_requirements else "Core Experience"
                for req_name, _ in parsed_requirements:
                    if any(word.lower() in highlight.lower() for word in req_name.split() if len(word) > 3):
                        matched_req_name = req_name
                        break

                if dim_idx == 0:
                    # Ownership & Contribution
                    if is_entry:
                        q_text = f"In your resume you noted: \"{highlight}\". What was your personal contribution and learning outcome in this project versus your team members or peers?"
                        probing = f"Probing personal ownership, foundational understanding, and lessons learned for {exp_level} candidate."
                    elif is_junior:
                        q_text = f"In your resume you noted: \"{highlight}\". Which parts of the codebase did you independently implement, test, and maintain versus existing framework code?"
                        probing = f"Probing hands-on code ownership and component boundaries for {exp_level} candidate."
                    elif is_senior:
                        q_text = f"In your resume you noted: \"{highlight}\". How did you exercise technical leadership, architectural governance, and team ownership to deliver this initiative?"
                        probing = f"Probing organizational technical leadership and governance for {exp_level} candidate."
                    else: # Mid level
                        q_text = f"In your resume you highlighted: \"{highlight}\". What was your personal ownership in architecting and delivering this service end-to-end?"
                        probing = f"Probing direct service ownership and technical agency for {exp_level} candidate."
                    pos_sig = "Direct personal accountability, clear distinction between personal code and team contributions, specific commits/designs."
                    red_flag = "Vague passive language ('we did'), inability to isolate personal contributions."

                elif dim_idx == 1:
                    # Implementation & Architecture
                    if is_entry:
                        q_text = f"Regarding your work: \"{highlight}\", can you walk us through the fundamental concepts, programming languages, or libraries you used to implement the solution?"
                        probing = f"Probing implementation fundamentals and coursework/project execution for {exp_level} candidate."
                    elif is_junior:
                        q_text = f"Regarding your work: \"{highlight}\", can you describe your hands-on implementation workflow, code structure, and debugging methods?"
                        probing = f"Probing implementation practices, code maintainability, and testing for {exp_level} candidate."
                    elif is_senior:
                        q_text = f"Regarding your work: \"{highlight}\", could you detail the overarching system architecture, component boundaries, and high-availability design you established?"
                        probing = f"Probing distributed systems architecture and system resilience for {exp_level} candidate."
                    else: # Mid level
                        q_text = f"Regarding your work: \"{highlight}\", could you detail the technical architecture, data flow, and key implementation decisions you made?"
                        probing = f"Probing architectural depth and hands-on implementation for {exp_level} candidate."
                    pos_sig = "Precise component diagrams, clear protocol/data flow explanations, concrete code rationale."
                    red_flag = "Superficial buzzword drops without implementation substance."

                elif dim_idx == 2:
                    # Trade-offs & Technical Alternatives
                    if is_entry:
                        q_text = f"When working on: \"{highlight}\", did you explore alternative approaches or tools, and what guided your technical choice?"
                        probing = f"Probing technical curiosity and initial decision-making for {exp_level} candidate."
                    elif is_junior:
                        q_text = f"While executing: \"{highlight}\", what technical alternatives did you evaluate and why was your chosen approach optimal?"
                        probing = f"Probing technical trade-offs and pragmatic tool selection for {exp_level} candidate."
                    elif is_senior:
                        q_text = f"When executing: \"{highlight}\", what strategic technical trade-offs, paradigm alternatives, and long-term maintainability constraints drove your architectural decisions?"
                        probing = f"Probing strategic trade-off evaluation and architectural foresight for {exp_level} candidate."
                    else: # Mid level
                        q_text = f"When executing: \"{highlight}\", what architectural trade-offs (e.g., latency vs simplicity, speed vs reliability) did you evaluate and why?"
                        probing = f"Probing balanced trade-off analysis and technical judgment for {exp_level} candidate."
                    pos_sig = "Balanced trade-off analysis (latency vs throughput, consistency vs availability, complexity vs speed)."
                    red_flag = "Dogmatic choices without evaluating trade-offs or constraints."

                elif dim_idx == 3:
                    # Scale & Failure Modes
                    if is_entry:
                        q_text = f"In your project: \"{highlight}\", what unexpected bugs, edge cases, or errors did you encounter, and how did you debug them?"
                        probing = f"Probing debugging technique and problem-solving clarity for {exp_level} candidate."
                    elif is_junior:
                        q_text = f"In your work on: \"{highlight}\", how did your implementation handle runtime exceptions, failure conditions, or unexpected edge cases?"
                        probing = f"Probing runtime exception handling and defensive coding for {exp_level} candidate."
                    elif is_senior:
                        q_text = f"Reflecting on: \"{highlight}\", what was the peak production scale, how did you architect against catastrophic failure modes, and what telemetry did you rely on?"
                        probing = f"Probing high-scale resilience, disaster recovery, and operational telemetry for {exp_level} candidate."
                    else: # Mid level
                        q_text = f"Reflecting on: \"{highlight}\", what was the operational scale or throughput, and how did your architecture prevent outages and handle failure modes?"
                        probing = f"Probing operational scale and failure mitigation for {exp_level} candidate."
                    pos_sig = "Concrete volume metrics, failure isolation, telemetry monitoring, systematic root-cause analysis."
                    red_flag = "Ignorance of failure modes, untested assumptions under load."

                else:
                    # Validation & Metrics
                    if is_entry:
                        q_text = f"Regarding your accomplishment: \"{highlight}\", how did you verify that the project was functioning as expected, and what was the outcome?"
                        probing = f"Probing project validation and results for {exp_level} candidate."
                    elif is_junior:
                        q_text = f"In your work on: \"{highlight}\", how did you validate code performance and verify that the requirements were accurately met?"
                        probing = f"Probing code validation and requirement testing for {exp_level} candidate."
                    elif is_senior:
                        q_text = f"You highlighted: \"{highlight}\". What empirical metrics, SLA/SLO uptime, and measurable organizational outcomes validated the success of this work?"
                        probing = f"Probing organizational business impact and empirical SLA validation for {exp_level} candidate."
                    else: # Mid level
                        q_text = f"You highlighted: \"{highlight}\". How did you measure, monitor, and validate the quantitative performance improvements or business impact?"
                        probing = f"Probing empirical metrics, telemetry tracking, and performance verification for {exp_level} candidate."
                    pos_sig = "Empirical metrics, latency reductions, SLA/SLO tracking, clear quantifiable business value."
                    red_flag = "Unsubstantiated claims without metrics or verification criteria."

                est_sec = 150 if is_5min else (120 if dim_idx in (1, 2) else (90 if dim_idx == 0 else 150))

                resume_questions.append(GeneratedQuestion(
                    requirement_name=matched_req_name,
                    target_gap=f"Verified resume accomplishment: {highlight[:50]}...",
                    question=q_text,
                    probing_context=probing,
                    positive_signals=pos_sig,
                    red_flags=red_flag,
                    question_type="RESUME_GROUNDED",
                    reason=f"Probing candidate's documented achievement in resume: \"{highlight[:60]}...\"",
                    evidence_basis=highlight,
                    estimated_duration_seconds=est_sec
                ))

        # 2. Generate GAP_VALIDATION questions
        gap_pool = parsed_gaps if parsed_gaps else [(r[0], "HIGH", "Candidate lacked documented evidence.") for r in parsed_requirements]
        g_idx = 0
        while len(gap_questions) < target_gap_count and gap_pool:
            req_name, priority, reason = gap_pool[g_idx % len(gap_pool)]
            g_idx += 1

            if is_entry:
                question_text = f"As you begin your career, how have you built foundational knowledge in {req_name}, and what academic or project exposure do you have with it?"
                pos_sig = "Clear understanding of core principles, enthusiasm to learn, coursework or self-directed project demonstration."
                red_flag = "Unable to explain basic terminology, lack of interest in fundamental concepts."
            elif is_junior:
                question_text = f"Can you describe your hands-on experience implementing and debugging {req_name} in practical assignments or early production tasks?"
                pos_sig = "Concrete examples of writing and fixing code, understanding standard workflows, asking for help appropriately."
                red_flag = "Unfamiliarity with basic toolchain, passing off team work as personal work without implementation knowledge."
            elif is_senior:
                question_text = f"Regarding {req_name}, could you explain your architectural design decisions, scale considerations, and how you lead teams through complex technical trade-offs with it?"
                pos_sig = "High-level architectural vision, failure mode mitigations, performance benchmarks, and mentoring experience."
                red_flag = "Focusing purely on syntax, inability to discuss failure recovery, lack of architectural trade-off justification."
            else: # Mid level
                if "NOT_FOUND" in reason or "not found" in reason.lower() or "missing" in reason.lower():
                    question_text = f"The resume does not detail prior experience with {req_name}. Can you describe your hands-on production involvement, if any, with {req_name}?"
                elif "UNVERIFIED" in reason or "unverified" in reason.lower():
                    question_text = f"Regarding {req_name}, could you explain the technical architecture and your specific contributions to substantiate your experience?"
                else:
                    question_text = f"Could you walk us through a complex project where you utilized {req_name}, focusing on the biggest challenges you solved?"
                pos_sig = "Specific metrics, root cause analysis, clear personal ownership and design trade-offs."
                red_flag = "Surface-level buzzwords, passing blame, inability to explain underlying failure modes."

            est_sec = 150 if is_5min else (60 if is_entry else (120 if is_senior else 90))

            gap_questions.append(GeneratedQuestion(
                requirement_name=req_name,
                target_gap=reason,
                question=question_text,
                probing_context=f"Targeting a {priority} gap in {req_name} for a {exp_level} role.",
                positive_signals=pos_sig,
                red_flags=red_flag,
                question_type="GAP_VALIDATION",
                reason=reason or f"Validating missing coverage for {req_name}",
                evidence_basis="Role Requirement Gap / Missing Documentation in Resume",
                estimated_duration_seconds=est_sec
            ))

        # 3. Interleave questions: Resume, Gap, Resume, Gap...
        questions: List[GeneratedQuestion] = []
        r_iter = iter(resume_questions)
        g_iter = iter(gap_questions)

        for _ in range(target_count):
            if len(questions) % 2 == 0:
                nxt = next(r_iter, None) or next(g_iter, None)
            else:
                nxt = next(g_iter, None) or next(r_iter, None)
            if nxt:
                questions.append(nxt)

        if not questions:
            questions.append(GeneratedQuestion(
                requirement_name="Target Requirement Gap",
                target_gap="Lack of verified production context in resume",
                question="Can you walk us through a specific technical challenge where you had to solve a difficult problem under pressure?",
                probing_context="Probing general technical problem-solving depth.",
                positive_signals="Specific metrics, root cause analysis, clear personal ownership.",
                red_flags="Vague generalities, passing blame, inability to explain underlying failure modes.",
                question_type="GAP_VALIDATION",
                reason="Validating general problem solving",
                evidence_basis="Screening Assessment",
                estimated_duration_seconds=150 if is_5min else 120
            ))

        return InterviewQuestionOutput(questions=questions[:target_count])

    def _fallback_interview_evidence(self, prompt: str) -> InterviewEvidenceOutput:
        """Deterministic interview notes evidence parser extracting authentic quotes and contradiction checks."""
        requirements = []
        notes_text = prompt

        for line in prompt.splitlines():
            line_str = line.strip()
            if line_str.startswith("REQUIREMENT:") or line_str.startswith("- REQUIREMENT:"):
                parts = line_str.split("|")
                name_part = parts[0].replace("- REQUIREMENT:", "").replace("REQUIREMENT:", "").strip()
                if name_part:
                    requirements.append(name_part)

        if "INTERVIEW_NOTES:" in prompt:
            notes_text = prompt.split("INTERVIEW_NOTES:", 1)[1]

        evidence_items = []
        if requirements:
            lower_notes = notes_text.lower()
            sentences = [s.strip() for s in notes_text.replace("\n", ". ").split(". ") if len(s.strip()) > 5]

            negative_markers = [
                "only completed", "no production", "had not operated", "never used",
                "lacks experience", "only a course", "did not know", "failed", "unable to"
            ]

            GENERIC_WORDS = {"engineering", "engineer", "software", "developer", "development", "systems", "system", "testing", "management", "experience"}

            for req_name in requirements:
                keywords = [w.lower() for w in req_name.split() if len(w) > 3 and w.lower() not in GENERIC_WORDS]
                if not keywords:
                    keywords = [req_name.lower()]

                matching_sentences = []
                for sentence in sentences:
                    s_low = sentence.lower()
                    if req_name.lower() in s_low or any(kw in s_low for kw in keywords):
                        matching_sentences.append(sentence)

                if matching_sentences:
                    contradicting = [s for s in matching_sentences if any(neg in s.lower() for neg in negative_markers)]
                    if contradicting:
                        matched_sentence = contradicting[0]
                        status = EvidenceStatus.CONTRADICTED
                        reasoning = f"Candidate stated in interview they had no production experience with {req_name}."
                    else:
                        matched_sentence = matching_sentences[0]
                        status = EvidenceStatus.PROVEN
                        reasoning = f"Direct candidate answer validated hands-on competency for {req_name}."

                    evidence_items.append(InterviewEvidenceItem(
                        requirement_name=req_name,
                        updated_status=status,
                        verbatim_quote=matched_sentence,
                        reasoning=reasoning,
                        confidence_score=0.95
                    ))
        else:
            evidence_items.append(InterviewEvidenceItem(
                requirement_name="Target Requirement Gap",
                updated_status=EvidenceStatus.PROVEN,
                verbatim_quote="Explained production troubleshooting steps clearly during technical interview.",
                reasoning="Direct candidate answer validated competency during interview round.",
                confidence_score=0.9
            ))

        return InterviewEvidenceOutput(evidence_items=evidence_items)
