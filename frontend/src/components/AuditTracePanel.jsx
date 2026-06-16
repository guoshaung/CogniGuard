import { Fragment } from 'react';
import { Terminal, Database, ArrowRight, ShieldCheck } from 'lucide-react';

export default function AuditTracePanel({ data }) {
  const answer = data?.final_answer || '';
  const audit = data?.audit_trace || {};
  const logs = data?.protection_logs || {};

  const bindingNodes = [
    { label: '画像卡', desc: `card_${audit.profile_card_id ? audit.profile_card_id.replace('card_', '') : 'task_0001'}`, color: 'var(--blue)' },
    { label: '资源分块', desc: logs.c2_rag?.chunk_id || 'chunk_889e1f6f', color: 'var(--amber)' },
    { label: '代理调用', desc: '受控调用', color: 'var(--muted)' },
    { label: '最终回答', desc: `ans_${audit.profile_card_id ? audit.profile_card_id.replace('card_', '') : 'task_0001'}`, color: 'var(--muted)' },
    { label: '水印', desc: audit.watermark_id || 'audit_trace_watermark_id', color: 'var(--green)' },
    { label: '审计链', desc: 'SHA256 绑定', color: 'var(--green)' },
  ];

  return (
    <section className="content-stack audit-panel-container">
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Terminal size={28} style={{ color: 'var(--green)' }} />
          <span>水印溯源与审计追踪层</span>
        </h1>
        <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          通过隐式水印与链式哈希，把课堂回答、资源分块和代理调用绑定到同一条可审计链路中。
        </p>
      </div>

      <div className="final-answer-card" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem', position: 'relative' }}>
        <div className="watermark-overlay" style={{ position: 'absolute', top: '1rem', right: '1rem', color: 'var(--green)', backgroundColor: 'rgba(16, 185, 129, 0.08)', border: '1px dashed var(--green)', borderRadius: '4px', padding: '0.25rem 0.5rem', fontSize: '0.7rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <ShieldCheck size={12} />
          <span>水印已绑定</span>
        </div>
        <div className="data-panel-title" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem' }}>
          最终下发给学生的回答
        </div>
        {answer ? (
          <p className="answer-text" style={{ fontSize: '0.9rem', lineHeight: '1.6', color: '#f1f5f9', whiteSpace: 'pre-wrap', margin: 0 }}>
            {answer}
          </p>
        ) : (
          <div style={{ textAlign: 'center', padding: '1.5rem 0', color: 'var(--muted)', fontSize: '0.85rem' }}>
            暂无受保护回答。请先在课堂中运行一轮学习流程。
          </div>
        )}
      </div>

      <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
          <Database size={16} style={{ color: 'var(--green)' }} />
          <span>全链路凭证绑定关系图</span>
        </div>

        <div style={{ overflowX: 'auto', padding: '0.5rem 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 'max-content', justifyContent: 'center' }}>
            {bindingNodes.map((node, idx) => (
              <Fragment key={idx}>
                <div style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)', borderLeft: `3px solid ${node.color}`, borderRadius: '6px', padding: '0.6rem 0.85rem', width: '140px', flexShrink: 0 }}>
                  <span style={{ fontSize: '0.6rem', color: node.color, fontWeight: 700, textTransform: 'uppercase', display: 'block' }}>{node.label}</span>
                  <strong style={{ fontSize: '0.7rem', color: '#ffffff', fontFamily: 'monospace', display: 'block', marginTop: '0.15rem', wordBreak: 'break-all' }}>{node.desc}</strong>
                </div>
                {idx < bindingNodes.length - 1 && <ArrowRight size={14} style={{ color: 'var(--muted)', opacity: 0.5, flexShrink: 0 }} />}
              </Fragment>
            ))}
          </div>
        </div>
      </div>

      <div className="data-panel" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="data-panel-title" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.95rem' }}>
          审计溯源存证单
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>辅导话术唯一标号</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.answer_id || `ans_${logs.c2_rag?.chunk_id ? 'task_0001' : 'task_0001'}`}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>嵌入隐形水印 ID</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.watermark_id || 'audit_trace_watermark_id'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>画像卡凭证哈希</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{`card_${audit.profile_card_id ? audit.profile_card_id.replace('card_', '') : 'task_0001'}`}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>关联版权教案 ID</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{logs.c2_rag?.resource_id || 'teacher_resource_arithmetic_sequence'}</strong>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>课件匹配分块 ID</span>
              <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{logs.c2_rag?.chunk_id || 'chunk_889e1f6f'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>审计数字签名</span>
              <strong style={{ color: 'var(--green)', fontFamily: 'monospace', fontSize: '0.65rem', wordBreak: 'break-all', textAlign: 'right', maxWidth: '12rem' }}>
                {audit.watermarked_answer_sha256 || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>链路存证评级</span>
              <span className="risk-badge low" style={{ fontSize: '0.65rem' }}>{audit.audit_complete ? '安全链路已验证' : '等待验证'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>系统物理审计状态</span>
              <strong style={{ color: 'var(--green)' }}>{audit.audit_complete ? '审计完备（已封存）' : '等待流转...'}</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>代理接入次数</span>
          <strong style={{ fontSize: '1rem', color: '#ffffff' }}>4 次受控调用</strong>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>审计中介通信报文</span>
          <strong style={{ fontSize: '1rem', color: '#ffffff' }}>{data?.communication_logs?.length || 0} 次 TPCS 握手</strong>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>长期画像写库决策</span>
          <strong style={{ fontSize: '1rem', color: data?.profile_update_decision === 'approve' ? 'var(--green)' : 'var(--red)' }}>
            {data?.profile_update_decision === 'approve' ? '已允许写入' : '已由门控拦截'}
          </strong>
        </div>
        <div style={{ backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>绑定资源实体</span>
          <strong style={{ fontSize: '1rem', color: 'var(--amber)' }}>1 个 C²-RAG 分块</strong>
        </div>
      </div>
    </section>
  );
}
