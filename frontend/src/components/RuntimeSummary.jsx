import React from 'react';
import { AlertTriangle, ShieldCheck, Key, RefreshCw, Terminal, CheckCircle } from 'lucide-react';

export default function RuntimeSummary({ pipelineData, runtimeStatus }) {
  const roundId = pipelineData?.round_id || 'Not Started';
  const mode = pipelineData?.runtime_status?.runtime_mode || runtimeStatus?.runtime_mode || 'mock';
  const callMode = pipelineData?.runtime_status?.agent_call_mode || runtimeStatus?.agent_call_mode || 'deterministic_fallback';
  const apiKeyLoaded = pipelineData?.runtime_status?.api_key_loaded ?? runtimeStatus?.api_key_loaded ?? false;
  const nemoEnabled = pipelineData?.runtime_status?.nemo_guardrails_enabled ?? runtimeStatus?.nemo_guardrails_enabled ?? false;
  const stepsCount = pipelineData?.workflow_steps?.length || 0;
  const auditComplete = pipelineData?.audit_trace?.audit_complete ?? false;

  const isMock = callMode === 'deterministic_fallback' || mode === 'mock';

  return (
    <div className="runtime-summary-container">
      {/* Alert Row */}
      {isMock ? (
        <div className="alert-card warning" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', backgroundColor: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: '8px', padding: '0.75rem 1rem', color: 'var(--color-yellow)' }}>
          <AlertTriangle size={18} />
          <strong>This run uses deterministic fallback. No real LLM call was made. (当前运行使用本地确定性规则集回退，未调用物理大模型。)</strong>
        </div>
      ) : (
        <div className="alert-card success" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', backgroundColor: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '8px', padding: '0.75rem 1rem', color: 'var(--color-green)' }}>
          <CheckCircle size={18} />
          <strong>Real LLM calls enabled. (大模型物理调用已成功激活。)</strong>
        </div>
      )}

      {/* Summary Grid Cards */}
      <div className="summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="summary-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>Round Trace ID</span>
          <strong style={{ fontSize: '1rem', color: '#ffffff', fontFamily: 'monospace' }}>{roundId}</strong>
        </div>

        <div className="summary-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>Runtime Mode</span>
          <strong style={{ fontSize: '1rem', color: mode.includes('guard') ? 'var(--color-green)' : 'var(--color-yellow)' }}>
            {mode === 'guarded_llm' ? '🛡️ Guarded LLM' : mode === 'llm' ? '⚠️ Direct LLM' : '⚙️ Mock Sandbox'}
          </strong>
        </div>

        <div className="summary-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>API Key Loaded</span>
          <strong style={{ fontSize: '1rem', color: apiKeyLoaded ? 'var(--color-green)' : 'var(--color-text-muted)' }}>
            {apiKeyLoaded ? '🔑 Active (已加载)' : '🔒 Inactive (未探测)'}
          </strong>
        </div>

        <div className="summary-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>NeMo Guardrails</span>
          <strong style={{ fontSize: '1rem', color: nemoEnabled ? 'var(--color-green)' : 'var(--color-text-muted)' }}>
            {nemoEnabled ? '🛡️ Enabled (已装载)' : '🚫 Disabled (未装载)'}
          </strong>
        </div>

        <div className="summary-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>Telemetry Steps</span>
          <strong style={{ fontSize: '1rem', color: 'var(--color-blue)' }}>{stepsCount} Ingestions</strong>
        </div>

        <div className="summary-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>Watermark Audit</span>
          <strong style={{ fontSize: '1rem', color: auditComplete ? 'var(--color-green)' : 'var(--color-text-muted)' }}>
            {auditComplete ? '✅ Complete (签名链完备)' : '⏳ Pending (等待注入)'}
          </strong>
        </div>
      </div>
    </div>
  );
}
