import { Scale, ShieldCheck } from 'lucide-react';

const shortList = (items = []) => {
  if (!items.length) return '-';
  return items.slice(0, 6).join(', ');
};

export default function ComplianceGovernancePanel({ pipelineData }) {
  const state = pipelineData?.compliance_state || pipelineData?.protection_logs?.tpcs?.compliance_state || {};
  const policy = pipelineData?.compliance_policy || pipelineData?.protection_logs?.tpcs?.compliance_policy || {};
  const events = pipelineData?.compliance_audit_log || pipelineData?.protection_logs?.tpcs?.compliance_audit_log || [];

  return (
    <section className="compliance-panel">
      <header className="compliance-panel-header">
        <span><Scale size={15} /> Compliance Governance</span>
        <strong>TPCS policy source</strong>
      </header>
      <p className="compliance-panel-note">
        FERPA/COPPA 合规治理不是第四个主创新机制，而是 TPCS 的横向策略约束，用于决定学生数据能否披露、能否进入第三方模型、保存多久以及如何审计。
      </p>
      <div className="compliance-grid">
        <div><span>FERPA applicable</span><strong>{String(state.ferpa_applicable ?? false)}</strong></div>
        <div><span>COPPA applicable</span><strong>{String(state.coppa_applicable ?? false)}</strong></div>
        <div><span>parental_consent</span><strong>{state.parental_consent || '-'}</strong></div>
        <div><span>school_authorization</span><strong>{state.school_authorization || '-'}</strong></div>
        <div><span>third_party_model_use_allowed</span><strong>{String(state.third_party_model_use_allowed ?? false)}</strong></div>
        <div><span>retention_action</span><strong>{policy.retention_action || '-'}</strong></div>
      </div>
      <div className="compliance-policy-grid">
        <article>
          <span>blocked_fields</span>
          <p>{shortList(policy.blocked_fields)}</p>
        </article>
        <article>
          <span>allowed_fields</span>
          <p>{shortList(policy.allowed_fields)}</p>
        </article>
        <article>
          <span>third_party_model_policy</span>
          <p>{policy.third_party_model_policy || '-'}</p>
        </article>
      </div>
      <div className="compliance-events">
        <span><ShieldCheck size={14} /> recent compliance audit events</span>
        {(events.length ? events.slice(-5) : []).map((event) => (
          <div key={event.event_id || event.audit_hash}>
            <strong>{event.event_type}</strong>
            <em>{event.legal_context} / {event.decision}</em>
            <code>{String(event.audit_hash || '').slice(0, 16)}</code>
          </div>
        ))}
        {!events.length && <p>No compliance audit events yet.</p>}
      </div>
    </section>
  );
}
