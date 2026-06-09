import React from 'react';
import { EyeOff, Lock, Check, X, Shield, AlertTriangle } from 'lucide-react';

export default function MMFOPDPanel({ data }) {
  const raw = data?.raw_data_summary || {};
  const semantics = data?.educational_semantics || {};
  const card = data?.context_card || {};
  const log = data?.privacy_log || {};

  return (
    <section className="content-stack mmfopd-panel-container">
      {/* Title block */}
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <EyeOff size={28} style={{ color: 'var(--color-blue)' }} />
          <span>MM-FOPD Student Profile Privacy Protection (画像隐私模糊控制层)</span>
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Raw high-dimensional student biometric signals are intercepted locally, obfuscated, and dynamically transformed into a minimum teaching context card before any LLM agent execution node can ingest it.
        </p>
      </div>

      {/* Warning/Security Badge */}
      <div className="fopd-shield-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem', backgroundColor: 'rgba(59, 130, 246, 0.04)', border: '1px solid var(--color-blue)', borderRadius: '12px', padding: '1rem 1.25rem', marginBottom: '1.5rem' }}>
        <Lock size={32} style={{ color: 'var(--color-blue)', flexShrink: 0 }} />
        <div>
          <h4 style={{ margin: '0 0 0.15rem 0', color: '#ffffff', fontSize: '0.9rem' }}>多模态物理数据红线隔离边界 (MM-FOPD Physical Isolation Boundary Active)</h4>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
            <strong>信息安全声明：</strong> 学生物理手写笔迹坐标、原始声纹特征文件、面部微表情信号以及全量长期学情，<strong>全权隔离在解密单元本地</strong>。严禁向任何大模型节点发送原始物理特征，彻底断绝“从会话反向重构用户真实实体”的画像重组威胁。
          </p>
        </div>
      </div>

      {/* Three Column Cards Layout */}
      <div className="three-column-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        
        {/* Column 1: Stored locally */}
        <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="data-panel-title" style={{ color: 'var(--color-blue)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--color-blue)' }}></span>
            <span>1. Raw Multimodal Data Intercepted</span>
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
            🔒 <em>Biometrics stored securely on local client. NEVER passed downstream.</em>
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem' }}>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>错题屏幕截图数据源 (screenshot image):</span>
              <div style={{ fontFamily: 'monospace', color: '#cbd5e1', marginTop: '0.15rem' }}>{raw.wrong_answer_image_path || "data/raw/wrong_answer_screenshot_003.png"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>声纹特征数据轴 (stress audio coordinates):</span>
              <div style={{ fontFamily: 'monospace', color: '#cbd5e1', marginTop: '0.15rem' }}>{raw.audio_feature_path || "data/raw/audio_features/stress_features_task_003.json"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>手写笔迹压感坐标 (handwriting stroke path):</span>
              <div style={{ fontFamily: 'monospace', color: '#cbd5e1', marginTop: '0.15rem' }}>{raw.handwriting_trace_path || "data/raw/handwriting/traces_task_003.json"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>面部实时情绪信号 (expression state):</span>
              <div style={{ fontFamily: 'monospace', color: '#cbd5e1', marginTop: '0.15rem' }}>{raw.expression_feature_path || "data/raw/facial_landmarks/expr_task_003.json"}</div>
            </div>
          </div>
        </div>

        {/* Column 2: Cognitive Details */}
        <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="data-panel-title" style={{ color: 'var(--color-blue)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--color-blue)' }}></span>
            <span>2. Parsed Educational Semantics</span>
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
            💡 <em>Cognitive markers extracted locally to enable personalized tutoring.</em>
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem' }}>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>错因判定 (Possible Error Cause):</span>
              <div style={{ color: 'var(--color-yellow)', marginTop: '0.15rem', fontWeight: 'bold' }}>{semantics.possible_cause || "Misunderstanding common differences in arithmetic operations"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>当前缺陷诊断 (Cognitive Deficit Class):</span>
              <div style={{ color: '#ffffff', marginTop: '0.15rem' }}>{semantics.current_error_type || "arithmetic index misalignment"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>错题关联知识点 (Knowledge point):</span>
              <div style={{ color: '#ffffff', marginTop: '0.15rem' }}>{semantics.knowledge_point || "arithmetic sequence"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>学情判定信号 (Learner state summary):</span>
              <div style={{ color: '#ffffff', marginTop: '0.15rem' }}>{semantics.learner_state_summary || "Low confidence in recursive sequences"}</div>
            </div>
          </div>
        </div>

        {/* Column 3: Minimum Context Card */}
        <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="data-panel-title" style={{ color: 'var(--color-blue)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--color-blue)' }}></span>
            <span>3. Minimum Teaching Context Card</span>
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
            ✔️ <em>The ONLY context structure released to upstream LLM tutoring agents.</em>
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Student Hash:</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 'bold' }}>{card.student_hash || "hash_b5f2a1b9"}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Task Reference:</span>
              <span style={{ fontFamily: 'monospace' }}>{card.task_id || "task_0003"}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Knowledge point:</span>
              <span>{card.knowledge_point || "arithmetic sequence"}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Deficit diagnosed:</span>
              <span style={{ color: 'var(--color-yellow)' }}>{card.current_error_type || "arithmetic index misalignment"}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Obfuscation rate:</span>
              <strong style={{ color: 'var(--color-green)' }}>99.9% Obfuscated</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>Disclosure budget:</span>
              <strong style={{ color: 'var(--color-blue)' }}>{Number(log?.disclosure_score_after ?? 0.24).toFixed(2)} / 0.75 Limit</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Blocked vs Released Table Comparison */}
      <div className="data-panel" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem' }}>
        <div className="data-panel-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.95rem' }}>
          🛡️画像脱敏要素对照清单 (Interception Comparison Audit Checklist)
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
          <div>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-green)', display: 'flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.5rem' }}>
              <Check size={16} /> Allowed to cloud-based tutoring agent (放行至 tutoring 智能体的数据)
            </span>
            <div className="tag-list">
              {['student_hash (加密ID)', 'task_id (任务标号)', 'knowledge_point (核心考点)', 'current_error_type (错误类型描述)', 'suggested_teaching_strategy (安全辅导话术建议)'].map(t => (
                <span key={t} className="tag-badge allowed" style={{ fontSize: '0.7rem' }}>{t}</span>
              ))}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-red)', display: 'flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.5rem' }}>
              <X size={16} /> Forbidden & blocked from cloud-based agent (本地严格拦截物理隔离数据)
            </span>
            <div className="tag-list">
              {['raw screenshot screenshot.png (原始截图)', 'audio coordinates (声纹特征文件)', 'handwriting stroke path (物理笔迹特征)', 'expression state markers (表情微表情信号)', 'full historic student profile (全量长期隐私学情)'].map(t => (
                <span key={t} className="tag-badge forbidden" style={{ fontSize: '0.7rem' }}>{t}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
