import { Fragment } from 'react';
import { Terminal, Database, ArrowRight, ShieldCheck } from 'lucide-react';

export default function AuditTracePanel({ data }) {
  const answer = data?.final_answer || "";
  const audit = data?.audit_trace || {};
  const logs = data?.protection_logs || {};

  const bindingNodes = [
    { label: 'Context Card', desc: `card_${audit.profile_card_id ? audit.profile_card_id.replace('card_', '') : 'task_0001'}`, color: 'var(--color-blue)' },
    { label: 'Resource Chunk', desc: logs.c2_rag?.chunk_id || 'chunk_889e1f6f', color: 'var(--color-purple)' },
    { label: 'Agent Calls', desc: '4 cloud dispatches', color: 'var(--color-text-muted)' },
    { label: 'Final Answer', desc: `ans_${audit.profile_card_id ? audit.profile_card_id.replace('card_', '') : 'task_0001'}`, color: 'var(--color-text-muted)' },
    { label: 'Watermark', desc: audit.watermark_id || 'hsw_st_minimal_id', color: 'var(--color-green)' },
    { label: 'Audit Trace', desc: 'SHA256 Bound', color: 'var(--color-green)' }
  ];

  return (
    <section className="content-stack audit-panel-container">
      {/* Title */}
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Terminal size={28} style={{ color: 'var(--color-green)' }} />
          <span>HSW-ST Generated Content Audit Trace (水印溯源与审计追踪层)</span>
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          By embedding high- ADR heuristic implicit watermarks into tutoring outputs, CogniGuard seals the entire pipeline lineage (Student ID, Chunks, Agent Calls) into a cryptographically bound auditable trace.
        </p>
      </div>

      {/* Final tutoring answer */}
      <div className="final-answer-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem', position: 'relative' }}>
        <div className="watermark-overlay" style={{ position: 'absolute', top: '1rem', right: '1rem', color: 'var(--color-green)', backgroundColor: 'rgba(16, 185, 129, 0.08)', border: '1px dashed var(--color-green)', borderRadius: '4px', padding: '0.25rem 0.5rem', fontSize: '0.7rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <ShieldCheck size={12} />
          <span>HSW-ST Watermark Bound (水印已绑定)</span>
        </div>
        <div className="data-panel-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem' }}>
          🖋️ 最终下发给学生的辅导话术 (Final Sanitized Output Answer)
        </div>
        {answer ? (
          <p className="answer-text" style={{ fontSize: '0.9rem', lineHeight: '1.6', color: '#f1f5f9', whiteSpace: 'pre-wrap', margin: 0 }}>
            {answer}
          </p>
        ) : (
          <div style={{ textAlign: 'center', padding: '1.5rem 0', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
            No protected answer generated yet. Select a student case and click "Run Protected Flow" at the top header to evaluate.
          </div>
        )}
      </div>

      {/* Binding Chain Graphic Flow */}
      <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Database size={16} style={{ color: 'var(--color-green)' }} />
          <span>全链路凭证绑定关系图 (Cryptographic Lineage Binding Flow Map)</span>
        </div>

        <div style={{ overflowX: 'auto', padding: '0.5rem 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 'max-content', justifyContent: 'center' }}>
            {bindingNodes.map((node, idx) => (
              <Fragment key={idx}>
                <div style={{
                  backgroundColor: 'var(--bg-primary)',
                  border: `1px solid var(--border-color)`,
                  borderLeft: `3px solid ${node.color}`,
                  borderRadius: '6px',
                  padding: '0.6rem 0.85rem',
                  width: '140px',
                  flexShrink: 0
                }}>
                  <span style={{ fontSize: '0.6rem', color: node.color, fontWeight: 700, textTransform: 'uppercase', display: 'block' }}>{node.label}</span>
                  <strong style={{ fontSize: '0.7rem', color: '#ffffff', fontFamily: 'monospace', display: 'block', marginTop: '0.15rem', wordBreak: 'break-all' }}>{node.desc}</strong>
                </div>
                {idx < bindingNodes.length - 1 && (
                  <ArrowRight size={14} style={{ color: 'var(--color-text-muted)', opacity: 0.5, flexShrink: 0 }} />
                )}
              </Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* Audit Chain Metadata Table */}
      <div className="data-panel" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="data-panel-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.95rem' }}>
          🛡️ HSW-ST 审计溯源存证单 ( Heuristic Watermark Cryptographic Bill )
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>辅导话术唯一标号 (Answer ID):</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.answer_id || `ans_${logs.c2_rag?.chunk_id ? 'task_0001' : 'task_0001'}`}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>嵌入隐形水印 ID (Watermark ID):</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.watermark_id || 'hsw_st_minimal_id'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>画像卡凭证哈希 (Profile Card ID):</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{`card_${audit.profile_card_id ? audit.profile_card_id.replace('card_', '') : 'task_0001'}`}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>关联版权教案 ID (Resource ID):</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{logs.c2_rag?.resource_id || 'teacher_resource_arithmetic_sequence'}</strong>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>课件匹配分块 ID (Resource Chunk ID):</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{logs.c2_rag?.chunk_id || 'chunk_889e1f6f'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>审计数字签名 (SHA256 watermark signature):</span>
              <strong style={{ color: 'var(--color-green)', fontFamily: 'monospace', fontSize: '0.65rem', wordBreak: 'break-all', textAlign: 'right', maxWidth: '12rem' }}>
                {audit.watermarked_answer_sha256 || "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>链路存证评级 (Audit status):</span>
              <span className="risk-badge low" style={{ fontSize: '0.65rem' }}>{audit.audit_complete ? 'VERIFIED_CHAIN_SECURE' : 'PENDING'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>系统物理审计状态:</span>
              <strong style={{ color: 'var(--color-green)' }}>{audit.audit_complete ? '完备 / Complete (已封印)' : '等待流转...'}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Summary telemetry */}
      <div className="summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>物理智能体接入次数 (Agent Calls)</span>
          <strong style={{ fontSize: '1rem', color: '#ffffff' }}>4 Dispatches (受控调用)</strong>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>审计中介通信报文 (Comms Logs)</span>
          <strong style={{ fontSize: '1rem', color: '#ffffff' }}>{data?.communication_logs?.length || 0} handshakes (TPCS 审计)</strong>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>长期画像写库决策 (Profile Update)</span>
          <strong style={{ fontSize: '1rem', color: 'var(--color-red)' }}>{data?.profile_update_decision === 'approve' ? 'Allowed' : 'Gated Denied (已拦截审计)'}</strong>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>绑定资源实体 (Resource Bindings)</span>
          <strong style={{ fontSize: '1rem', color: 'var(--color-purple)' }}>1 chunk (C²-RAG)</strong>
        </div>
      </div>
    </section>
  );
}
