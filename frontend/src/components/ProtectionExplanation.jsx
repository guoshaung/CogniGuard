import { EyeOff, ShieldAlert, FileText, Lock, HelpCircle, Terminal } from 'lucide-react';

export default function ProtectionExplanation({ step, pipelineData }) {
  if (!step) {
    return (
      <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
        <HelpCircle size={30} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
        <span>No step active. Select a step to view active protection policy explanation.</span>
      </div>
    );
  }

  const layer = String(step.layer || '').toLowerCase();
  const name = String(step.step_name || '').toLowerCase();

  // Helper safe fetch
  const getFopdDetails = () => ({
    visible: ['knowledge_point', 'current_error_type', 'suggested_teaching_strategy'],
    blocked: ['raw screenshot screenshot.png', 'audio acoustic coordinates', 'handwriting pressure trace', 'expression micro-signals', 'full historic student profile']
  });

  const getC2RagDetails = () => {
    const c2ragLog = pipelineData?.protection_logs?.c2_rag || {};
    return {
      resource_id: c2ragLog?.resource_id || 'teacher_resource_arithmetic_sequence',
      chunk_id: c2ragLog?.chunk_id || 'chunk_889e1f6f',
      copyright_level: c2ragLog?.copyright_level || 'level_high',
      exposure_budget_before: c2ragLog?.exposure_budget_before ?? 0.85,
      exposure_cost: c2ragLog?.exposure_cost ?? 0.14,
      exposure_budget_after: c2ragLog?.exposure_budget_after ?? 0.71,
      return_mode: c2ragLog?.return_mode || 'variant_question'
    };
  };

  const getAuditDetails = () => ({
    answer_id: pipelineData?.audit_trace?.answer_id || `ans_${pipelineData?.generated_context_card?.task_id || 'task_0001'}`,
    watermark_id: pipelineData?.audit_trace?.watermark_id || 'audit_trace_watermark_id',
    profile_card_id: pipelineData?.audit_trace?.profile_card_id || `card_${pipelineData?.generated_context_card?.task_id || 'task_0001'}`,
    resource_ids: [pipelineData?.protection_logs?.c2_rag?.resource_id || 'teacher_resource_arithmetic_sequence'],
    chunk_ids: [pipelineData?.protection_logs?.c2_rag?.chunk_id || 'chunk_889e1f6f'],
    audit_complete: pipelineData?.audit_trace?.audit_complete ? '✅ Complete (签名链完备)' : '❌ Pending'
  });

  // Render logic depending on layer & name
  if (layer.includes('mm-fopd')) {
    const fopd = getFopdDetails();
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <EyeOff size={16} style={{ color: 'var(--color-blue)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>What MM-FOPD Protected</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>用户侧隐私物理隔离机制：</strong> 学生高精度截图、手写轨迹、声纹等物理隐私在本地解析为教育语义后被强行截断，不允许被发送到下游的云端大模型智能体中。
        </p>
        <div style={{ fontSize: '0.7rem' }}>
          <span style={{ color: 'var(--color-green)', fontWeight: 'bold', display: 'block', marginBottom: '0.2rem' }}>✔️ Released (可见字段):</span>
          <ul style={{ paddingLeft: '1rem', margin: 0, color: 'var(--color-text-muted)' }}>
            {fopd.visible.map(f => <li key={f}>{f}</li>)}
          </ul>
        </div>
        <div style={{ fontSize: '0.7rem' }}>
          <span style={{ color: 'var(--color-red)', fontWeight: 'bold', display: 'block', marginBottom: '0.2rem' }}>❌ Blocked (物理隔离字段):</span>
          <ul style={{ paddingLeft: '1rem', margin: 0, color: 'var(--color-text-muted)' }}>
            {fopd.blocked.map(f => <li key={f}>{f}</li>)}
          </ul>
        </div>
      </div>
    );
  }

  if (layer.includes('tpcs') && !name.includes('update')) {
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Lock size={16} style={{ color: 'var(--color-yellow)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>What TPCS checked</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>横向准入前置路由审计：</strong> TPCS 控制器核算当前智能体发送消息的准入凭证，拦截未经授权的越权传输。
        </p>
        <div style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: 'var(--color-text-muted)' }}>
          <div>🛡️ Pre-Check Result: <strong style={{ color: 'var(--color-green)' }}>{step.tpcs_decision}</strong></div>
          <div>📈 Ingest Risk Score: <strong>{Number(step.risk_score ?? 0).toFixed(2)}</strong></div>
          <div>⛓️ Comms rule: <strong>Restricts direct connection between execute nodes.</strong></div>
        </div>
      </div>
    );
  }

  if (layer.includes('nemo')) {
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <ShieldAlert size={16} style={{ color: 'var(--color-red)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>What NeMo Guardrails checked</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>物理护栏级防御拦截：</strong> 装载输入、检索或输出防护围栏，防止提示词注入、敏感榨取或越权输出。
        </p>
        <div style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: 'var(--color-text-muted)' }}>
          <div>🛡️ NeMo decision: <strong style={{ color: 'var(--color-yellow)' }}>{step.nemo_decision || 'PASSED'}</strong></div>
          <div>📌 Verification scope: <strong>Input Rail / Retrieval Rail / Output Rail</strong></div>
          <div>🚨 Threat state: <strong>Passed safety checking with zero sanitizations.</strong></div>
        </div>
      </div>
    );
  }

  if (name.includes('diagnosis')) {
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <FileText size={16} style={{ color: 'var(--color-text-muted)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Agent Input/Output Boundary</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>诊断智能体（ProfileDiagnosisAgent）：</strong> 仅被允许接入由 MM-FOPD 重构之后的**脱敏画像卡片**。
        </p>
        <p style={{ fontSize: '0.7rem', color: 'var(--color-yellow)', margin: 0 }}>
          ⚠️ 诊断智能体物理上无法获取学生的真实声纹、物理坐标和历史学情，最大程度防止底层执行大模型节点泄露学生隐私。
        </p>
      </div>
    );
  }

  if (name.includes('resource') || layer.includes('c2-rag')) {
    const c2 = getC2RagDetails();
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Lock size={16} style={{ color: 'var(--color-purple)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Copyright Control (C²-RAG)</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>检索版权开销动态衰减机制：</strong> 教师讲义不允许被 verbatim (逐字原文) 流出。C²-RAG 动态根据版权级别、出库压力以及预算扣减出库版权资源。
        </p>
        <div style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: 'var(--color-text-muted)' }}>
          <div>📄 Resource ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{c2.resource_id}</strong></div>
          <div>🧩 Chunk ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{c2.chunk_id}</strong></div>
          <div>📌 Copyright level: <span className="risk-badge med" style={{ fontSize: '0.65rem' }}>{c2.copyright_level}</span></div>
          <div>📉 Budget Before: <strong style={{ color: 'var(--color-green)' }}>{c2.exposure_budget_before}</strong></div>
          <div>💸 Exposure Cost: <strong style={{ color: 'var(--color-red)' }}>{c2.exposure_cost}</strong></div>
          <div>📈 Budget After: <strong style={{ color: 'var(--color-yellow)' }}>{c2.exposure_budget_after}</strong></div>
          <div>🔄 Output Mode: <span className="risk-badge low" style={{ fontSize: '0.65rem', textTransform: 'uppercase' }}>{c2.return_mode}</span></div>
        </div>
      </div>
    );
  }

  if (name.includes('teaching') || name.includes('pedagogical')) {
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <FileText size={16} style={{ color: 'var(--color-text-muted)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Protected Teaching Generation</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>授课智能体（PedagogicalTeachingAgent）：</strong> 根据脱敏画像卡片及 C²-RAG 脱敏后的教案片段，组合生成可用的教学辅导话术。
        </p>
        <p style={{ fontSize: '0.7rem', color: 'var(--color-green)', margin: 0 }}>
          ✔️ 物理沙盒隔离：授课智能体永远不可能直接调用受产权保护的原版付费教案，也无法接触到原始隐私画像，从根本上杜绝越权风险。
        </p>
      </div>
    );
  }

  if (name.includes('assessment') && !layer.includes('tpcs')) {
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <FileText size={16} style={{ color: 'var(--color-text-muted)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Evidence-Gated Assessment</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>评估智能体（LearningAssessmentAgent）：</strong> 抓取错题辅导响应后，将学情 Mastery 变化抽象为“写库凭证（Profile Evidence）”。
        </p>
        <p style={{ fontSize: '0.7rem', color: 'var(--color-yellow)', margin: 0 }}>
          ⚠️ 物理隔离机制：该智能体无权直接对长期学情数据库进行修改，写库凭证必须提交给 TPCS 控制器进行二次核算，防止学生谎报自诉污染库表。
        </p>
      </div>
    );
  }

  if (layer.includes('tpcs') && name.includes('update')) {
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Lock size={16} style={{ color: 'var(--color-yellow)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Evidence-Gated Update (TPCS)</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>长期画像写库准入审查：</strong> TPCS 控制器对评估智能体递交的自诉画像更新数据进行严格校验，拒绝将高危学情指标（如谎报 mastery=100% 等污染动作）直接写入长期数据库中。
        </p>
        <div style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: 'var(--color-text-muted)' }}>
          <div>🛡️ Writing Permit: <strong style={{ color: 'var(--color-red)' }}>{pipelineData?.profile_update_decision || 'denied (隔离存证审查)'}</strong></div>
          <div>🧬 Review state: <strong>Logged for secondary supervisor audit. Direct writing BLOCKED.</strong></div>
        </div>
      </div>
    );
  }

  if (layer.includes('hsw-st') || name.includes('hsw') || name.includes('watermark') || name.includes('audit')) {
    const audit = getAuditDetails();
    return (
      <div className="explanation-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Terminal size={16} style={{ color: 'var(--color-green)' }} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Audit and Watermark Binding</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
          <strong>最终输出隐形水印嵌入与全链路可追溯审计：</strong> 在最终下发的辅导话术中嵌入隐形高抗篡改性软水印，并将该会话流转关联的画像 ID、版权 ID 绑定生成不可伪造的加密哈希，以便将来实施侵权或泄露追踪。
        </p>
        <div style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: 'var(--color-text-muted)' }}>
          <div>📄 Answer ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.answer_id}</strong></div>
          <div>🛡️ Watermark ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.watermark_id}</strong></div>
          <div>👤 Card ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.profile_card_id}</strong></div>
          <div>📚 Resource ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.resource_ids.join(', ')}</strong></div>
          <div>🧩 Chunk ID: <strong style={{ color: '#ffffff', fontFamily: 'monospace' }}>{audit.chunk_ids.join(', ')}</strong></div>
          <div>⚙️ Audit complete: <strong style={{ color: 'var(--color-green)' }}>{audit.audit_complete}</strong></div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '1rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
      No specific explanation mapped for: {step.step_name}.
    </div>
  );
}
