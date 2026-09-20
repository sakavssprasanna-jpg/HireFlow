import React from 'react';
import { Scale, CheckCircle2, AlertTriangle, HelpCircle, XCircle, FileX } from 'lucide-react';
import { Role } from '../types';

interface FormulaInspectorProps {
  role?: Role;
  compact?: boolean;
}

export const FormulaInspector: React.FC<FormulaInspectorProps> = ({ role, compact = false }) => {
  const wMust = role?.weight_must_have ? Math.round(role.weight_must_have * 100) : 65;
  const wNice = role?.weight_nice_to_have ? Math.round(role.weight_nice_to_have * 100) : 20;
  const wExp = role?.weight_experience ? Math.round(role.weight_experience * 100) : 15;

  return (
    <div
      style={{
        backgroundColor: '#0f172a',
        border: '1px solid #1e293b',
        borderRadius: '8px',
        padding: compact ? '14px' : '20px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <Scale size={18} color="#38bdf8" />
        <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#ffffff' }}>
          Deterministic Fit Formula Inspector
        </h3>
        <span
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            color: '#34d399',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            fontSize: '10px',
            fontWeight: 700,
            padding: '2px 7px',
            borderRadius: '10px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          100% Pure Math
        </span>
      </div>

      <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: '#94a3b8', lineHeight: '1.5' }}>
        Scores are calculated purely by deterministic equations. The AI reasons over text and proposes evidence, but has <strong style={{ color: '#e2e8f0' }}>zero authority</strong> to invent, manipulate, or assign numerical fit scores.
      </p>

      {/* Formula Box */}
      <div
        style={{
          backgroundColor: '#070b14',
          border: '1px solid #1e293b',
          color: '#38bdf8',
          padding: '12px 16px',
          borderRadius: '6px',
          fontFamily: 'monospace',
          fontSize: '13px',
          fontWeight: 600,
          marginBottom: '16px',
          overflowX: 'auto',
          boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.4)',
        }}
      >
        Final Fit = (S_must × {wMust}% + S_nice × {wNice}% + S_exp × {wExp}%) × 100
      </div>

      {/* Component Weights */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '16px' }}>
        <div
          style={{
            backgroundColor: '#131d35',
            border: '1px solid #1e293b',
            padding: '10px',
            borderRadius: '6px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>Must-Have Weight</div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#ffffff', marginTop: '2px' }}>
            {wMust}%
          </div>
          <div style={{ fontSize: '10px', color: '#64748b' }}>Critical core criteria</div>
        </div>

        <div
          style={{
            backgroundColor: '#131d35',
            border: '1px solid #1e293b',
            padding: '10px',
            borderRadius: '6px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>Nice-To-Have Weight</div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#ffffff', marginTop: '2px' }}>
            {wNice}%
          </div>
          <div style={{ fontSize: '10px', color: '#64748b' }}>Bonus accelerators</div>
        </div>

        <div
          style={{
            backgroundColor: '#131d35',
            border: '1px solid #1e293b',
            padding: '10px',
            borderRadius: '6px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>Experience Weight</div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#ffffff', marginTop: '2px' }}>
            {wExp}%
          </div>
          <div style={{ fontSize: '10px', color: '#64748b' }}>Tenure benchmark</div>
        </div>
      </div>

      {/* Status Points Mapping */}
      <div style={{ borderTop: '1px solid #1e293b', paddingTop: '12px' }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Status Point Values:
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#34d399' }}>
            <CheckCircle2 size={13} color="#10b981" />
            <span><strong>PROVEN:</strong> +1.0</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#fbbf24' }}>
            <AlertTriangle size={13} color="#f59e0b" />
            <span><strong>PARTIAL:</strong> +0.5</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#a5b4fc' }}>
            <HelpCircle size={13} color="#818cf8" />
            <span><strong>UNVERIFIED:</strong> 0.0</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#94a3b8' }}>
            <FileX size={13} color="#64748b" />
            <span><strong>NOT FOUND:</strong> 0.0</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#f87171' }}>
            <XCircle size={13} color="#ef4444" />
            <span><strong>CONTRADICTED:</strong> -0.5</span>
          </div>
        </div>
      </div>
    </div>
  );
};
