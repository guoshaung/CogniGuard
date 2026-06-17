import { ArrowRight, Database, Fingerprint, Link2, ShieldCheck, Terminal } from 'lucide-react';
import AcademicFigurePanel from './AcademicFigurePanel';
import WatermarkDetectorPanel from './WatermarkDetectorPanel';
import WatermarkRoundAccordion from './WatermarkRoundAccordion';

const placeholderRecord = {
  answer_id: 'ans_waiting_for_classroom_round',
  session_id: 'sess_pending',
  round_id: '-',
  profile_card_id: 'card_hash_pending',
  resource_trace: [
    {
      resource_id: 'res_pending',
      chunk_id: 'chunk_pending',
      return_mode: 'summary',
      exposure_score: 0,
    },
  ],
  risk_state: 'pending',
  policy_decision: 'pending',
  previous_audit_hash: 'GENESIS',
  timestamp_bucket: 'pending',
};

const fieldLine = (label, value) => (
  <div className="audit-field-line" key={label}>
    <span>{label}</span>
    <strong>{value ?? '-'}</strong>
  </div>
);

export default function AuditTracePanel({ data }) {
  const answer = data?.final_answer || '';
  const audit = data?.audit_trace || {};
  const hsw = data?.protection_logs?.hsw_st || {};
  const c2rag = data?.protection_logs?.c2_rag || {};
  const record = audit.audit_record || placeholderRecord;
  const semantic = audit.semantic_watermark || hsw.semantic_watermark || {};
  const verification = audit.verification_preview || hsw.verification_preview || {};
  const seedCommitments = audit.sub_seed_commitments || {};
  const sessionId = audit.audit_record?.session_id || '';

  const bindingNodes = [
    { label: '审计记录', desc: record.answer_id, color: 'var(--blue)' },
    { label: '规范化 JSON', desc: audit.canonical_audit_record ? 'sort_keys + stable separators' : '待生成', color: 'var(--muted)' },
    { label: '审计摘要', desc: audit.audit_digest ? `${audit.audit_digest.slice(0, 14)}...` : 'SHA256 pending', color: 'var(--amber)' },
    { label: '隐藏 Seed', desc: audit.watermark_seed_commitment || 'HMAC pending', color: 'var(--green)' },
    { label: '多轮绑定', desc: audit.multi_round_binding?.round_seed || 'round seed pending', color: 'var(--green)' },
  ];

  return (
    <section className="content-stack audit-panel-container">
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Terminal size={28} style={{ color: 'var(--green)' }} />
          <span>大模型生成内容审计追踪机制：HSW-ST 水印、来源追踪与可信审计</span>
        </h1>
        <p style={{ color: 'var(--muted)', fontSize: '0.92rem', marginTop: '0.25rem' }}>
          当前水印升级为“语义感知 + 证据链绑定 + 多轮鲁棒水印机制”：先生成审计证据字段，再规范化哈希并派生隐藏 seed，最后只在语义等价表达空间中施加水印。
        </p>
      </div>

      <WatermarkDetectorPanel
        defaultText={answer}
        auditTrace={audit}
        sessionId={sessionId}
      />

      <WatermarkRoundAccordion sessionId={sessionId} />

      <div className="final-answer-card glass-panel" style={{ position: 'relative' }}>
        <div className="watermark-overlay" style={{ position: 'absolute', top: '1rem', right: '1rem', color: 'var(--green)', backgroundColor: 'rgba(16, 185, 129, 0.08)', border: '1px dashed var(--green)', borderRadius: '999px', padding: '0.35rem 0.65rem', fontSize: '0.72rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <ShieldCheck size={13} />
          <span>{audit.watermark_scheme || 'semantic_evidence_chain_multiround'}</span>
        </div>
        <div className="data-panel-title">最终下发给学生的回答</div>
        {answer ? (
          <p className="answer-text" style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
        ) : (
          <div className="empty-hint">暂无受保护回答。请先在“闭环案例演示”中运行至少一轮学习流程。</div>
        )}
      </div>

      <div className="data-panel-card glass-panel">
        <div className="data-panel-title"><Link2 size={16} /> 六步证据链绑定路径</div>
        <div style={{ overflowX: 'auto', padding: '0.6rem 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 'max-content' }}>
            {bindingNodes.map((node, idx) => (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }} key={node.label}>
                <div style={{ backgroundColor: 'rgba(4, 16, 28, 0.62)', border: '1px solid var(--border)', borderLeft: `3px solid ${node.color}`, borderRadius: '12px', padding: '0.75rem 0.9rem', width: '170px' }}>
                  <span style={{ fontSize: '0.68rem', color: node.color, fontWeight: 800 }}>{node.label}</span>
                  <strong style={{ display: 'block', marginTop: '0.2rem', fontSize: '0.72rem', wordBreak: 'break-all' }}>{node.desc}</strong>
                </div>
                {idx < bindingNodes.length - 1 && <ArrowRight size={15} style={{ color: 'var(--muted)' }} />}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="data-panel glass-panel">
        <div className="data-panel-title"><Database size={16} /> Step 1-3：审计记录、规范化与隐藏 Seed</div>
        <div className="audit-two-column">
          <div>
            {fieldLine('answer_id', record.answer_id)}
            {fieldLine('session_id', record.session_id)}
            {fieldLine('round_id', record.round_id)}
            {fieldLine('profile_card_id', record.profile_card_id)}
            {fieldLine('risk_state', record.risk_state)}
            {fieldLine('policy_decision', record.policy_decision)}
            {fieldLine('previous_audit_hash', record.previous_audit_hash)}
            {fieldLine('timestamp_bucket', record.timestamp_bucket)}
          </div>
          <div>
            {fieldLine('resource_id', record.resource_trace?.[0]?.resource_id || c2rag.resource_id)}
            {fieldLine('chunk_id', record.resource_trace?.[0]?.chunk_id || c2rag.chunk_id)}
            {fieldLine('return_mode', record.resource_trace?.[0]?.return_mode || c2rag.return_mode)}
            {fieldLine('audit_digest', audit.audit_digest ? `${audit.audit_digest.slice(0, 28)}...` : '-')}
            {fieldLine('seed_commitment', audit.watermark_seed_commitment)}
            {Object.entries(seedCommitments).map(([key, value]) => fieldLine(key, value))}
          </div>
        </div>
        <pre className="audit-json-block">{audit.canonical_audit_record || JSON.stringify(record, null, 2)}</pre>
      </div>

      <div className="summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div className="glass-panel">
          <div className="data-panel-title"><Fingerprint size={16} /> Step 4：语义感知水印</div>
          <p className="audit-mini-copy">锁定公式、数字、单位、专有名词、知识点、关键步骤和来源 ID，只在连接词、语气、句式、例子和段落组织中选择等价表达。</p>
          {(semantic.variant_choices || []).map((item) => fieldLine(item.channel, item.choice))}
        </div>

        <div className="glass-panel">
          <div className="data-panel-title"><Link2 size={16} /> Step 5：多轮鲁棒绑定</div>
          {fieldLine('session_seed', audit.multi_round_binding?.session_seed)}
          {fieldLine('round_seed', audit.multi_round_binding?.round_seed)}
          {fieldLine('resource_seed', audit.multi_round_binding?.resource_seed)}
          {fieldLine('audit_seed', audit.multi_round_binding?.audit_seed)}
        </div>

        <div className="glass-panel">
          <div className="data-panel-title"><ShieldCheck size={16} /> Step 6：检测与验证</div>
          {fieldLine('watermark_detected', String(verification.watermark_detected ?? false))}
          {fieldLine('confidence', verification.confidence ?? '-')}
          {fieldLine('matched_round_id', verification.matched_round_id ?? '-')}
          {fieldLine('matched_resource_id', verification.matched_resource_id ?? '-')}
          {fieldLine('audit_chain_valid', String(verification.audit_chain_valid ?? false))}
          {fieldLine('tamper_suspicion', String(verification.tamper_suspicion ?? false))}
        </div>
      </div>

      <AcademicFigurePanel
        data={data}
        figures={['evidence_pipeline', 'audit_chain', 'seed_binding', 'watermark_attack_robustness']}
      />
    </section>
  );
}
