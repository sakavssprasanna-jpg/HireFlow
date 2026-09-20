import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Lock,
  UserCheck,
  Bot,
  FileSearch,
  EyeOff,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Clock,
  CheckCircle2
} from 'lucide-react';
import { AuditEvent, Candidate } from '../types';

interface AuditSecurityStudioProps {
  candidate: Candidate | null;
  auditEvents: AuditEvent[];
  isLoadingEvents: boolean;
  onRefreshAudit: () => Promise<void>;
  blindMode: boolean;
}

export const AuditSecurityStudio: React.FC<AuditSecurityStudioProps> = ({
  candidate,
  auditEvents,
  isLoadingEvents,
  onRefreshAudit,
  blindMode,
}) => {
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const toggleEvent = (id: string) => {
    setExpandedEventId(expandedEventId === id ? null : id);
  };

  const getActorBadge = (actor: string) => {
    if (actor === 'RECRUITER') {
      return {
        bg: 'rgba(56, 189, 248, 0.15)',
        border: 'rgba(56, 189, 248, 0.35)',
        text: '#38bdf8',
        icon: <UserCheck size={12} color="#38bdf8" />,
        label: 'HUMAN RECRUITER'
      };
    }
    return {
      bg: 'rgba(168, 85, 247, 0.15)',
      border: 'rgba(168, 85, 247, 0.35)',
      text: '#c084fc',
      icon: <Bot size={12} color="#c084fc" />,
      label: 'SYSTEM AGENT'
    };
  };

  const formatAction = (action: string) => {
    return action
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner: Enterprise Audit & Compliance Overview */}
      <div style={{
        backgroundColor: '#0f172a',
        color: '#ffffff',
        borderRadius: '10px',
        border: '1px solid #1e293b',
        padding: '18px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '8px',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <ShieldCheck size={24} color="#38bdf8" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 700 }}>
                Audit Trail &amp; Security Center
              </h2>
              <span style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '10px',
                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                color: '#38bdf8',
                fontWeight: 600,
                border: '1px solid rgba(56, 189, 248, 0.3)'
              }}>
                SOC2 / GDPR Audit-Ready
              </span>
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#94a3b8' }}>
              Immutable event log tracking all AI extractions, prompt security evaluations, and human recruiter overrides.
            </p>
          </div>
        </div>

        <button
          onClick={onRefreshAudit}
          disabled={isLoadingEvents}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            borderRadius: '6px',
            backgroundColor: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid #334155',
            fontSize: '12px',
            fontWeight: 600,
            cursor: isLoadingEvents ? 'not-allowed' : 'pointer'
          }}
        >
          <RefreshCw size={13} className={isLoadingEvents ? 'animate-spin' : ''} />
          {isLoadingEvents ? 'Refreshing...' : 'Refresh Audit'}
        </button>
      </div>

      {/* Two-Column Layout: Chronological Audit Trail (Left) + Security & Trust Cards (Right) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 0.8fr',
        gap: '20px',
        alignItems: 'start'
      }}>
        {/* LEFT COLUMN: Chronological Audit Trail Timeline */}
        <div style={{
          backgroundColor: '#0f172a',
          borderRadius: '10px',
          border: '1px solid #1e293b',
          padding: '20px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={18} color="#38bdf8" />
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#ffffff' }}>
                Chronological Event Ledger ({auditEvents.length})
              </h3>
            </div>
            {candidate && (
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                Candidate: <strong style={{ color: '#f8fafc' }}>{blindMode ? candidate.anonymous_alias : candidate.full_name}</strong>
              </span>
            )}
          </div>

          {!candidate ? (
            <div style={{
              padding: '40px 16px',
              textAlign: 'center',
              backgroundColor: '#0b1020',
              borderRadius: '8px',
              border: '1px dashed #334155',
              color: '#64748b',
              fontSize: '13px'
            }}>
              Select or ingest a candidate to view their complete immutable audit trail.
            </div>
          ) : auditEvents.length === 0 ? (
            <div style={{
              padding: '40px 16px',
              textAlign: 'center',
              backgroundColor: '#0b1020',
              borderRadius: '8px',
              border: '1px dashed #334155',
              color: '#64748b',
              fontSize: '13px'
            }}>
              No audit events recorded for this candidate yet.
            </div>
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              maxHeight: '680px',
              overflowY: 'auto',
              paddingRight: '4px'
            }}>
              {auditEvents.map((evt) => {
                const badge = getActorBadge(evt.actor);
                const isExpanded = expandedEventId === evt.id;

                return (
                  <div
                    key={evt.id}
                    style={{
                      border: '1px solid #1e293b',
                      borderRadius: '8px',
                      backgroundColor: '#131d35',
                      overflow: 'hidden',
                      transition: 'border-color 0.15s ease'
                    }}
                  >
                    {/* Header Row */}
                    <div
                      onClick={() => toggleEvent(evt.id)}
                      style={{
                        padding: '12px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        backgroundColor: isExpanded ? '#172554' : '#131d35',
                        borderBottom: isExpanded ? '1px solid #1e293b' : 'none'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        {isExpanded ? <ChevronDown size={15} color="#94a3b8" /> : <ChevronRight size={15} color="#64748b" />}
                        <span style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          backgroundColor: badge.bg,
                          border: `1px solid ${badge.border}`,
                          color: badge.text,
                          fontWeight: 700
                        }}>
                          {badge.icon} {badge.label}
                        </span>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                          {formatAction(evt.action)}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>
                          {new Date(evt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                      </div>
                    </div>

                    {/* Expandable JSON Details */}
                    {isExpanded && (
                      <div style={{
                        padding: '12px 14px',
                        backgroundColor: '#070b14',
                        color: '#cbd5e1',
                        fontFamily: 'Consolas, Monaco, monospace',
                        fontSize: '11px',
                        lineHeight: '1.45',
                        overflowX: 'auto',
                        borderTop: '1px solid #1e293b'
                      }}>
                        <div style={{ color: '#64748b', marginBottom: '6px', fontSize: '10px', textTransform: 'uppercase' }}>
                          Event ID: {evt.id} | Entity: {evt.entity_type} ({evt.entity_id}) | Timestamp: {evt.created_at}
                        </div>
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                          {JSON.stringify(evt.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Security & Trust Center */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Card 1: Prompt Injection Defense */}
          <div style={{
            backgroundColor: '#0f172a',
            borderRadius: '10px',
            border: '1px solid #1e293b',
            padding: '18px 20px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldAlert size={18} color="#f87171" />
              <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#ffffff' }}>
                Prompt Injection Defense &amp; Quarantine
              </h4>
            </div>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', lineHeight: '1.45' }}>
              Every uploaded resume and interview note is scanned by the multi-pattern <code style={{ backgroundColor: '#0b1020', border: '1px solid #334155', color: '#38bdf8', padding: '1px 4px', borderRadius: '3px' }}>SecurityScanner</code> before parsing.
            </p>

            <div style={{
              backgroundColor: candidate?.quarantined ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.12)',
              border: `1px solid ${candidate?.quarantined ? 'rgba(239, 68, 68, 0.35)' : 'rgba(16, 185, 129, 0.3)'}`,
              borderRadius: '6px',
              padding: '10px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}>
              {candidate?.quarantined ? (
                <>
                  <ShieldAlert size={20} color="#f87171" />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 700, color: '#f87171' }}>
                      CANDIDATE DOCUMENT QUARANTINED
                    </div>
                    <div style={{ fontSize: '11px', color: '#fca5a5' }}>
                      Reason: {candidate.quarantine_reason || 'Adversarial instruction detected.'}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <ShieldCheck size={20} color="#10b981" />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 700, color: '#34d399' }}>
                      SECURITY VERIFICATION ACTIVE
                    </div>
                    <div style={{ fontSize: '11px', color: '#6ee7b7' }}>
                      No jailbreak patterns, system prompt overrides, or canary leaks detected.
                    </div>
                  </div>
                </>
              )}
            </div>

            <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Lock size={12} color="#38bdf8" />
              <span><strong style={{ color: '#f8fafc' }}>0-LLM Guarantee:</strong> Quarantined files are permanently isolated from AI prompts.</span>
            </div>
          </div>

          {/* Card 2: PII Masking & Blind Screening */}
          <div style={{
            backgroundColor: '#0f172a',
            borderRadius: '10px',
            border: '1px solid #1e293b',
            padding: '18px 20px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <EyeOff size={18} color="#c084fc" />
              <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#ffffff' }}>
                PII Anonymization &amp; Blind Screening
              </h4>
            </div>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', lineHeight: '1.45' }}>
              Protects against unconscious recruiter bias by stripping candidate full names, emails, phone numbers, and addresses prior to presentation.
            </p>

            <div style={{
              backgroundColor: '#0b1020',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                <span style={{ color: '#64748b' }}>Active Blind State:</span>
                <strong style={{ color: blindMode ? '#c084fc' : '#94a3b8' }}>
                  {blindMode ? 'ENABLED (Anonymous Alias)' : 'OFF (Identifiable Info Visible)'}
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                <span style={{ color: '#64748b' }}>Deterministic Alias:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#f8fafc' }}>
                  {candidate?.anonymous_alias || 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* Card 3: Deterministic Quote Verifier */}
          <div style={{
            backgroundColor: '#0f172a',
            borderRadius: '10px',
            border: '1px solid #1e293b',
            padding: '18px 20px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileSearch size={18} color="#38bdf8" />
              <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#ffffff' }}>
                Deterministic Quote Verifier
              </h4>
            </div>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', lineHeight: '1.45' }}>
              Every claim citation produced by the LLM is verified by Python substring and byte-offset math against the original raw parsed document.
            </p>

            <div style={{
              backgroundColor: 'rgba(56, 189, 248, 0.12)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '6px',
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={13} color="#38bdf8" /> Hallucination-Proof Validation
              </div>
              <div style={{ fontSize: '11px', color: '#e0f2fe', lineHeight: '1.4' }}>
                If an LLM hallucinates a quote not present in the document text, the claim is rejected or flagged as unverified automatically.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
