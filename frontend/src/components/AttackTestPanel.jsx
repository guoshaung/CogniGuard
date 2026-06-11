import { useState } from 'react';
import {
  AlertTriangle,
  Braces,
  CheckCircle,
  Crosshair,
  RefreshCw,
  Shield,
  ShieldAlert,
  Swords,
  Zap,
} from 'lucide-react';
import DecisionBadge from './DecisionBadge';

export default function AttackTestPanel({
  attackResults,
  metrics,
  onRunAttackBatch,
  runningAttackBatch,
  onRunSingleAttack,
}) {
  const hasHistory = metrics && metrics.total_attacks > 0;
  const [runningAttackId, setRunningAttackId] = useState(null);
  const [executionResult, setExecutionResult] = useState(null);
  const [localError, setLocalError] = useState('');

  const handleSingleAttack = async (caseId) => {
    if (!onRunSingleAttack) return;
    setRunningAttackId(caseId);
    setLocalError('');
    try {
      const result = await onRunSingleAttack(caseId);
      setExecutionResult({
        mode: 'single',
        timestamp: new Date().toISOString(),
        ...result,
      });
    } catch (error) {
      setLocalError(error.message);
    } finally {
      setRunningAttackId(null);
    }
  };

  const handleBatchAttack = async () => {
    setLocalError('');
    try {
      const result = await onRunAttackBatch();
      setExecutionResult({
        mode: 'batch',
        timestamp: new Date().toISOString(),
        ...result,
      });
    } catch (error) {
      setLocalError(error.message);
    }
  };

  return (
    <section className="content-stack attack-panel-container">
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ShieldAlert size={28} style={{ color: 'var(--color-red)' }} />
            <span>CogniGuard Attack & Defense Sandbox / 模拟攻防沙盘</span>
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Run one attack or the full seven-case suite and inspect the actual TPCS decision returned by the backend.
          </p>
        </div>
      </div>

      <div className="attack-launch-section">
        <button
          className={`attack-launch-btn ${runningAttackBatch ? 'running' : ''}`}
          onClick={handleBatchAttack}
          disabled={runningAttackBatch || Boolean(runningAttackId)}
        >
          <div className="attack-launch-btn-glow" />
          {runningAttackBatch ? (
            <>
              <RefreshCw size={20} className="spin" />
              <span>Running seven attack cases...</span>
            </>
          ) : (
            <>
              <Swords size={20} />
              <span>Launch Full Attack Simulation / 启动全面攻防演练</span>
            </>
          )}
        </button>
        <p className="attack-launch-hint">
          <Zap size={13} />
          <span>Each execution is persisted to the audit history and immediately reflected in the metrics below.</span>
        </p>
      </div>

      {localError && (
        <div className="attack-execution-banner error">
          <AlertTriangle size={18} />
          <span>{localError}</span>
        </div>
      )}

      {executionResult && (
        <div className="attack-execution-result">
          <div className="attack-execution-result-header">
            <div>
              <CheckCircle size={18} />
              <strong>
                {executionResult.mode === 'batch'
                  ? `${executionResult.results?.length || 0} attacks completed`
                  : `${executionResult.case?.attack_case_id || 'Attack'} completed`}
              </strong>
            </div>
            <span>{new Date(executionResult.timestamp).toLocaleTimeString('zh-CN')}</span>
          </div>
          {executionResult.mode === 'single' && executionResult.case && (
            <div className="attack-execution-summary">
              <span>Decision: <strong>{executionResult.case.actual_decision}</strong></span>
              <span>Result: <strong>{executionResult.case.result}</strong></span>
              <span>Risk: <strong>{executionResult.case.risk_score}</strong></span>
              <span>Audit: <strong>{executionResult.case.audit_log_id}</strong></span>
            </div>
          )}
          <details>
            <summary><Braces size={14} /> Inspect execution JSON</summary>
            <pre>{JSON.stringify(executionResult, null, 2)}</pre>
          </details>
        </div>
      )}

      <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem', marginBottom: '2rem' }}>
        <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Shield size={16} style={{ color: 'var(--color-red)' }} />
          <span>Live Attack & Defense Analytics</span>
        </div>

        {!hasHistory ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
            <AlertTriangle size={32} style={{ margin: '0 auto 0.75rem', display: 'block', color: 'var(--color-yellow)' }} />
            <span>No attack execution has been recorded yet.</span>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem' }}>
            <Stat label="Total" value={metrics.total_attacks} />
            <Stat label="Blocked" value={metrics.blocked_attacks} color="var(--color-green)" />
            <Stat label="Sanitized" value={metrics.sanitized_attacks} color="var(--color-blue)" />
            <Stat label="Degraded" value={metrics.degraded_attacks} color="var(--color-yellow)" />
            <Stat label="Escaped" value={metrics.successful_attacks} color="var(--color-red)" />
            <Stat label="Attack success" value={`${(metrics.attack_success_rate * 100).toFixed(1)}%`} />
            <Stat label="Defense rate" value={`${(metrics.defense_success_rate * 100).toFixed(1)}%`} color="var(--color-green)" />
          </div>
        )}
      </div>

      <div className="attack-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {attackResults.map((item) => {
          const isRunning = runningAttackId === item.attack_case_id;
          const isLatest = executionResult?.case?.attack_case_id === item.attack_case_id;
          return (
            <div
              className={`attack-card ${isLatest ? 'latest-execution' : ''}`}
              key={item.attack_case_id}
              style={{
                backgroundColor: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderTop: '3px solid var(--color-red)',
                borderRadius: '12px',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: '250px',
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 'bold', color: 'var(--color-red)', fontSize: '0.75rem' }}>{item.attack_case_id}</span>
                  <span className="risk-badge med" style={{ fontSize: '0.6rem' }}>{item.target_protection_layer}</span>
                </div>
                <h3 style={{ fontSize: '0.85rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#fff' }}>
                  {item.attack_type}
                </h3>
                <div className="attack-prompt-preview">"{item.malicious_prompt}"</div>
              </div>

              <div className="attack-card-footer">
                <div>Target agent: <strong>{item.target_agent}</strong></div>
                <div>Expected defense: <em>{item.expected_defense}</em></div>
                <div className="attack-card-decision-row">
                  <div><span>Decision: </span><DecisionBadge decision={item.actual_decision} /></div>
                  <span className="risk-badge low">{item.result}</span>
                </div>
                <button
                  className="attack-single-btn"
                  onClick={() => handleSingleAttack(item.attack_case_id)}
                  disabled={isRunning || runningAttackBatch}
                >
                  {isRunning ? (
                    <><RefreshCw size={12} className="spin" /> Executing...</>
                  ) : (
                    <><Crosshair size={12} /> Run This Attack / 执行此攻击</>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="attack-stat-card">
      <span className="attack-stat-label">{label}</span>
      <strong className="attack-stat-value" style={{ color }}>{value}</strong>
    </div>
  );
}
