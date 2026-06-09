import React, { useState } from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle, Shield, Play, Zap, RefreshCw, Crosshair, Swords } from 'lucide-react';
import DecisionBadge from './DecisionBadge';

export default function AttackTestPanel({ attackResults, metrics, onRunAttackBatch, runningAttackBatch, onRunSingleAttack }) {
  const hasHistory = metrics && metrics.total_attacks > 0;
  const [runningAttackId, setRunningAttackId] = useState(null);

  const handleSingleAttack = async (caseId) => {
    if (!onRunSingleAttack) return;
    setRunningAttackId(caseId);
    try {
      await onRunSingleAttack(caseId);
    } finally {
      setRunningAttackId(null);
    }
  };

  return (
    <section className="content-stack attack-panel-container">
      {/* Title */}
      <div className="section-header" style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ShieldAlert size={28} style={{ color: 'var(--color-red)' }} />
            <span>CogniGuard 攻防演练与防御决策测试舱 (Attack & Defense Lab)</span>
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Inject high-risk malicious prompt payloads directly to target agents and evaluate the horizontal mediation controller's safety enforcement in real-time.
          </p>
        </div>
      </div>

      {/* Launch Attack Button */}
      <div className="attack-launch-section">
        <button
          className={`attack-launch-btn ${runningAttackBatch ? 'running' : ''}`}
          onClick={onRunAttackBatch}
          disabled={runningAttackBatch}
        >
          <div className="attack-launch-btn-glow" />
          {runningAttackBatch ? (
            <>
              <RefreshCw size={20} className="spin" />
              <span>正在执行攻防演练...</span>
            </>
          ) : (
            <>
              <Swords size={20} />
              <span>启动全面攻防演练 / Launch Attack Simulation</span>
            </>
          )}
        </button>
        <p className="attack-launch-hint">
          <Zap size={13} />
          <span>批量注入 7 种高危攻击向量，测试 TPCS 中介控制器的横向隔离与安全拦截能力</span>
        </p>
      </div>

      {/* Dynamic Summary Dashboard */}
      <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem', marginBottom: '2rem' }}>
        <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Shield size={16} style={{ color: 'var(--color-red)' }} />
          <span>攻防演练防御决策状态统计 (Live Attack & Defense Analytics)</span>
        </div>

        {!hasHistory ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
            <AlertTriangle size={32} style={{ margin: '0 auto 0.75rem', display: 'block', color: 'var(--color-yellow)' }} />
            <span>暂无攻防演练记录。请点击上方 <strong>"启动全面攻防演练"</strong> 按钮开始注入攻击向量。</span>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem' }}>
            <div className="attack-stat-card">
              <span className="attack-stat-label">总测试注入次数 (Total)</span>
              <strong className="attack-stat-value">{metrics.total_attacks} 次</strong>
            </div>
            <div className="attack-stat-card stat-green">
              <span className="attack-stat-label">强力阻断拦截 (Blocked)</span>
              <strong className="attack-stat-value" style={{ color: 'var(--color-green)' }}>{metrics.blocked_attacks} 次</strong>
            </div>
            <div className="attack-stat-card stat-blue">
              <span className="attack-stat-label">文本脱敏净化 (Sanitized)</span>
              <strong className="attack-stat-value" style={{ color: 'var(--color-blue)' }}>{metrics.sanitized_attacks} 次</strong>
            </div>
            <div className="attack-stat-card stat-yellow">
              <span className="attack-stat-label">降级凭证审查 (Degraded)</span>
              <strong className="attack-stat-value" style={{ color: 'var(--color-yellow)' }}>{metrics.degraded_attacks} 次</strong>
            </div>
            <div className="attack-stat-card stat-red">
              <span className="attack-stat-label">恶意逃逸成功 (ASR)</span>
              <strong className="attack-stat-value" style={{ color: metrics.successful_attacks > 0 ? 'var(--color-red)' : '#ffffff' }}>{metrics.successful_attacks} 次</strong>
            </div>
            <div className="attack-stat-card">
              <span className="attack-stat-label">攻击成功率 (ASR %)</span>
              <strong className="attack-stat-value" style={{ color: metrics.attack_success_rate > 0 ? 'var(--color-red)' : 'var(--color-green)' }}>
                {(metrics.attack_success_rate * 100).toFixed(1)}%
              </strong>
            </div>
            <div className="attack-stat-card">
              <span className="attack-stat-label">安全防御率 (ADR %)</span>
              <strong className="attack-stat-value" style={{ color: 'var(--color-green)' }}>
                {(metrics.defense_success_rate * 100).toFixed(1)}%
              </strong>
            </div>
          </div>
        )}
      </div>

      {/* Case cards */}
      <div className="attack-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {attackResults.map((item) => {
          const isRunning = runningAttackId === item.attack_case_id;

          return (
            <div
              className="attack-card"
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
                minHeight: '230px'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 'bold', color: 'var(--color-red)', fontSize: '0.75rem' }}>{item.attack_case_id}</span>
                  <span className="risk-badge med" style={{ fontSize: '0.6rem' }}>{item.target_protection_layer}</span>
                </div>
                
                <h3 style={{ fontSize: '0.85rem', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#ffffff' }}>
                  {item.attack_type}
                </h3>
                
                <div style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  padding: '0.5rem',
                  fontFamily: 'monospace',
                  fontSize: '0.7rem',
                  color: 'var(--color-red)',
                  maxHeight: '75px',
                  overflowY: 'auto',
                  lineHeight: '1.4',
                  marginBottom: '0.75rem'
                }}>
                  "{item.malicious_prompt}"
                </div>
              </div>

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
                <div>受侵智能体: <strong style={{ color: '#ffffff' }}>{item.target_agent}</strong></div>
                <div>安全预案设计: <em>{item.expected_defense}</em></div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                  <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                    <span>Decision:</span>
                    <DecisionBadge decision={item.actual_decision} />
                  </div>
                  <div>
                    <span>Result: </span>
                    <span className="risk-badge low" style={{ fontSize: '0.65rem', textTransform: 'uppercase', backgroundColor: 'rgba(16, 185, 129, 0.08)', color: 'var(--color-green)' }}>
                      {item.result}
                    </span>
                  </div>
                </div>

                {/* Single attack trigger button */}
                <button
                  className="attack-single-btn"
                  onClick={() => handleSingleAttack(item.attack_case_id)}
                  disabled={isRunning || runningAttackBatch}
                >
                  {isRunning ? (
                    <><RefreshCw size={12} className="spin" /> 执行中...</>
                  ) : (
                    <><Crosshair size={12} /> 执行此攻击 / Run This Attack</>
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
