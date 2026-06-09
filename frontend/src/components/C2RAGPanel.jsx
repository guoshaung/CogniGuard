import React from 'react';
import { BookOpen, Lock, ShieldCheck, AlertTriangle } from 'lucide-react';

export default function C2RAGPanel({ data }) {
  const c2 = data?.c2_rag_log || {};
  const agent = data?.copyright_agent || {};
  const snippets = data?.snippets || [];

  return (
    <section className="content-stack c2rag-panel-container">
      {/* Title block */}
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <BookOpen size={28} style={{ color: 'var(--color-purple)' }} />
          <span>C²-RAG Teacher Copyright Resource Protection (检索版权安全层)</span>
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Teacher learning materials are retrieval-sanitized and gated by session budgets to prevent verbatim leakage under multi-round adversarial chat extraction attacks.
        </p>
      </div>

      {/* Grid structure */}
      <div className="three-column-grid" style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1.3fr', gap: '1.5rem', marginBottom: '2rem' }}>
        
        {/* Column 1: Request Details */}
        <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="data-panel-title" style={{ color: 'var(--color-purple)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem' }}>
            📥 Teaching Resource Request
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.75rem' }}>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>检索关键词 (Knowledge point):</span>
              <div style={{ color: '#ffffff', marginTop: '0.15rem', fontWeight: 'bold' }}>{c2.knowledge_point || "arithmetic sequence"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>检索要求 (Requested Support):</span>
              <div style={{ color: '#cbd5e1', marginTop: '0.15rem' }}>{agent.controlled_resource_snippets?.[0]?.title || "Generate sequence exercises tailored to diagnosis"}</div>
            </div>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: '6px', padding: '0.5rem' }}>
              <span className="percent-label" style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>系统指令安全级 (Instruction Privacy level):</span>
              <div style={{ color: '#cbd5e1', marginTop: '0.15rem' }}>{c2.copyright_level === 'level_high' ? 'High Security / 限制大篇幅引述' : 'Standard'}</div>
            </div>
          </div>
        </div>

        {/* Column 2: Copyright Control */}
        <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="data-panel-title" style={{ color: 'var(--color-purple)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem' }}>
            🛡️ Copyright Control Budget
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>Copyright Rank (资源版权级):</span>
              <span className="risk-badge med" style={{ fontSize: '0.65rem', textTransform: 'uppercase' }}>{c2.copyright_level || "level_high"}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>Exposure Budget Before:</span>
              <span style={{ color: 'var(--color-green)', fontWeight: 'bold' }}>{c2.exposure_budget_before ?? 0.85}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>Round Exposure Cost:</span>
              <span style={{ color: 'var(--color-red)', fontWeight: 'bold' }}>{c2.exposure_cost ?? 0.14}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>Exposure Budget After:</span>
              <span style={{ color: 'var(--color-yellow)', fontWeight: 'bold' }}>{c2.exposure_budget_after ?? 0.71}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>Sanitization Mode:</span>
              <span className="risk-badge low" style={{ fontSize: '0.65rem', textTransform: 'uppercase' }}>{c2.return_mode || "variant_question"}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '0.25rem' }}>
              <span>Injection Scanner:</span>
              <span style={{ color: 'var(--color-green)' }}>SAFE (0 prompt hacks detected)</span>
            </div>
          </div>
        </div>

        {/* Column 3: Controlled Snippet */}
        <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="data-panel-title" style={{ color: 'var(--color-purple)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.9rem' }}>
            📄 Controlled Resource Snippet
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '0.5rem' }}>
            ✔️ <em>Sanitized output snippet returned by copyright governor.</em>
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
              <span>Resource ID:</span>
              <span style={{ fontFamily: 'monospace' }}>{c2.resource_id || 'teacher_resource_arithmetic_sequence'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
              <span>Retrieved Chunk ID:</span>
              <span style={{ fontFamily: 'monospace' }}>{c2.chunk_id || 'chunk_889e1f6f'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
              <span>Full original text returned:</span>
              <strong style={{ color: 'var(--color-red)' }}>FALSE (已物理拦截)</strong>
            </div>

            <div style={{ marginTop: '0.25rem' }}>
              <span className="percent-label" style={{ fontSize: '0.65rem', display: 'block', marginBottom: '0.15rem' }}>脱敏处理片段 (Controlled Output Text):</span>
              <div style={{
                backgroundColor: 'rgba(0, 0, 0, 0.2)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '0.5rem',
                fontSize: '0.7rem',
                maxHeight: '85px',
                overflowY: 'auto',
                fontStyle: 'italic',
                color: 'var(--color-text-muted)',
                lineHeight: '1.4'
              }}>
                {snippets?.[0]?.content || snippets?.[0]?.variant_text || "The teaching agent requested arithmetic sequence teaching guides. C²-RAG exposure control determined this text contains high-level copyrighted exercises. The text is obfuscated into sequence definitions and dynamic variant exercises to prevent direct memorization leaks."}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom explanation */}
      <div className="fopd-shield-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem', backgroundColor: 'rgba(139, 92, 246, 0.04)', border: '1px solid var(--color-purple)', borderRadius: '12px', padding: '1rem 1.25rem' }}>
        <ShieldCheck size={32} style={{ color: 'var(--color-purple)', flexShrink: 0 }} />
        <div>
          <h4 style={{ margin: '0 0 0.15rem 0', color: '#ffffff', fontSize: '0.9rem' }}>C²-RAG 课件库安全机制说明 (C²-RAG Budget Mediation Principle)</h4>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
            <strong>课件资产版权红线：</strong> 教师付费教案、教材原文不得向辅导智能体提供大段 Verbatim (原文逐字) 出库。C²-RAG 会根据计算所得的单轮开销 (Exposure Cost)，将出库模式实时降级衰减。仅根据预算阈值返回**概要摘要 (summary)**、**教学大纲 (outline)**、**短句引用 (short quote)**、**等效变体题 (variant question)** 或直接**拦截熔断 (refusal)**，最大程度防止黑客通过会话将名师课件库原文全部套出。
          </p>
        </div>
      </div>
    </section>
  );
}
