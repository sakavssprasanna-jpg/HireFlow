import React, { useState } from 'react';
import { Layers, Users, FileCheck2, MessageSquare, ShieldCheck, AlertCircle, ChevronRight } from 'lucide-react';

export type CockpitTab = 'requisition' | 'candidates' | 'evidence' | 'interview' | 'audit';

interface NavigationProps {
  activeTab: CockpitTab;
  onTabChange: (tab: CockpitTab) => void;
  requirementsCount: number;
  candidatesCount: number;
  evidenceCount: number;
  criticalGapsCount: number;
  isQuarantined?: boolean;
}

export const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  onTabChange,
  requirementsCount,
  candidatesCount,
  evidenceCount,
  criticalGapsCount,
  isQuarantined,
}) => {
  const [hoveredTab, setHoveredTab] = useState<CockpitTab | null>(null);

  const tabs = [
    {
      id: 'requisition' as CockpitTab,
      step: 1,
      label: 'Requisition',
      subtitle: 'Criteria & Formula',
      icon: Layers,
      count: requirementsCount,
    },
    {
      id: 'candidates' as CockpitTab,
      step: 2,
      label: 'Candidates',
      subtitle: 'Comparison Matrix',
      icon: Users,
      count: candidatesCount,
    },
    {
      id: 'evidence' as CockpitTab,
      step: 3,
      label: 'Evidence',
      subtitle: 'Dual-Pane Studio',
      icon: FileCheck2,
      count: evidenceCount,
      alertCount: criticalGapsCount > 0 ? criticalGapsCount : undefined,
    },
    {
      id: 'interview' as CockpitTab,
      step: 4,
      label: 'Interview',
      subtitle: 'Questions & Reassessment',
      icon: MessageSquare,
      badge: isQuarantined ? 'QUARANTINE' : undefined,
    },
    {
      id: 'audit' as CockpitTab,
      step: 5,
      label: 'Audit & Security',
      subtitle: 'Immutable Logs & Defense',
      icon: ShieldCheck,
    },
  ];

  return (
    <nav
      style={{
        backgroundColor: '#0c1222',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        gap: '2px',
        userSelect: 'none',
      }}
    >
      {tabs.map((tab, index) => {
        const isActive = activeTab === tab.id;
        const isHovered = hoveredTab === tab.id;
        const Icon = tab.icon;

        return (
          <React.Fragment key={tab.id}>
            <button
              onClick={() => onTabChange(tab.id)}
              onMouseEnter={() => setHoveredTab(tab.id)}
              onMouseLeave={() => setHoveredTab(null)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '13px 18px',
                backgroundColor: isActive
                  ? 'rgba(56, 189, 248, 0.08)'
                  : isHovered
                  ? 'rgba(255, 255, 255, 0.04)'
                  : 'transparent',
                border: 'none',
                borderBottom: isActive ? '3px solid #38bdf8' : '3px solid transparent',
                cursor: 'pointer',
                color: isActive ? '#ffffff' : isHovered ? '#f1f5f9' : '#94a3b8',
                transition: 'all 0.15s ease',
                outline: 'none',
                boxShadow: isActive
                  ? 'inset 0 -3px 8px rgba(56, 189, 248, 0.3)'
                  : 'none',
                borderRadius: '4px 4px 0 0',
              }}
            >
              {/* Step Sequence Badge (1 -> 2 -> 3 -> 4 -> 5) */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '20px',
                  height: '20px',
                  borderRadius: '4px',
                  backgroundColor: isActive
                    ? '#38bdf8'
                    : isHovered
                    ? 'rgba(255, 255, 255, 0.12)'
                    : 'rgba(255, 255, 255, 0.06)',
                  color: isActive ? '#080c18' : isHovered ? '#f8fafc' : '#64748b',
                  fontSize: '11px',
                  fontWeight: 900,
                  fontFamily: 'monospace',
                  letterSpacing: '0',
                  flexShrink: 0,
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.step}
              </div>

              {/* Icon */}
              <Icon
                size={16}
                color={isActive ? '#38bdf8' : isHovered ? '#cbd5e1' : '#64748b'}
                style={{ flexShrink: 0, transition: 'color 0.15s ease' }}
              />

              {/* Headings */}
              <div style={{ textAlign: 'left', display: 'flex', flexDirection: 'column' }}>
                <div
                  style={{
                    fontSize: '13.5px',
                    fontWeight: isActive ? 800 : 700,
                    color: isActive ? '#ffffff' : isHovered ? '#f8fafc' : '#94a3b8',
                    letterSpacing: '-0.015em',
                    lineHeight: '1.2',
                    transition: 'color 0.15s ease',
                  }}
                >
                  {tab.label}
                </div>
                <div
                  style={{
                    fontSize: '10px',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? '#7dd3fc' : '#64748b',
                    lineHeight: '1.2',
                    marginTop: '2px',
                    letterSpacing: '0.01em',
                  }}
                >
                  {tab.subtitle}
                </div>
              </div>

              {/* Badges */}
              {tab.count !== undefined && (
                <span
                  style={{
                    backgroundColor: isActive ? 'rgba(56, 189, 248, 0.18)' : 'rgba(255, 255, 255, 0.06)',
                    color: isActive ? '#38bdf8' : '#94a3b8',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 7px',
                    borderRadius: '10px',
                    marginLeft: '4px',
                    border: isActive ? '1px solid rgba(56, 189, 248, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)',
                    lineHeight: 1,
                  }}
                >
                  {tab.count}
                </span>
              )}

              {tab.alertCount !== undefined && tab.alertCount > 0 && (
                <span
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.18)',
                    color: '#f87171',
                    fontSize: '10px',
                    fontWeight: 800,
                    padding: '2px 6px',
                    borderRadius: '10px',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px',
                    lineHeight: 1,
                  }}
                  title={`${tab.alertCount} critical gaps detected`}
                >
                  <AlertCircle size={11} color="#f87171" />
                  {tab.alertCount}
                </span>
              )}

              {tab.badge && (
                <span
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.22)',
                    color: '#f87171',
                    fontSize: '9.5px',
                    fontWeight: 800,
                    letterSpacing: '0.05em',
                    padding: '2.5px 7px',
                    borderRadius: '4px',
                    border: '1px solid rgba(239, 68, 68, 0.5)',
                    lineHeight: 1,
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </button>

            {/* Sequence Flow Separator */}
            {index < tabs.length - 1 && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0 2px',
                  opacity: 0.35,
                  userSelect: 'none',
                }}
              >
                <ChevronRight size={14} color="#64748b" />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};
