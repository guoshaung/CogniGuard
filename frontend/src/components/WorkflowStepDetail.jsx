import React from 'react';
import { Terminal, Shield, Cpu, Clock } from 'lucide-react';
import DecisionBadge from './DecisionBadge';

export default function WorkflowStepDetail({ step }) {
  if (!step) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
        Select a timeline step or flow node to inspect detailed execution metadata.
      </div>
    );
  }

  const risk = Number(step.risk_score ?? 0.05);

  return (
    <div className="workflow-step-detail-container" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <Terminal size={16} />
        <span>审计控制室：阶段 {step.step_id}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--color-blue)' }}>{step.step_name}</h3>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', display: 'block', marginTop: '0.15rem' }}>
            防御阻断层 (Layer): <strong>{step.layer}</strong>
          </span>
        </div>

        {/* Timestamps */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
          <Clock size={12} />
          <span>审计时间戳 (Telemetry timestamp): {step.timestamp || '2026-05-27T19:12Z'}</span>
        </div>

        {/* Metadata grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '0.25rem' }}>
          <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.5rem' }}>
            <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: '0.15rem' }}>TPCS controller Decision</span>
            <DecisionBadge decision={step.tpcs_decision} />
          </div>

          <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.5rem' }}>
            <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: '0.15rem' }}>NeMo safety decision</span>
            <DecisionBadge decision={step.nemo_decision || 'not_enabled'} />
          </div>
        </div>

        {/* Risk score */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.5rem 0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>节点实时安全风险评级:</span>
          <span className={`risk-badge ${risk > 0.3 ? 'high' : 'low'}`} style={{ fontSize: '0.7rem', fontWeight: 'bold' }}>
            {risk > 0.3 ? '⚠️ 高风险威胁' : '🛡️ 安全流转'} ({risk.toFixed(2)})
          </span>
        </div>

        {/* Payload Inputs/Outputs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.25rem' }}>
          <div>
            <span className="percent-label" style={{ fontSize: '0.7rem', display: 'block', marginBottom: '0.25rem' }}>截获智能体输入载荷 (JSON Input):</span>
            <pre className="json-block input" style={{ margin: 0, maxHeight: '180px', fontSize: '0.7rem' }}>
              {JSON.stringify(step.input_summary ?? {}, null, 2)}
            </pre>
          </div>

          <div>
            <span className="percent-label" style={{ fontSize: '0.7rem', display: 'block', marginBottom: '0.25rem' }}>审计智能体输出报文 (JSON Output):</span>
            <pre className="json-block output" style={{ margin: 0, maxHeight: '180px', fontSize: '0.7rem' }}>
              {JSON.stringify(step.output_summary ?? {}, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
