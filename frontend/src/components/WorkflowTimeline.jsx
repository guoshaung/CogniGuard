import React from 'react';
import { Shield, GitBranch, Cpu, Lock, Terminal, Activity } from 'lucide-react';
import DecisionBadge from './DecisionBadge';

export default function WorkflowTimeline({ steps, activeStep, onSelectStep }) {
  const getStepIcon = (layer) => {
    const l = String(layer).toLowerCase();
    if (l.includes('fopd')) return <EyeOff size={14} style={{ color: 'var(--color-blue)' }} />;
    if (l.includes('c2')) return <BookOpen size={14} style={{ color: 'var(--color-purple)' }} />;
    if (l.includes('hsw') || l.includes('watermark') || l.includes('audit')) return <Terminal size={14} style={{ color: 'var(--color-green)' }} />;
    if (l.includes('tpcs')) return <GitBranch size={14} style={{ color: 'var(--color-yellow)' }} />;
    if (l.includes('nemo')) return <Shield size={14} style={{ color: 'var(--color-red)' }} />;
    return <Cpu size={14} style={{ color: 'var(--color-text-muted)' }} />;
  };

  return (
    <div className="workflow-timeline-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
        Workflow Steps Ingested ({steps.length})
      </span>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '550px', overflowY: 'auto', paddingRight: '0.25rem' }}>
        {steps.map((step) => {
          const stepId = step.step_id ?? 0;
          const isSelected = activeStep === stepId;
          const risk = Number(step.risk_score ?? 0.05);

          return (
            <div
              key={stepId}
              onClick={() => onSelectStep(stepId)}
              className={`timeline-step-row ${isSelected ? 'active' : ''}`}
              style={{
                backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-secondary)',
                border: isSelected ? '1px solid var(--color-blue)' : '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '0.75rem',
                cursor: 'pointer',
                transition: 'var(--transition-smooth)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem'
              }}
            >
              <div className="timeline-num-badge" style={{
                width: '22px',
                height: '22px',
                borderRadius: '50%',
                backgroundColor: isSelected ? 'var(--color-blue)' : 'rgba(255,255,255,0.03)',
                color: isSelected ? '#ffffff' : 'var(--color-text-muted)',
                fontSize: '0.7rem',
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                {stepId}
              </div>

              <div style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ fontSize: '0.8rem', color: '#ffffff', display: 'block' }}>
                    {step.step_name}
                  </strong>
                </div>
                
                <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>
                  {step.layer}
                </span>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.35rem' }}>
                  <DecisionBadge decision={step.tpcs_decision || 'allow'} />
                  {step.nemo_decision && step.nemo_decision !== 'not_enabled' && step.nemo_decision !== 'not_triggered' && (
                    <span style={{ fontSize: '0.65rem', color: 'var(--color-red)' }}>
                      NeMo: {step.nemo_decision}
                    </span>
                  )}
                  <span style={{ fontSize: '0.65rem', color: risk > 0.3 ? 'var(--color-red)' : 'var(--color-text-muted)' }}>
                    Risk: {risk.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Simple internal icon selector fallback since eye-off is not imported directly here
function EyeOff({ size, style }) {
  return <Terminal size={size} style={style} />;
}
function BookOpen({ size, style }) {
  return <Terminal size={size} style={style} />;
}
