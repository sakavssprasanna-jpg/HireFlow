export type EvidenceStatus =
  | 'PROVEN'
  | 'PARTIALLY_PROVEN'
  | 'UNVERIFIED'
  | 'CONTRADICTED'
  | 'NOT_FOUND_IN_PROVIDED_MATERIAL';

export type RequirementCategory = 'MUST_HAVE' | 'NICE_TO_HAVE';

export type AIMode = 'LIVE_GEMINI' | 'LIVE_GROQ' | 'OFFLINE_FALLBACK';

export interface Requirement {
  id: string;
  role_id: string;
  name: string;
  category: RequirementCategory;
  description?: string;
  weight: number;
}

export interface Role {
  id: string;
  title: string;
  department?: string;
  raw_jd_text: string;
  min_years_experience: number;
  weight_must_have: number;
  weight_nice_to_have: number;
  weight_experience: number;
  requirements: Requirement[];
}

export interface Candidate {
  id: string;
  role_id: string;
  full_name: string;
  email?: string;
  phone?: string;
  anonymous_alias: string;
  years_experience: number;
  quarantined: boolean;
  quarantine_reason?: string;
  created_at: string;
}

export interface EvidenceClaim {
  id: string;
  candidate_id: string;
  requirement_id: string;
  source_type: 'RESUME' | 'INTERVIEW_NOTE';
  section_reference?: string;
  verbatim_quote?: string;
  start_offset?: number;
  end_offset?: number;
  status: EvidenceStatus;
  reasoning?: string;
  confidence: number;
  is_human_overridden: boolean;
  override_reason?: string;
}

export interface FitScoreBreakdown {
  candidate_id: string;
  overall_score: number;
  must_have_score: number;
  nice_to_have_score: number;
  experience_score: number;
  formula_representation: string;
  calculation_version: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  database_connected: boolean;
  ai_mode: AIMode;
  timestamp: string;
}

export interface SecurityScanResult {
  is_suspicious: boolean;
  quarantined: boolean;
  severity: string;
  matched_rules: string[];
  quarantine_reason?: string;
  sanitized_preview: string;
}

export interface CandidateUploadResponse {
  candidate: Candidate;
  document_id: string;
  security_scan: SecurityScanResult;
  blind_preview?: string;
  fit_score?: FitScoreBreakdown;
}

export type GapPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface CandidateGap {
  requirement_id: string;
  requirement_name: string;
  category: RequirementCategory;
  status: EvidenceStatus;
  priority: GapPriority;
  reason: string;
}

export interface CandidateGapsResponse {
  candidate_id: string;
  total_gaps: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  gaps: CandidateGap[];
}

export interface InterviewQuestion {
  id: string;
  session_id: string;
  requirement_id?: string;
  target_gap_description: string;
  question_text: string;
  probing_context?: string;
  expected_positive_signals?: string;
  expected_red_flags?: string;
  question_type?: string;
  reason?: string;
  evidence_basis?: string;
  experience_level?: string;
  priority?: string;
  estimated_duration_seconds?: number;
  candidate_answer?: string;
  extracted_evidence?: string;
  evidence_status?: string;
  is_skipped?: boolean;
  is_answered?: boolean;
  answered_at?: string;
  order_index?: number;
  recruiter_approved: boolean;
  created_at: string;
}

export type InterviewSessionStatus = 'DRAFT' | 'IN_PROGRESS' | 'COMPLETED' | 'REVIEWED' | 'QUARANTINED';
export type InterviewProposalStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export interface RequirementCoverageItem {
  requirement_id: string;
  requirement_name: string;
  category: 'MUST_HAVE' | 'NICE_TO_HAVE';
  status: EvidenceStatus;
  coverage_state: 'CONFIRMED' | 'PARTIAL' | 'UNRESOLVED' | 'NOT_ASSESSED';
  evidence_quote?: string;
  reasoning?: string;
}

