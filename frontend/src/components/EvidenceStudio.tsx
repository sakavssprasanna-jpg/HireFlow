import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  FileX,
  FileText,
  Sparkles,
  SlidersHorizontal,
  ArrowRight,
  ShieldCheck,
  AlertCircle
} from 'lucide-react';
import {
  EvidenceClaim,
  Requirement,
  EvidenceStatus,
  Candidate,
  CandidateGapsResponse,
  FitScoreBreakdown
} from '../types';

interface EvidenceStudioProps {
  candidate: Candidate | null;
  fitScore?: FitScoreBreakdown | null;
  requirements: Requirement[];
  evidenceClaims: EvidenceClaim[];
  candidateGaps: CandidateGapsResponse | null;
  selectedRequirementId?: string | null;
  onSelectRequirement?: (reqId: string) => void;
  onOpenOverrideModal: (claim: EvidenceClaim, requirementName: string) => void;
  onRunAIMatching: () => Promise<void>;
  onGenerateQuestions: () => Promise<void>;
  isAnalyzing: boolean;
  isGeneratingQuestions: boolean;
  rawDocumentText?: string;
  documentFilename?: string;
  documentHash?: string;
  blindMode: boolean;
}

export const EvidenceStudio: React.FC<EvidenceStudioProps> = ({
  candidate,
  fitScore,
  requirements,
  evidenceClaims,
  candidateGaps,
  selectedRequirementId,
  onSelectRequirement,
  onOpenOverrideModal,
  onRunAIMatching,
  onGenerateQuestions,
  isAnalyzing,
  isGeneratingQuestions,
  rawDocumentText,
  documentFilename,
  documentHash,
  blindMode,
}) => {
  const [activeReqId, setActiveReqId] = useState<string>(
    selectedRequirementId || (requirements.length > 0 ? requirements[0].id : '')
  );

  const activeRequirement = requirements.find((r) => r.id === activeReqId);
  const activeClaim = evidenceClaims.find((c) => c.requirement_id === activeReqId);

  const handleSelectReq = (reqId: string) => {
    setActiveReqId(reqId);
    if (onSelectRequirement) onSelectRequirement(reqId);
  };

  const getStatusBadge = (status?: EvidenceStatus) => {
    switch (status) {
      case 'PROVEN':
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.35)',
          text: '#34d399',
          icon: <CheckCircle2 size={13} color="#10b981" />,
          label: 'PROVEN',
        };
      case 'PARTIALLY_PROVEN':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          border: 'rgba(245, 158, 11, 0.35)',
          text: '#fbbf24',
          icon: <AlertTriangle size={13} color="#f59e0b" />,
          label: 'PARTIALLY PROVEN',
        };
      case 'UNVERIFIED':
        return {
          bg: 'rgba(99, 102, 241, 0.15)',
          border: 'rgba(99, 102, 241, 0.35)',
          text: '#818cf8',
          icon: <HelpCircle size={13} color="#818cf8" />,
          label: 'UNVERIFIED',
        };
      case 'CONTRADICTED':
        return {
          bg: 'rgba(239, 68, 68, 0.2)',
          border: 'rgba(239, 68, 68, 0.45)',
          text: '#f87171',
          icon: <XCircle size={13} color="#ef4444" />,
          label: 'CONTRADICTED',
        };
      case 'NOT_FOUND_IN_PROVIDED_MATERIAL':
      default:
        return {
          bg: 'rgba(100, 116, 139, 0.15)',
          border: 'rgba(100, 116, 139, 0.25)',
          text: '#94a3b8',
          icon: <FileX size={13} color="#64748b" />,
          label: 'NOT FOUND',
        };
    }
  };

  const candidateDisplayName = candidate
    ? blindMode
      ? candidate.anonymous_alias
      : candidate.full_name
    : 'No Candidate Selected';

  return (
    <div style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
      {/* Candidate Banner & Fit Summary */}
      <div
        style={{
          backgroundColor: '#0f172a',
          borderRadius: '8px',
          border: '1px solid #1e293b',
          padding: '20px 24px',
          marginBottom: '20px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              backgroundColor: '#2563eb',
              border: '1px solid #3b82f6',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '16px',
              fontWeight: 800,
            }}
          >
            {candidateDisplayName.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#ffffff' }}>
                {candidateDisplayName}
              </h2>
              {blindMode && (
                <span
                  style={{
                    backgroundColor: 'rgba(16, 185, 129, 0.15)',
                    color: '#34d399',
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '2px 7px',
                    borderRadius: '4px',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    letterSpacing: '0.5px',
                  }}
                >
                  BLIND MASKED
                </span>
              )}
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
              Experience: <strong style={{ color: '#f8fafc' }}>{candidate?.years_experience || 0} yrs</strong> · Claims Verified: <strong style={{ color: '#f8fafc' }}>{evidenceClaims.length}</strong> · Active Gaps: <strong style={{ color: '#f8fafc' }}>{candidateGaps?.total_gaps || 0}</strong>
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {fitScore ? (
            <div
              style={{
                backgroundColor: '#070b14',
                border: '1px solid #1e293b',
                padding: '8px 18px',
                borderRadius: '6px',
                textAlign: 'right',
              }}
            >
              <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                DETERMINISTIC FIT
              </div>
              <div
                style={{
                  fontSize: '22px',
                  fontWeight: 900,
                  color: fitScore.overall_score >= 75 ? '#34d399' : fitScore.overall_score >= 50 ? '#fbbf24' : '#f87171',
                }}
              >
                {fitScore.overall_score.toFixed(1)}%
              </div>
            </div>
          ) : (
            <button
              onClick={onRunAIMatching}
              disabled={isAnalyzing || !candidate}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                border: '1px solid #3b82f6',
                padding: '10px 18px',
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: (isAnalyzing || !candidate) ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.3)',
              }}
            >
              <Sparkles size={16} />
              <span>{isAnalyzing ? 'Matching Evidence...' : 'Run AI Evidence Matching'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Dual-Pane Workstation Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '46% 54%', gap: '20px' }}>
        {/* LEFT PANE: Requirements & Evidence Claims */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '8px',
              border: '1px solid #1e293b',
              padding: '18px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#ffffff' }}>
                Role Criteria &amp; Evidence Claims
              </h3>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                Select to inspect citation
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {requirements.map((req) => {
                const claim = evidenceClaims.find((c) => c.requirement_id === req.id);
                const isSelected = activeReqId === req.id;
                const badge = getStatusBadge(claim?.status);

                return (
                  <div
                    key={req.id}
                    onClick={() => handleSelectReq(req.id)}
                    style={{
                      padding: '12px 14px',
                      borderRadius: '6px',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid #1e293b',
                      backgroundColor: isSelected ? '#172554' : '#131d35',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 0 10px rgba(56, 189, 248, 0.15)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <strong style={{ fontSize: '13px', color: '#f8fafc' }}>{req.name}</strong>
                          <span
                            style={{
                              fontSize: '9px',
                              fontWeight: 700,
                              padding: '1px 5px',
                              borderRadius: '3px',
                              backgroundColor: req.category === 'MUST_HAVE' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                              color: req.category === 'MUST_HAVE' ? '#f87171' : '#fbbf24',
                              border: `1px solid ${req.category === 'MUST_HAVE' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                            }}
                          >
                            {req.category === 'MUST_HAVE' ? 'MUST' : 'NICE'}
                          </span>
                        </div>

                        {claim?.verbatim_quote ? (
                          <p
                            style={{
                              margin: '5px 0 0 0',
                              fontSize: '11px',
                              color: '#cbd5e1',
                              fontStyle: 'italic',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              lineHeight: '1.4',
                            }}
                          >
                            &quot;{claim.verbatim_quote}&quot;
                          </p>
                        ) : (
                          <p style={{ margin: '5px 0 0 0', fontSize: '11px', color: '#64748b' }}>
                            No evidence citation located in candidate material.
                          </p>
                        )}
                      </div>

                      <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '12px' }}>
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            backgroundColor: badge.bg,
                            color: badge.text,
                            border: `1px solid ${badge.border}`,
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            fontWeight: 700,
                          }}
                        >
                          {badge.icon}
                          {badge.label}
                        </span>

                        {claim?.is_human_overridden && (
                          <div style={{ fontSize: '9px', fontWeight: 700, color: '#38bdf8', marginTop: '3px' }}>
                            RECRUITER OVR
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Quick Override Button when selected */}
                    {isSelected && claim && (
                      <div
                        style={{
                          marginTop: '10px',
                          paddingTop: '8px',
                          borderTop: '1px dashed #334155',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                          Source: <strong style={{ color: '#f8fafc' }}>{claim.source_type}</strong> · Confidence: <strong style={{ color: '#f8fafc' }}>{Math.round(claim.confidence * 100)}%</strong>
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenOverrideModal(claim, req.name);
                          }}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            color: '#cbd5e1',
                            padding: '4px 10px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          <SlidersHorizontal size={11} />
                          <span>Recruiter Override</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Competency Gap Cockpit */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '8px',
              border: '1px solid #1e293b',
              padding: '18px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={16} color="#f87171" />
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#ffffff' }}>
                  Competency Gaps ({candidateGaps?.total_gaps || 0})
                </h3>
              </div>

              {candidateGaps && candidateGaps.total_gaps > 0 && (
                <button
                  onClick={onGenerateQuestions}
                  disabled={isGeneratingQuestions}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    color: '#38bdf8',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: isGeneratingQuestions ? 'not-allowed' : 'pointer',
                  }}
                >
                  <span>{isGeneratingQuestions ? 'Generating...' : 'Generate Targeted Questions'}</span>
                  <ArrowRight size={12} />
                </button>
              )}
            </div>

            {(!candidateGaps || candidateGaps.gaps.length === 0) ? (
              <div style={{ padding: '16px', textAlign: 'center', color: '#34d399', fontSize: '12px', backgroundColor: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '6px' }}>
                ✓ No competency gaps detected in verified evidence.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {candidateGaps.gaps.map((gap, idx) => (
                  <div
                    key={idx}
                    style={{
                      borderLeft: `3px solid ${gap.priority === 'CRITICAL' ? '#ef4444' : gap.priority === 'HIGH' ? '#f59e0b' : '#3b82f6'}`,
                      backgroundColor: '#131d35',
                      padding: '10px 14px',
                      borderRadius: '0 6px 6px 0',
                      borderTop: '1px solid #1e293b',
                      borderRight: '1px solid #1e293b',
                      borderBottom: '1px solid #1e293b',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '13px', color: '#f8fafc' }}>{gap.requirement_name}</strong>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          color: gap.priority === 'CRITICAL' ? '#f87171' : gap.priority === 'HIGH' ? '#fbbf24' : '#60a5fa',
                          backgroundColor: gap.priority === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : gap.priority === 'HIGH' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                          padding: '1px 6px',
                          borderRadius: '3px',
                          border: `1px solid ${gap.priority === 'CRITICAL' ? 'rgba(239, 68, 68, 0.4)' : gap.priority === 'HIGH' ? 'rgba(245, 158, 11, 0.4)' : 'rgba(59, 130, 246, 0.4)'}`,
                        }}
                      >
                        {gap.priority} GAP
                      </span>
                    </div>
                    <p style={{ margin: '4px 0 0 0', fontSize: '11px', color: '#94a3b8' }}>
                      {gap.reason}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT PANE: Source Document Inspector */}
        <div
          style={{
            backgroundColor: '#0f172a',
            borderRadius: '8px',
            border: '1px solid #1e293b',
            padding: '20px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '820px',
          }}
        >
          {/* Document Header & Provenance */}
          <div style={{ borderBottom: '1px solid #1e293b', paddingBottom: '14px', marginBottom: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={16} color="#38bdf8" />
                <strong style={{ fontSize: '14px', color: '#ffffff' }}>
                  {documentFilename || 'candidate_resume.txt'}
                </strong>
                {documentHash && (
                  <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'monospace' }}>
                    SHA: {documentHash.slice(0, 10)}...
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ShieldCheck size={14} color="#10b981" />
                <span style={{ fontSize: '11px', color: '#34d399', fontWeight: 600 }}>
                  PII Sanitized &amp; Verified
                </span>
              </div>
            </div>

            {/* Provenance Status Banner */}
            {activeClaim?.verbatim_quote ? (
              <div
                style={{
                  backgroundColor: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <CheckCircle2 size={16} color="#10b981" style={{ flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#34d399' }}>
                    VERIFIED SOURCE CITATION
                  </div>
                  <div style={{ fontSize: '11px', color: '#6ee7b7' }}>
                    Exact excerpt located in candidate document. Offsets: [{activeClaim.start_offset ?? 'N/A'} - {activeClaim.end_offset ?? 'N/A'}] · Page information unavailable
                  </div>
                </div>
              </div>
            ) : (
              <div
                style={{
                  backgroundColor: 'rgba(100, 116, 139, 0.12)',
                  border: '1px solid rgba(100, 116, 139, 0.25)',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <FileX size={16} color="#64748b" style={{ flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1' }}>
                    NOT FOUND IN PROVIDED MATERIAL
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                    This does not establish that the candidate lacks the skill; it indicates no direct citation was discovered.
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Active Highlighted Excerpt Callout */}
          {activeClaim?.verbatim_quote && (
            <div
              style={{
                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                borderRadius: '6px',
                padding: '12px 14px',
                marginBottom: '14px',
                boxShadow: '0 0 10px rgba(56, 189, 248, 0.1)',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8', marginBottom: '4px' }}>
                Active Citation for &quot;{activeRequirement?.name}&quot;:
              </div>
              <p style={{ margin: 0, fontSize: '12px', color: '#e0f2fe', fontStyle: 'italic', lineHeight: '1.5' }}>
                &quot;{activeClaim.verbatim_quote}&quot;
              </p>
            </div>
          )}

          {/* Raw Text Viewer */}
          <div
            style={{
              flex: 1,
              backgroundColor: '#070b14',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '14px',
              overflowY: 'auto',
              fontSize: '12px',
              fontFamily: 'monospace',
              lineHeight: '1.6',
              color: '#cbd5e1',
              whiteSpace: 'pre-wrap',
            }}
          >
            {rawDocumentText || 'Source document text will appear here after candidate ingestion.'}
          </div>
        </div>
      </div>
    </div>
  );
};
