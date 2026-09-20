import React, { useState } from 'react';
import {
  Upload,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  FileX,
  ArrowRight,
  ShieldAlert,
  FileText
} from 'lucide-react';
import { CandidateMatrixRow, Requirement, EvidenceStatus } from '../types';

interface CandidateMatrixProps {
  candidates: CandidateMatrixRow[];
  requirements: Requirement[];
  selectedCandidateId: string | null;
  onSelectCandidate: (candidateId: string, requirementId?: string) => void;
  blindMode: boolean;
  onUploadCandidate: (file: File, nameHint?: string) => Promise<void>;
  isUploading: boolean;
  uploadError: string | null;
}

export const CandidateMatrix: React.FC<CandidateMatrixProps> = ({
  candidates,
  requirements,
  selectedCandidateId,
  onSelectCandidate,
  blindMode,
  onUploadCandidate,
  isUploading,
  uploadError,
}) => {
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [nameHint, setNameHint] = useState('');

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    await onUploadCandidate(file, nameHint);
    setFile(null);
    setNameHint('');
    setShowUploadModal(false);
  };

  const renderStatusBadge = (status: EvidenceStatus, isOverridden: boolean) => {
    switch (status) {
      case 'PROVEN':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              border: '1px solid rgba(16, 185, 129, 0.35)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
            }}
          >
            <CheckCircle2 size={12} color="#10b981" />
            PROVEN
            {isOverridden && <span style={{ fontSize: '9px', color: '#6ee7b7' }}>(OVR)</span>}
          </span>
        );
      case 'PARTIALLY_PROVEN':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: 'rgba(245, 158, 11, 0.15)',
              color: '#fbbf24',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
            }}
          >
            <AlertTriangle size={12} color="#f59e0b" />
            PARTIAL
            {isOverridden && <span style={{ fontSize: '9px', color: '#fde68a' }}>(OVR)</span>}
          </span>
        );
      case 'UNVERIFIED':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: 'rgba(99, 102, 241, 0.15)',
              color: '#818cf8',
              border: '1px solid rgba(99, 102, 241, 0.35)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
            }}
          >
            <HelpCircle size={12} color="#818cf8" />
            UNVERIFIED
          </span>
        );
      case 'CONTRADICTED':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.45)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
            }}
          >
            <XCircle size={12} color="#ef4444" />
            CONTRADICTED
          </span>
        );
      case 'NOT_FOUND_IN_PROVIDED_MATERIAL':
      default:
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: 'rgba(100, 116, 139, 0.15)',
              color: '#94a3b8',
              border: '1px solid rgba(100, 116, 139, 0.25)',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <FileX size={12} color="#64748b" />
            NOT FOUND
          </span>
        );
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
      {/* Top Action Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: '#ffffff' }}>
            Candidate Comparison Matrix
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#94a3b8' }}>
            Evaluate and compare verified evidence claims across all role criteria. Click any cell to inspect source citations.
          </p>
        </div>

        <button
          onClick={() => setShowUploadModal(true)}
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
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(37, 99, 235, 0.3)',
          }}
        >
          <Upload size={16} />
          <span>Ingest New Candidate</span>
        </button>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '10px',
              border: '1px solid #1e293b',
              padding: '24px',
              width: '100%',
              maxWidth: '520px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#ffffff' }}>
                Ingest Candidate Resume
              </h3>
              <button
                onClick={() => setShowUploadModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#94a3b8' }}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleFormSubmit}>
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>
                  Candidate Name (Optional Hint)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Alex Rivera"
                  value={nameHint}
                  onChange={(e) => setNameHint(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #334155',
                    backgroundColor: '#0b1020',
                    color: '#f8fafc',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>
                  Resume Document (.pdf, .docx, .txt) *
                </label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #334155',
                    backgroundColor: '#0b1020',
                    color: '#cbd5e1',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
                <p style={{ margin: '6px 0 0 0', fontSize: '11px', color: '#94a3b8', lineHeight: '1.4' }}>
                  Documents pass automated security quarantine scanning and PII sanitization before processing.
                </p>
              </div>

              {uploadError && (
                <div
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#f87171',
                    padding: '10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    marginBottom: '14px',
                  }}
                >
                  {uploadError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: '1px solid #334155',
                    backgroundColor: '#1e293b',
                    color: '#94a3b8',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!file || isUploading}
                  style={{
                    padding: '8px 20px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: '#2563eb',
                    color: '#ffffff',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: (!file || isUploading) ? 'not-allowed' : 'pointer',
                    boxShadow: '0 2px 6px rgba(37, 99, 235, 0.4)',
                  }}
                >
                  {isUploading ? 'Ingesting & Scanning...' : 'Start Ingestion'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Comparison Grid */}
      {candidates.length === 0 ? (
        <div
          style={{
            backgroundColor: '#0f172a',
            borderRadius: '8px',
            border: '1px solid #1e293b',
            padding: '48px 24px',
            textAlign: 'center',
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
          }}
        >
          <FileText size={40} color="#64748b" style={{ marginBottom: '12px' }} />
          <h3 style={{ margin: '0 0 6px 0', fontSize: '16px', fontWeight: 700, color: '#ffffff' }}>
            No Candidates Ingested Yet
          </h3>
          <p style={{ margin: '0 0 20px 0', fontSize: '13px', color: '#94a3b8' }}>
            Upload a candidate resume to begin automated evidence matching and competency comparison.
          </p>
          <button
            onClick={() => setShowUploadModal(true)}
            style={{
              backgroundColor: '#2563eb',
              color: '#ffffff',
              border: 'none',
              padding: '8px 18px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Upload Resume
          </button>
        </div>
      ) : (
        <div
          style={{
            backgroundColor: '#0f172a',
            borderRadius: '8px',
            border: '1px solid #1e293b',
            overflowX: 'auto',
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '980px' }}>
            <thead>
              <tr style={{ backgroundColor: '#0c1222', borderBottom: '1px solid #1e293b' }}>
                <th style={{ padding: '14px 18px', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Candidate
                </th>
                <th style={{ padding: '14px 18px', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Deterministic Fit
                </th>
                <th style={{ padding: '14px 18px', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Experience
                </th>
                {requirements.map((req) => (
                  <th
                    key={req.id}
                    style={{
                      padding: '14px 18px',
                      fontSize: '12px',
                      fontWeight: 700,
                      color: '#94a3b8',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}
                  >
                    <div>{req.name}</div>
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
                  </th>
                ))}
                <th style={{ padding: '14px 18px', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => {
                const isSelected = selectedCandidateId === c.candidate_id;
                const displayName = blindMode ? c.anonymous_alias : c.full_name;

                return (
                  <tr
                    key={c.candidate_id}
                    style={{
                      borderBottom: '1px solid #1e293b',
                      backgroundColor: isSelected ? '#172554' : c.quarantined ? 'rgba(239, 68, 68, 0.08)' : 'transparent',
                      transition: 'background-color 0.15s ease',
                    }}
                  >
                    {/* Candidate Name / Blind Alias */}
                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {c.quarantined ? (
                          <span title="Quarantined document">
                            <ShieldAlert size={16} color="#ef4444" />
                          </span>
                        ) : (
                          <div
                            style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '50%',
                              backgroundColor: isSelected ? '#2563eb' : '#1e293b',
                              border: '1px solid #334155',
                              color: isSelected ? '#ffffff' : '#38bdf8',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '11px',
                              fontWeight: 700,
                            }}
                          >
                            {displayName.slice(0, 2).toUpperCase()}
                          </div>
                        )}
                        <div>
                          <strong style={{ fontSize: '13px', color: '#f8fafc' }}>{displayName}</strong>
                          {blindMode && (
                            <span style={{ fontSize: '10px', color: '#34d399', display: 'block' }}>
                              Blind Shield Active
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Deterministic Fit Score */}
                    <td style={{ padding: '14px 18px' }}>
                      {c.quarantined ? (
                        <span
                          style={{
                            backgroundColor: 'rgba(239, 68, 68, 0.2)',
                            color: '#f87171',
                            border: '1px solid rgba(239, 68, 68, 0.4)',
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                          }}
                        >
                          EXCLUDED
                        </span>
                      ) : c.overall_score !== null && c.overall_score !== undefined ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span
                            style={{
                              fontSize: '14px',
                              fontWeight: 800,
                              color: c.overall_score >= 75 ? '#34d399' : c.overall_score >= 50 ? '#fbbf24' : '#f87171',
                            }}
                          >
                            {c.overall_score.toFixed(1)}%
                          </span>
                        </div>
                      ) : (
                        <span style={{ fontSize: '11px', color: '#64748b' }}>Pending match</span>
                      )}
                    </td>

                    {/* Experience */}
                    <td style={{ padding: '14px 18px', fontSize: '13px', color: '#cbd5e1' }}>
                      <strong style={{ color: '#f8fafc' }}>{c.years_experience}</strong> yrs
                    </td>

                    {/* Requirement Cells (Interactive) */}
                    {requirements.map((req) => {
                      const cell = c.cells[req.id];
                      const status = cell?.status || 'NOT_FOUND_IN_PROVIDED_MATERIAL';
                      const isOverridden = cell?.is_human_overridden || false;

                      return (
                        <td
                          key={req.id}
                          onClick={() => onSelectCandidate(c.candidate_id, req.id)}
                          style={{
                            padding: '14px 18px',
                            cursor: 'pointer',
                          }}
                          title="Click to view evidence citation in Dual-Pane Studio"
                        >
                          {renderStatusBadge(status, isOverridden)}
                        </td>
                      );
                    })}

                    {/* Actions */}
                    <td style={{ padding: '14px 18px' }}>
                      <button
                        onClick={() => onSelectCandidate(c.candidate_id)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '6px 12px',
                          borderRadius: '5px',
                          backgroundColor: isSelected ? '#2563eb' : '#1e293b',
                          color: isSelected ? '#ffffff' : '#cbd5e1',
                          border: `1px solid ${isSelected ? '#3b82f6' : '#334155'}`,
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        <span>Evidence</span>
                        <ArrowRight size={12} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