export interface InterviewEvidenceProposal {
  id: string;
  session_id: string;
  requirement_id: string;
  requirement_name: string;
  verbatim_excerpt: string;
  start_offset?: number;
  end_offset?: number;
  proposed_status: EvidenceStatus;
  justification: string;
  confidence_score: number;
  review_status: InterviewProposalStatus;
  recruiter_notes?: string;
  created_at: string;
}

export interface InterviewSession {
  id: string;
  candidate_id: string;
  role_id?: string;
  interviewer_name?: string;
  interview_round: string;
  status: InterviewSessionStatus;
  experience_level?: string;
  duration_seconds?: number;
  remaining_seconds?: number;
  current_question_index?: number;
  summary_json?: string;
  raw_notes?: string;
  created_at: string;
  updated_at?: string;
  questions: InterviewQuestion[];
  proposals?: InterviewEvidenceProposal[];
}

export interface InterviewSummaryResponse {
  session_id: string;
  candidate_id: string;
  candidate_name: string;
  role_title: string;
  experience_level: string;
  duration_minutes: number;
  time_spent_seconds: number;
  questions_total: number;
  questions_answered: number;
  questions_skipped: number;
  resume_questions_count?: number;
  gap_questions_count?: number;
  followup_reserve_seconds?: number;
  pre_interview_score: number;
  post_interview_score: number;
  score_delta: number;
  pre_interview_gaps_count: number;
  post_interview_gaps_count: number;
  resolved_gaps_count: number;
  coverage_breakdown: RequirementCoverageItem[];
  transcript: Array<{
    order: number;
    requirement_id?: string;
    question: string;
    reason?: string;
    answer?: string;
    evidence?: string;
    status?: string;
    is_skipped?: boolean;
    is_answered?: boolean;
  }>;
  score_breakdown: FitScoreBreakdown;
  created_at: string;
  completed_at: string;
}

export interface AdaptiveInterviewState {
  session_id: string;
  candidate_id: string;
  candidate_name: string;
  role_id?: string;
  role_title: string;
  status: InterviewSessionStatus;
  experience_level: string;
  duration_seconds: number;
  remaining_seconds: number;
  current_question_index: number;
  total_questions: number;
  resume_questions_count?: number;
  gap_questions_count?: number;
  followup_reserve_seconds?: number;
  current_question?: InterviewQuestion | null;
  questions: InterviewQuestion[];
  coverage_breakdown: RequirementCoverageItem[];
  current_score: number;
  previous_score: number;
  summary?: InterviewSummaryResponse | null;
}

export interface InterviewEvidenceConfirmResponse {
  proposal: InterviewEvidenceProposal;
  previous_score: number;
  new_score: number;
  score_breakdown: FitScoreBreakdown;
  gaps_response: CandidateGapsResponse;
  changed_requirement_id: string;
}

export interface EvidenceAnalysisResponse {
  candidate_id: string;
  claims_analyzed: number;
  proven_count: number;
  partially_proven_count: number;
  unverified_count: number;
  not_found_count: number;
  provider_metadata: {
    provider_name: string;
    model_name: string;
    ai_mode: AIMode;
    is_fallback: boolean;
    tokens_prompt?: number;
    tokens_completion?: number;
    latency_ms?: number;
  };
  fit_score: FitScoreBreakdown;
}

export interface CandidateMatrixCell {
  requirement_id: string;
  requirement_name: string;
  status: EvidenceStatus;
  confidence: number;
  source_type: string;
  verbatim_quote?: string;
  is_human_overridden: boolean;
}

export interface CandidateMatrixRow {
  candidate_id: string;
  full_name: string;
  anonymous_alias: string;
  years_experience: number;
  quarantined: boolean;
  quarantine_reason?: string;
  overall_score?: number | null;
  cells: Record<string, CandidateMatrixCell>;
}

export interface CandidateComparisonMatrixResponse {
  role_id: string;
  role_title: string;
  requirements: Requirement[];
  candidates: CandidateMatrixRow[];
}

export interface AuditEvent {
  id: string;
  entity_type: string;
  entity_id: string;
  actor: 'RECRUITER' | 'SYSTEM_AGENT';
  action: string;
  details: Record<string, any>;
  created_at: string;
}

