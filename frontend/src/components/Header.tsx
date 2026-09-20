import React from 'react';
import { Eye, EyeOff, Brain, Plus } from 'lucide-react';
import { HealthStatus, Role, AIMode } from '../types';

interface HeaderProps {
  health: HealthStatus | null;
  roles: Role[];
  selectedRoleId: string;
  onSelectRoleId: (id: string) => void;
  onOpenAddRoleModal: () => void;
  blindMode: boolean;
  onToggleBlindMode: (val: boolean) => void;
  selectedAIMode: AIMode;
  onSelectAIMode: (mode: AIMode) => void;
  providerMeta?: {
    provider_name?: string;
    model_name?: string;
    is_fallback?: boolean;
    latency_ms?: number;
  } | null;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  roles,
  selectedRoleId,
  onSelectRoleId,
  onOpenAddRoleModal,
  blindMode,
  onToggleBlindMode,
  selectedAIMode,
  onSelectAIMode,
  providerMeta,
}) => {
  const activeRole = roles.find((r) => r.id === selectedRoleId);

  return (
    <header
      style={{
        backgroundColor: '#0a0f1d',
        color: '#ffffff',
        padding: '0 24px',
        height: '56px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.45)',
        position: 'relative',
        zIndex: 100,
        boxSizing: 'border-box',
      }}
    >
      {/* Brand & Product Statement */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 900,
              fontSize: '14px',
              letterSpacing: '0.02em',
              boxShadow: '0 0 14px rgba(37, 99, 235, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              flexShrink: 0,
            }}
          >
            HF
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1
                style={{
                  margin: 0,
                  fontSize: '18px',
                  fontWeight: 900,
                  letterSpacing: '-0.03em',
                  color: '#ffffff',
                  lineHeight: 1.1,
                }}
              >
                HireFlow
              </h1>
              <span
                style={{
                  backgroundColor: 'rgba(56, 189, 248, 0.08)',
                  color: '#38bdf8',
                  fontSize: '9.5px',
                  padding: '2px 7px',
                  borderRadius: '4px',
                  fontWeight: 800,
                  letterSpacing: '0.06em',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  textTransform: 'uppercase',
                  lineHeight: 1.2,
                }}
              >
                ENTERPRISE COCKPIT
              </span>
            </div>
            <p
              style={{
                margin: '2px 0 0 0',
                fontSize: '11px',
                color: '#94a3b8',
                letterSpacing: '-0.01em',
                fontWeight: 400,
                lineHeight: 1.2,
              }}
            >
              Evidence-First AI Screening &amp; Interview Intelligence
            </p>
          </div>
        </div>

        {/* Role Context Selector */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            borderLeft: '1px solid rgba(255, 255, 255, 0.08)',
            paddingLeft: '16px',
            marginLeft: '4px',
          }}
        >
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Active Role:
          </span>
          <select
            value={selectedRoleId}
            onChange={(e) => onSelectRoleId(e.target.value)}
            style={{
              height: '34px',
              backgroundColor: '#0f172a',
              color: '#f8fafc',
              border: '1px solid #1e293b',
              padding: '0 12px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none',
              maxWidth: '260px',
              boxSizing: 'border-box',
              transition: 'border-color 0.15s ease',
            }}
          >
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title} ({r.department || 'General'})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onOpenAddRoleModal}
            style={{
              height: '34px',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              color: '#38bdf8',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              padding: '0 11px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'all 0.15s ease',
              boxSizing: 'border-box',
              flexShrink: 0,
            }}
            title="Create a new job requisition role"
          >
            <Plus size={14} />
            <span>Add Role</span>
          </button>
          {activeRole && (
            <span
              style={{
                height: '34px',
                boxSizing: 'border-box',
                display: 'inline-flex',
                alignItems: 'center',
                fontSize: '11px',
                color: '#94a3b8',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                padding: '0 10px',
                borderRadius: '6px',
                fontWeight: 600,
                letterSpacing: '-0.01em',
              }}
            >
              {activeRole.min_years_experience}+ Yrs Exp Required
            </span>
          )}
        </div>
      </div>

      {/* Global Controls & Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {/* Blind Screening Toggle */}
        <button
          onClick={() => onToggleBlindMode(!blindMode)}
          style={{
            height: '34px',
            boxSizing: 'border-box',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '7px',
            backgroundColor: blindMode ? 'rgba(16, 185, 129, 0.12)' : '#0f172a',
            color: blindMode ? '#34d399' : '#94a3b8',
            border: blindMode ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid #1e293b',
            padding: '0 12px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 700,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: blindMode ? '0 0 12px rgba(16, 185, 129, 0.2)' : 'none',
          }}
          title="Masks candidate name, email, phone, and photos to prevent demographic bias."
        >
          {blindMode ? <EyeOff size={14} color="#34d399" /> : <Eye size={14} color="#94a3b8" />}
          <span>Blind Mode: {blindMode ? 'ACTIVE' : 'OFF'}</span>
        </button>

        {/* AI Provider & Telemetry Pill */}
        <div
          style={{
            height: '34px',
            boxSizing: 'border-box',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#0f172a',
            border: '1px solid #1e293b',
            padding: '0 12px',
            borderRadius: '6px',
          }}
        >
          <Brain size={15} color={selectedAIMode === 'OFFLINE_FALLBACK' ? '#f59e0b' : '#38bdf8'} />
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', lineHeight: 1 }}>
              <span
                style={{
                  fontSize: '9px',
                  fontWeight: 800,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  color: selectedAIMode === 'OFFLINE_FALLBACK' ? '#fbbf24' : '#38bdf8',
                }}
              >
                {selectedAIMode === 'OFFLINE_FALLBACK' ? 'OFFLINE FALLBACK' : 'LIVE MODEL'}
              </span>
              {providerMeta?.latency_ms !== undefined && (
                <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'monospace' }}>
                  {providerMeta.latency_ms}ms
                </span>
              )}
            </div>
            <select
              value={selectedAIMode}
              onChange={(e) => onSelectAIMode(e.target.value as AIMode)}
              style={{
                backgroundColor: 'transparent',
                color: '#e2e8f0',
                border: 'none',
                fontSize: '11px',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
                padding: 0,
                lineHeight: 1.2,
              }}
            >
              <option value="OFFLINE_FALLBACK" style={{ backgroundColor: '#111827', color: '#ffffff' }}>
                Deterministic Rule Engine (Zero Cost)
              </option>
              <option value="LIVE_GEMINI" style={{ backgroundColor: '#111827', color: '#ffffff' }}>
                Google Gemini 2.5
              </option>
              <option value="LIVE_GROQ" style={{ backgroundColor: '#111827', color: '#ffffff' }}>
                Groq Cloud LLaMA 3.3
              </option>
            </select>
          </div>
        </div>

        {/* Database & Health Telemetry */}
        <div
          style={{
            height: '34px',
            boxSizing: 'border-box',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#0f172a',
            border: '1px solid #1e293b',
            padding: '0 12px',
            borderRadius: '6px',
            fontSize: '11px',
            fontWeight: 600,
            color: '#cbd5e1',
          }}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: health?.database_connected ? '#10b981' : '#f59e0b',
              boxShadow: health?.database_connected ? '0 0 8px #10b981' : 'none',
            }}
          />
          <span>DB: {health?.database_connected ? 'Connected' : 'Connecting...'}</span>
        </div>
      </div>
    </header>
  );
};
