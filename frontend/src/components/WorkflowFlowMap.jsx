import React from 'react';
import { ArrowRight, GitBranch } from 'lucide-react';
import DecisionBadge from './DecisionBadge';

const flowNodes = [
  { id: 1, label: 'MM-FOPD Context Card', layer: 'MM-FOPD', color: 'var(--color-blue)' },
  { id: 2, label: 'TPCS Privacy Pre-check', layer: 'TPCS', color: 'var(--color-yellow)' },
  { id: 3, label: 'NeMo Input Rail', layer: 'Guardrail', color: 'var(--color-red)' },
  { id: 4, label: 'ProfileDiagnosisAgent', layer: 'Agent', color: 'var(--color-blue)' },
  { id: 5, label: 'Resource Agent', layer: 'Agent', color: 'var(--color-purple)' },
  { id: 6, label: 'C2-RAG Exposure Control', layer: 'C2-RAG', color: 'var(--color-purple)' },
  { id: 7, label: 'NeMo Retrieval Rail', layer: 'Guardrail', color: 'var(--color-red)' },
  { id: 8, label: 'Teaching Agent', layer: 'Agent', color: 'var(--color-green)' },
  { id: 9, label: 'NeMo Output Rail', layer: 'Guardrail', color: 'var(--color-red)' },
  { id: 10, label: 'Assessment Agent', layer: 'Agent', color: '#ec4899' },
  { id: 11, label: 'TPCS Profile Review', layer: 'TPCS', color: 'var(--color-yellow)' },
  { id: 12, label: 'HSW-ST Audit Binding', layer: 'HSW-ST', color: 'var(--color-green)' },
];

export default function WorkflowFlowMap({ pipelineData, activeStep, onSelectStep }) {
  const steps = pipelineData?.workflow_steps || [];

  const getNodeDetails = (node) => {
    const step = steps.find((item) => item.step_id === node.id);
    return {
      step,
      ingested: Boolean(step),
      decision: step?.tpcs_decision || step?.nemo_decision || 'Pending',
      risk: Number(step?.risk_score ?? 0),
    };
  };

  return (
    <div className="flow-map-container" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
      <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <GitBranch size={18} style={{ color: 'var(--color-blue)' }} />
        <span>CogniGuard Live Mediation Flow Map</span>
      </div>

      <div className="flow-map-scroll-wrapper" style={{ overflowX: 'auto', padding: '0.5rem 0' }}>
        <div className="flow-map-flex" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 'max-content' }}>
          {flowNodes.map((node, index) => {
            const { decision, risk, ingested } = getNodeDetails(node);
            const isSelected = activeStep === node.id;

            return (
              <React.Fragment key={node.id}>
                <div
                  onClick={() => onSelectStep(node.id)}
                  className={`flow-node-card ${isSelected ? 'active' : ''} ${ingested ? 'ingested' : 'pending'}`}
                  style={{
                    backgroundColor: ingested ? 'var(--bg-primary)' : 'rgba(7, 10, 16, 0.45)',
                    border: isSelected ? `2px solid ${node.color}` : '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    cursor: 'pointer',
                    width: '185px',
                    flexShrink: 0,
                    transition: 'var(--transition-smooth)',
                    boxShadow: isSelected ? `0 0 12px ${node.color}55` : 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '115px',
                    opacity: ingested || isSelected ? 1 : 0.45,
                  }}
                >
                  <div>
                    <span style={{ fontSize: '0.6rem', color: node.color, fontWeight: '700', textTransform: 'uppercase', display: 'block', marginBottom: '0.15rem' }}>
                      Step {node.id} / {node.layer}
                    </span>
                    <strong style={{ fontSize: '0.75rem', color: '#ffffff', display: 'block', lineHeight: '1.3', wordBreak: 'break-word' }}>
                      {node.label}
                    </strong>
                  </div>

                  <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.65rem' }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>{ingested ? 'Ingested' : 'Pending'}</span>
                      <span style={{ color: risk > 0.3 ? 'var(--color-red)' : 'var(--color-green)', fontWeight: 'bold' }}>
                        {risk.toFixed(2)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.15rem' }}>
                      <DecisionBadge decision={decision} />
                    </div>
                  </div>
                </div>

                {index < flowNodes.length - 1 && (
                  <ArrowRight size={16} style={{ color: 'var(--color-text-muted)', opacity: 0.5, flexShrink: 0 }} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
