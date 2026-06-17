import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BookOpen, Database, FileText, ShieldCheck } from 'lucide-react';
import AcademicFigurePanel from './AcademicFigurePanel';

const DEMO_METADATA = {
  source_type: 'institutional_database',
  license_type: 'educational_license',
};

const formatValue = (value, fallback = '-') => {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'number') return Number.isInteger(value) ? value : value.toFixed(3);
  return String(value);
};

const buildDemoTraceId = (record, index) => (
  record.source_trace_id
  || `trace_demo_${record.resource_id || record.chunk_id || String(index + 1).padStart(3, '0')}`
);

export default function C2RAGPanel({ caseIndex = 0, pipelineData }) {
  const [cases, setCases] = useState([]);
  const [attacks, setAttacks] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    const loadCopyrightData = async () => {
      setLoading(true);
      setError('');
      try {
        const [caseResponse, attackResponse] = await Promise.all([
          fetch(`/api/c2-rag/cases?index=${caseIndex}&_=${Date.now()}`, { cache: 'no-store' }),
          fetch(`/api/c2rag-attacks?_=${Date.now()}`, { cache: 'no-store' }),
        ]);
        if (!caseResponse.ok) throw new Error(`/api/c2-rag/cases 返回 HTTP ${caseResponse.status}`);
        const casePayload = await caseResponse.json();
        const attackPayload = attackResponse.ok ? await attackResponse.json() : null;
        if (!alive) return;
        setCases(casePayload.cases || []);
        setAttacks(attackPayload);
        setSelectedIndex(0);
      } catch (caughtError) {
        if (alive) setError(caughtError.message);
      } finally {
        if (alive) setLoading(false);
      }
    };

    loadCopyrightData();
    return () => {
      alive = false;
    };
  }, [caseIndex]);

  const selectedCase = cases[selectedIndex] || {};
  const pipelineC2Rag = pipelineData?.protection_logs?.c2_rag || {};
  const record = useMemo(() => {
    const merged = { ...selectedCase, ...pipelineC2Rag };
    const hasDemoMetadata = !merged.source_type || !merged.license_type || !merged.source_trace_id;
    return {
      ...merged,
      source_type: merged.source_type || DEMO_METADATA.source_type,
      license_type: merged.license_type || DEMO_METADATA.license_type,
      source_trace_id: buildDemoTraceId(merged, selectedIndex),
      demo_metadata: hasDemoMetadata,
    };
  }, [pipelineC2Rag, selectedCase, selectedIndex]);

  const fieldRows = [
    ['resource_id', '资源 ID'],
    ['chunk_id', '检索分块 ID'],
    ['source_type', '来源类型'],
    ['license_type', '授权类型'],
    ['copyright_level', '版权等级'],
    ['exposure_budget_before', '披露预算：前'],
    ['exposure_cost', '本轮披露成本'],
    ['exposure_budget_after', '披露预算：后'],
    ['return_mode', '返回模式'],
    ['reconstruction_risk', '重构风险'],
    ['source_trace_id', '来源追踪 ID'],
  ];

  const attackSummary = attacks?.summary || {};
  const attackRows = attacks?.rows || [];

  return (
    <section className="content-stack c2rag-panel-container">
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <BookOpen size={28} style={{ color: 'var(--color-purple, #a78bfa)' }} />
          <span>教师版权保护子机制：C²-RAG 版权约束检索与反重构控制</span>
        </h1>
        <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          对教师资源、学校购买数据库、出版社资料库、开放教育资源和 AI 衍生教学内容进行受控检索、披露预算扣减、返回模式降级与反重构审计。
        </p>
      </div>

      {error && (
        <div className="error-banner" style={{ marginBottom: '1rem' }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="three-column-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 0.8fr) minmax(320px, 1.2fr) minmax(280px, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
        <aside className="data-panel-card" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1rem' }}>
          <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.85rem', fontWeight: 800 }}>
            <Database size={16} style={{ color: 'var(--color-purple, #a78bfa)' }} />
            版权资源样例
          </div>
          <div style={{ display: 'grid', gap: '0.55rem' }}>
            {(cases.length ? cases : [record]).slice(0, 8).map((item, index) => (
              <button
                type="button"
                key={`${item.resource_id || 'resource'}-${item.chunk_id || index}`}
                onClick={() => setSelectedIndex(index)}
                style={{
                  textAlign: 'left',
                  padding: '0.75rem',
                  borderRadius: '12px',
                  border: selectedIndex === index ? '1px solid var(--color-purple, #a78bfa)' : '1px solid var(--border)',
                  background: selectedIndex === index ? 'rgba(167,139,250,0.12)' : 'rgba(255,255,255,0.035)',
                  color: '#e5f6ff',
                }}
              >
                <strong style={{ display: 'block', fontSize: '0.82rem' }}>{item.resource_id || `resource_${index + 1}`}</strong>
                <span style={{ display: 'block', marginTop: '0.25rem', color: 'var(--muted)', fontSize: '0.72rem' }}>
                  {item.chunk_id || 'chunk_pending'} · {item.return_mode || 'controlled'}
                </span>
              </button>
            ))}
          </div>
        </aside>

        <section className="data-panel-card" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1rem' }}>
          <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.9rem', fontWeight: 800 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldCheck size={16} style={{ color: 'var(--green)' }} />
              C²-RAG 版权控制凭证
            </span>
            {record.demo_metadata && (
              <em style={{ padding: '0.25rem 0.5rem', borderRadius: '999px', background: 'rgba(251,191,36,0.1)', color: '#fde68a', fontSize: '0.65rem', fontStyle: 'normal' }}>
                demo metadata
              </em>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '0.65rem' }}>
            {fieldRows.map(([key, label]) => (
              <div key={key} style={{ padding: '0.7rem', borderRadius: '12px', background: 'rgba(0,0,0,0.18)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <span style={{ display: 'block', color: 'var(--muted)', fontSize: '0.68rem', marginBottom: '0.25rem' }}>{label}</span>
                <strong style={{ color: '#f8fbff', fontSize: '0.82rem', wordBreak: 'break-word' }}>{formatValue(record[key])}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="data-panel-card" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1rem' }}>
          <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', fontWeight: 800 }}>
            <FileText size={16} style={{ color: 'var(--blue)' }} />
            受控返回内容
          </div>
          <div style={{ minHeight: '210px', maxHeight: '320px', overflowY: 'auto', padding: '0.9rem', borderRadius: '12px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.06)', color: '#d7e8ee', lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
            {record.controlled_content || '暂无受控内容。运行闭环案例后，这里会展示 C²-RAG 返回给教学代理的摘要、变体题或降级提示。'}
          </div>
        </section>
      </div>

      <div className="data-panel-card" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.75rem', backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1rem', marginBottom: '1.5rem' }}>
        <div><span style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>Plain RAG 平均泄漏</span><strong style={{ display: 'block', color: '#fecaca' }}>{formatValue(attackSummary.plain_avg_leakage, loading ? '加载中' : '-')}</strong></div>
        <div><span style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>C²-RAG 平均泄漏</span><strong style={{ display: 'block', color: '#bbf7d0' }}>{formatValue(attackSummary.c2rag_avg_leakage, '-')}</strong></div>
        <div><span style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>反重构攻击样例</span><strong style={{ display: 'block', color: '#f8fbff' }}>{attackRows.length} 条</strong></div>
      </div>

      <div className="fopd-shield-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem', backgroundColor: 'rgba(139, 92, 246, 0.04)', border: '1px solid var(--color-purple, #a78bfa)', borderRadius: '16px', padding: '1rem 1.25rem' }}>
        <ShieldCheck size={32} style={{ color: 'var(--color-purple, #a78bfa)', flexShrink: 0 }} />
        <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--muted)', lineHeight: 1.7 }}>
          <strong style={{ color: '#ffffff' }}>资源范围说明：</strong>
          教师版权保护子机制不仅处理教师手动上传资料，也处理学校购买数据库、出版社题库、商业课程包、公开教育资源和 AI 衍生教学内容。
        </p>
      </div>

      <AcademicFigurePanel
        pipelineData={pipelineData}
        figures={['multi_round_detection', 'tamper_localization', 'cross_mechanism_heatmap']}
      />
    </section>
  );
}
