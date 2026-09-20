import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle } from 'lucide-react';
import { EvidenceStatus } from '../types';

interface RecruiterOverrideModalProps {
  isOpen: boolean;
  requirementName: string;
  currentStatus: EvidenceStatus;
  onConfirm: (newStatus: EvidenceStatus, justification: string) => Promise<void>;
  onClose: () => void;
  isSubmitting: boolean;
  error?: string | null;
}

export const RecruiterOverrideModal: React.FC<RecruiterOverrideModalProps> = ({
  isOpen,
  requirementName,
  currentStatus,
  onConfirm,
  onClose,
  isSubmitting,
  error,
}) => {
  const [newStatus, setNewStatus] = useState<EvidenceStatus>('PROVEN');
  const [justification, setJustification] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (justification.trim().length < 5) return;
    await onConfirm(newStatus, justification.trim());
  };

  const isJustificationValid = justification.trim().length >= 5;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
      }}
    >
      <div
        style={{
          backgroundColor: '#0f172a',
          borderRadius: '10px',
          padding: '28px',
          width: '100%',
          maxWidth: '560px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
          border: '1px solid #1e293b',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
          <ShieldAlert size={22} color="#38bdf8" />
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#ffffff' }}>
            Recruiter Evidence Override
          </h3>
        </div>

        <p style={{ margin: '0 0 16px 0', fontSize: '13px', color: '#94a3b8', lineHeight: '1.5' }}>
          Human recruiter decisions supersede all automated AI proposals. Overriding updates candidate evidence, triggers instant mathematical score recalculation, and records an immutable entry in the audit trail.
        </p>

        {/* Current State Banner */}
        <div
          style={{
            backgroundColor: '#0b1020',
            border: '1px solid #1e293b',
            borderRadius: '6px',
            padding: '12px 16px',
            marginBottom: '18px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Target Criterion
            </div>
            <strong style={{ fontSize: '14px', color: '#f8fafc' }}>{requirementName}</strong>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Current Status
            </div>
            <span
              style={{
                display: 'inline-block',
                marginTop: '2px',
                fontSize: '11px',
                fontWeight: 700,
                color: '#cbd5e1',
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                padding: '2px 8px',
                borderRadius: '4px',
              }}
            >
              {currentStatus}
            </span>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* New Status */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#cbd5e1', marginBottom: '6px' }}>
              New Reconciled Status *
            </label>
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value as EvidenceStatus)}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid #334155',
                fontSize: '13px',
                fontWeight: 600,
                color: '#f8fafc',
                backgroundColor: '#0b1020',
                boxSizing: 'border-box',
              }}
            >
              <option value="PROVEN">PROVEN (+1.0 point credit)</option>
              <option value="PARTIALLY_PROVEN">PARTIALLY_PROVEN (+0.5 point credit)</option>
              <option value="UNVERIFIED">UNVERIFIED (0.0 point credit)</option>
              <option value="CONTRADICTED">CONTRADICTED (-0.5 point penalty)</option>
              <option value="NOT_FOUND_IN_PROVIDED_MATERIAL">NOT_FOUND_IN_PROVIDED_MATERIAL (0.0 point credit)</option>
            </select>
          </div>

          {/* Mandatory Justification */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <label style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1' }}>
                Mandatory Written Justification *
              </label>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: isJustificationValid ? '#34d399' : '#fbbf24',
                }}
              >
                {justification.trim().length}/5 min chars
              </span>
            </div>
            <textarea
              required
              rows={3}
              placeholder="e.g. Verified hands-on production cluster administration during round 2 deep dive scenario."
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                border: isJustificationValid ? '1px solid #10b981' : '1px solid #334155',
                backgroundColor: '#0b1020',
                color: '#f8fafc',
                fontSize: '13px',
                lineHeight: '1.4',
                boxSizing: 'border-box',
                outline: 'none',
              }}
            />
          </div>

          {/* Audit Warning */}
          <div
            style={{
              backgroundColor: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: '6px',
              padding: '10px 14px',
              fontSize: '11px',
              color: '#fbbf24',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '20px',
            }}
          >
            <AlertTriangle size={15} color="#f59e0b" style={{ flexShrink: 0 }} />
            <span>
              <strong style={{ color: '#fef3c7' }}>Compliance Notice:</strong> This action will be permanently recorded in the immutable audit trail with your recruiter credentials and timestamp.
            </span>
          </div>

          {error && (
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
              {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: '1px solid #334155',
                backgroundColor: '#1e293b',
                color: '#94a3b8',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isJustificationValid || isSubmitting}
              style={{
                padding: '8px 20px',
                borderRadius: '6px',
                border: '1px solid #3b82f6',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 600,
                cursor: (!isJustificationValid || isSubmitting) ? 'not-allowed' : 'pointer',
                opacity: (!isJustificationValid || isSubmitting) ? 0.6 : 1,
                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.4)',
              }}
            >
              {isSubmitting ? 'Recording Decision...' : 'Confirm Recruiter Override'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
