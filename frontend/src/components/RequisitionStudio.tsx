import React, { useState } from 'react';
import { Plus, Trash2, AlertCircle, AlertTriangle } from 'lucide-react';
import { Role, RequirementCategory } from '../types';
import { FormulaInspector } from './FormulaInspector';

interface RequisitionStudioProps {
  role?: Role;
  onAddRequirement: (name: string, category: RequirementCategory, description: string, weight: number) => Promise<void>;
  onDeleteRequirement: (requirementId: string, name: string) => Promise<void>;
}

export const RequisitionStudio: React.FC<RequisitionStudioProps> = ({
  role,
  onAddRequirement,
  onDeleteRequirement,
}) => {
  const [showAddForm, setShowAddForm] = useState(false);
  const [name, setName] = useState('');
  const [category, setCategory] = useState<RequirementCategory>('MUST_HAVE');
  const [description, setDescription] = useState('');
  const [weight, setWeight] = useState(1.0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Deletion modal state
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const mustHaves = role?.requirements.filter((r) => r.category === 'MUST_HAVE') || [];
  const niceToHaves = role?.requirements.filter((r) => r.category === 'NICE_TO_HAVE') || [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    // Normalized duplicate prevention check (case-insensitive, whitespace normalized)
    const norm = trimmedName.toLowerCase().replace(/\s+/g, ' ');
    const existing = role?.requirements?.find(
      (r) => r.name.trim().toLowerCase().replace(/\s+/g, ' ') === norm
    );
    if (existing) {
      setFormError('This criterion already exists for the selected role.');
      return;
    }

    setFormError(null);
    setIsSubmitting(true);
    try {
      await onAddRequirement(trimmedName, category, description.trim(), weight);
      setName('');
      setDescription('');
      setShowAddForm(false);
    } catch (err: any) {
      setFormError(err.message || 'Failed to add criterion.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Role Profile Header */}
      <div
        style={{
          backgroundColor: '#0f172a',
          borderRadius: '8px',
          border: '1px solid #1e293b',
          padding: '24px',
          marginBottom: '24px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span
              style={{
                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                fontSize: '10.5px',
                fontWeight: 800,
                padding: '3px 9px',
                borderRadius: '4px',
                textTransform: 'uppercase',
                letterSpacing: '0.07em',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#38bdf8' }} />
              Requisition Profile
            </span>
            <span
              style={{
                fontSize: '12px',
                color: '#94a3b8',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                padding: '3px 10px',
                borderRadius: '4px',
                fontWeight: 500,
              }}
            >
              Dept: <strong style={{ color: '#f1f5f9', fontWeight: 700 }}>{role?.department || 'Engineering'}</strong>
            </span>
            <span
              style={{
                fontSize: '12px',
                color: '#94a3b8',
                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                padding: '3px 10px',
                borderRadius: '4px',
                fontWeight: 500,
              }}
            >
              Min Experience: <strong style={{ color: '#f1f5f9', fontWeight: 700 }}>{role?.min_years_experience || 0} Years</strong>
            </span>
          </div>

          <h2
            style={{
              margin: '12px 0 8px 0',
              fontSize: '26px',
              fontWeight: 900,
              letterSpacing: '-0.025em',
              color: '#ffffff',
              lineHeight: 1.2,
            }}
          >
            {role?.title || 'Job Requisition'}
          </h2>

          <p
            style={{
              margin: 0,
              fontSize: '13.5px',
              color: '#cbd5e1',
              maxWidth: '900px',
              lineHeight: '1.65',
              letterSpacing: '-0.005em',
            }}
          >
            {role?.raw_jd_text || 'No job description text loaded.'}
          </p>
        </div>

        <button
          onClick={() => {
            setShowAddForm(!showAddForm);
            setFormError(null);
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: '#2563eb',
            color: '#ffffff',
            border: '1px solid #3b82f6',
            padding: '8px 16px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(37, 99, 235, 0.3)',
          }}
        >
          <Plus size={16} />
          <span>Add Evaluation Criterion</span>
        </button>
      </div>

      {/* Add Criterion Form Drawer */}
      {showAddForm && (
        <form
          onSubmit={handleSubmit}
          style={{
            backgroundColor: '#111827',
            borderRadius: '8px',
            border: '1px solid #2563eb',
            padding: '20px',
            marginBottom: '24px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          }}
        >
          <h4 style={{ margin: '0 0 14px 0', fontSize: '15px', fontWeight: 700, color: '#60a5fa' }}>
            Define New Grounded Criterion
          </h4>

          {formError && (
            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                color: '#fca5a5',
                padding: '10px 14px',
                borderRadius: '6px',
                fontSize: '12.5px',
                marginBottom: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <AlertCircle size={16} />
              <span>{formError}</span>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '14px', marginBottom: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>
                Skill / Criterion Name *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Distributed Systems Architecture"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (formError) setFormError(null);
                }}
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
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>
                Category Priority
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as RequirementCategory)}
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
              >
                <option value="MUST_HAVE">MUST-HAVE (Core Weight 0.65)</option>
                <option value="NICE_TO_HAVE">NICE-TO-HAVE (Bonus Weight 0.20)</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>
                Relative Weight (0.1 - 5.0)
              </label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="5.0"
                value={weight}
                onChange={(e) => setWeight(parseFloat(e.target.value) || 1.0)}
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
          </div>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '4px' }}>
              Evaluation Scope &amp; Evidence Expectations
            </label>
            <input
              type="text"
              placeholder="e.g. Hands-on experience designing and operating multi-cluster setups in production."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
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
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={() => {
                setShowAddForm(false);
                setFormError(null);
              }}
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
              disabled={isSubmitting}
              style={{
                padding: '8px 18px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 6px rgba(37, 99, 235, 0.4)',
              }}
            >
              {isSubmitting ? 'Saving Criterion...' : 'Save Criterion'}
            </button>
          </div>
        </form>
      )}

      {/* Main Grid: Must-Have vs Nice-To-Have + Formula Inspector */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
        {/* Requirements Breakdown */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* MUST-HAVE Group */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '8px',
              border: '1px solid #1e293b',
              padding: '20px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    color: '#f87171',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    fontSize: '11px',
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    letterSpacing: '0.5px',
                  }}
                >
                  MUST-HAVE
                </span>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#ffffff' }}>
                  Critical Core Criteria ({mustHaves.length})
                </h3>
              </div>
              <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600 }}>
                Category Weight: 65%
              </span>
            </div>

            {mustHaves.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                No must-have requirements defined yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {mustHaves.map((req, idx) => (
                  <div
                    key={req.id}
                    style={{
                      border: '1px solid #1e293b',
                      backgroundColor: '#131d35',
                      padding: '12px 16px',
                      borderRadius: '6px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div style={{ flex: 1, paddingRight: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8', fontFamily: 'monospace' }}>
                          0{idx + 1}
                        </span>
                        <strong style={{ fontSize: '14px', color: '#f8fafc' }}>{req.name}</strong>
                      </div>
                      {req.description && (
                        <p style={{ margin: '4px 0 0 24px', fontSize: '12px', color: '#94a3b8' }}>
                          {req.description}
                        </p>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ textAlign: 'right' }}>
                        <span
                          style={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            color: '#cbd5e1',
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '10px',
                          }}
                        >
                          Weight: {req.weight}x
                        </span>
                        <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px', fontFamily: 'monospace' }}>
                          ID: {req.id.slice(0, 8)}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setConfirmDelete({ id: req.id, name: req.name });
                          setDeleteError(null);
                        }}
                        style={{
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          color: '#f87171',
                          borderRadius: '6px',
                          padding: '7px 9px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'all 0.15s ease',
                        }}
                        title={`Delete criterion "${req.name}"`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* NICE-TO-HAVE Group */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '8px',
              border: '1px solid #1e293b',
              padding: '20px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    backgroundColor: 'rgba(245, 158, 11, 0.15)',
                    color: '#fbbf24',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    fontSize: '11px',
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    letterSpacing: '0.5px',
                  }}
                >
                  NICE-TO-HAVE
                </span>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#ffffff' }}>
                  Bonus Accelerators ({niceToHaves.length})
                </h3>
              </div>
              <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600 }}>
                Category Weight: 20%
              </span>
            </div>

            {niceToHaves.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                No nice-to-have requirements defined yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {niceToHaves.map((req, idx) => (
                  <div
                    key={req.id}
                    style={{
                      border: '1px solid #1e293b',
                      backgroundColor: '#131d35',
                      padding: '12px 16px',
                      borderRadius: '6px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div style={{ flex: 1, paddingRight: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8', fontFamily: 'monospace' }}>
                          0{idx + 1}
                        </span>
                        <strong style={{ fontSize: '14px', color: '#f8fafc' }}>{req.name}</strong>
                      </div>
                      {req.description && (
                        <p style={{ margin: '4px 0 0 24px', fontSize: '12px', color: '#94a3b8' }}>
                          {req.description}
                        </p>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ textAlign: 'right' }}>
                        <span
                          style={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            color: '#cbd5e1',
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '10px',
                          }}
                        >
                          Weight: {req.weight}x
                        </span>
                        <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px', fontFamily: 'monospace' }}>
                          ID: {req.id.slice(0, 8)}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setConfirmDelete({ id: req.id, name: req.name });
                          setDeleteError(null);
                        }}
                        style={{
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          color: '#f87171',
                          borderRadius: '6px',
                          padding: '7px 9px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'all 0.15s ease',
                        }}
                        title={`Delete criterion "${req.name}"`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Formula Inspector Column */}
        <div>
          <FormulaInspector role={role} />
        </div>
      </div>

      {/* Confirmation Modal for Deletion */}
      {confirmDelete && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
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
              width: '100%',
              maxWidth: '480px',
              padding: '24px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
              border: '1px solid #1e293b',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ef4444',
                  flexShrink: 0,
                }}
              >
                <AlertTriangle size={18} />
              </div>
              <h3 style={{ margin: 0, fontSize: '17px', color: '#f8fafc', fontWeight: 700 }}>
                Delete "{confirmDelete.name}" from this role?
              </h3>
            </div>

            <p style={{ fontSize: '13.5px', color: '#cbd5e1', margin: '0 0 12px 0', lineHeight: 1.5 }}>
              Are you sure you want to delete <strong style={{ color: '#f87171' }}>"{confirmDelete.name}"</strong> from{' '}
              <strong style={{ color: '#ffffff' }}>{role?.title}</strong>?
            </p>
            <p style={{ fontSize: '12px', color: '#94a3b8', margin: '0 0 18px 0', lineHeight: 1.5 }}>
              This action permanently removes this criterion from candidate comparison matrices, evidence claims, and
              recalculates candidate fit scores across all remaining criteria.
            </p>

            {deleteError && (
              <div
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid #ef4444',
                  color: '#fca5a5',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <AlertCircle size={15} />
                <span>Unable to delete criterion: {deleteError.replace(/^Unable to delete criterion:\s*/i, '')}</span>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setConfirmDelete(null)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #334155',
                  backgroundColor: '#1e293b',
                  color: '#cbd5e1',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={async () => {
                  if (!confirmDelete) return;
                  setIsDeleting(true);
                  setDeleteError(null);
                  try {
                    await onDeleteRequirement(confirmDelete.id, confirmDelete.name);
                    setConfirmDelete(null);
                  } catch (err: any) {
                    setDeleteError(err.message || 'Failed to delete criterion.');
                  } finally {
                    setIsDeleting(false);
                  }
                }}
                style={{
                  padding: '8px 18px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: '#dc2626',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  boxShadow: '0 2px 6px rgba(220, 38, 38, 0.4)',
                }}
              >
                {isDeleting ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
