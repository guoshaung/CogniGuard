import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle,
  Database,
  EyeOff,
  GitBranch,
  Layers,
  Lock,
  Play,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Workflow
} from 'lucide-react';
import { Bar, Doughnut, Radar } from 'react-chartjs-2';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  PointElement,
  RadialLinearScale,
  Title,
  Tooltip
} from 'chart.js';
import './App.css';

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  PointElement,
  RadialLinearScale,
  Title,
  Tooltip
);

const tabs = [
  { id: 'overview', label: 'Overview', icon: Shield },
  { id: 'workflow', label: 'Live workflow', icon: Workflow },
  { id: 'mmfopd', label: 'MM-FOPD', icon: EyeOff },
  { id: 'c2rag', label: 'C2-RAG', icon: BookOpen },
  { id: 'communications', label: 'Agent comms', icon: GitBranch },
  { id: 'attacks', label: 'Attack tests', icon: ShieldAlert },
  { id: 'audit', label: 'Audit trace', icon: Terminal }
];

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#cbd5e1' } },
    tooltip: { backgroundColor: '#0f172a' }
  },
  scales: {
    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.08)' } },
    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.08)' } },
    r: {
      ticks: { color: '#94a3b8', backdropColor: 'transparent' },
      grid: { color: 'rgba(148, 163, 184, 0.12)' },
      angleLines: { color: 'rgba(148, 163, 184, 0.12)' },
      pointLabels: { color: '#cbd5e1' }
    }
  }
};

function safeJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function percent(value) {
  const n = Number(value ?? 0);
  return `${(n * 100).toFixed(1)}%`;
}

function summarizeCaseName(item, index) {
  return item?.student_hash || item?.student_id || item?.context_card?.student_hash || `student_${index + 1}`;
}

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [cases, setCases] = useState([]);
  const [selectedCaseIdx, setSelectedCaseIdx] = useState(0);
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [attackResults, setAttackResults] = useState([]);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [error, setError] = useState('');

  const apiGet = async (path) => {
    const res = await fetch(`${path}${path.includes('?') ? '&' : '?'}_=${Date.now()}`, {
      cache: 'no-store'
    });
    if (!res.ok) throw new Error(`${path} returned ${res.status}`);
    return res.json();
  };

  const loadInitialData = async () => {
    setError('');
    try {
      const [status, metricData, caseData, attacks] = await Promise.all([
        apiGet('/api/runtime/status'),
        apiGet('/api/dashboard/metrics'),
        apiGet('/api/cases'),
        apiGet('/api/attacks/results')
      ]);
      setRuntimeStatus(status);
      setMetrics(metricData);
      setCases(caseData.rows || caseData.cases || []);
      setAttackResults(attacks.results || []);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const runProtectedFlow = async () => {
    setRunningPipeline(true);
    setError('');
    try {
      const res = await fetch('/api/run-case', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({
          case_index: selectedCaseIdx,
          runtime_mode: runtimeStatus?.runtime_mode || 'guarded_llm',
          enable_nemo: runtimeStatus?.nemo_guardrails_enabled ?? true
        })
      });
      if (!res.ok) throw new Error(`/api/run-case returned ${res.status}`);
      const data = await res.json();
      setPipelineData(data);
      setRuntimeStatus(data.runtime_status || runtimeStatus);
      setActiveTab('workflow');
      await loadInitialData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningPipeline(false);
    }
  };

  const defenseChart = useMemo(() => ({
    labels: ['Blocked', 'Sanitized', 'Degraded', 'Successful'],
    datasets: [{
      label: 'Attack outcomes',
      data: [
        metrics?.blocked_attacks || 0,
        metrics?.sanitized_attacks || 0,
        metrics?.degraded_attacks || 0,
        metrics?.successful_attacks || 0
      ],
      backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
    }]
  }), [metrics]);

  const radarChart = useMemo(() => ({
    labels: ['Privacy', 'Copyright', 'Audit', 'Defense', 'TPCS'],
    datasets: [{
      label: 'CogniGuard protection rate',
      data: [
        (metrics?.privacy_protection_rate || 0) * 100,
        (metrics?.copyright_protection_rate || 0) * 100,
        (metrics?.audit_coverage_rate || 0) * 100,
        (metrics?.defense_success_rate || 0) * 100,
        100
      ],
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.22)',
      pointBackgroundColor: '#3b82f6'
    }]
  }), [metrics]);

  const caseName = summarizeCaseName(cases[selectedCaseIdx], selectedCaseIdx);
  const runtimeMessage = runtimeStatus?.api_key_loaded
    ? `Current mode: ${runtimeStatus.runtime_mode}. Agent call mode: ${runtimeStatus.agent_call_mode}.`
    : 'Current mode: mock fallback. No real LLM call is being made.';

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-section">
            <ShieldCheck className="brand-icon" size={30} />
            <div>
              <div className="brand-title">CogniGuard</div>
              <div className="brand-subtitle">protected tutoring demo</div>
            </div>
          </div>
        </div>

        <nav className="nav-menu">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={`nav-item ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
                title={tab.label}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div>Three protection layers plus TPCS governance</div>
          <div className="status-indicator active">
            <span className="dot" />
            <span>{runtimeStatus?.runtime_mode || 'loading'}</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <h2>Interactive protected multi-agent LLM demo</h2>
            <p>MM-FOPD privacy, C2-RAG copyright control, HSW-ST watermark audit, governed by TPCS.</p>
          </div>
          <div className="topbar-actions">
            <select
              className="case-selector"
              value={selectedCaseIdx}
              onChange={(event) => setSelectedCaseIdx(Number(event.target.value))}
            >
              {(cases.length ? cases : [{ student_hash: 'fallback_student' }]).map((item, index) => (
                <option key={index} value={index}>{summarizeCaseName(item, index)}</option>
              ))}
            </select>
            <button className="run-btn" onClick={runProtectedFlow} disabled={runningPipeline}>
              {runningPipeline ? <RefreshCw size={18} className="spin" /> : <Play size={18} />}
              <span>{runningPipeline ? 'Running...' : 'Run Protected Flow'}</span>
            </button>
          </div>
        </header>

        {error && (
          <section className="alert-card">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </section>
        )}

        <section className="runtime-banner">
          <div>
            <strong>{runtimeMessage}</strong>
            <span>
              Provider: {runtimeStatus?.llm_provider || 'MiniMax'} | API key loaded: {String(Boolean(runtimeStatus?.api_key_loaded))}
              {' '}| NeMo Guardrails: {runtimeStatus?.nemo_guardrails_enabled ? 'enabled' : 'disabled'}
            </span>
          </div>
          <Lock size={22} />
        </section>

        {activeTab === 'overview' && (
          <section className="dashboard-grid">
            <MetricCard title="Total requests" value={metrics?.total_requests ?? 0} detail="Normal plus attack traffic" icon={Activity} />
            <MetricCard title="Blocked attacks" value={metrics?.blocked_attacks ?? 0} detail="Refused by protection framework" icon={Shield} />
            <MetricCard title="Defense success" value={percent(metrics?.defense_success_rate)} detail="Blocked, sanitized, or degraded" icon={CheckCircle} />
            <MetricCard title="Audit coverage" value={percent(metrics?.audit_coverage_rate)} detail="Watermark and trace binding" icon={Terminal} />

            <div className="data-panel wide">
              <div className="data-panel-title">Protection architecture</div>
              <div className="layer-row">
                <LayerCard title="1. MM-FOPD" text="Raw multimodal student data is minimized into low exposure teaching context cards." />
                <LayerCard title="2. C2-RAG" text="Teacher resources are retrieved through exposure budgets and controlled return modes." />
                <LayerCard title="3. HSW-ST" text="Final answers are watermarked and bound to an auditable trace." />
                <LayerCard title="TPCS" text="Horizontal controller routes every agent message and approves profile updates." />
              </div>
            </div>

            <div className="data-panel">
              <div className="data-panel-title">Attack outcomes</div>
              <div className="chart-box"><Doughnut data={defenseChart} options={chartOptions} /></div>
            </div>
            <div className="data-panel">
              <div className="data-panel-title">Protection rates</div>
              <div className="chart-box"><Radar data={radarChart} options={chartOptions} /></div>
            </div>
          </section>
        )}

        {activeTab === 'workflow' && (
          <section className="content-stack">
            <HeaderBlock
              title={`Live protected run: ${pipelineData?.round_id || 'not started'}`}
              subtitle={`Selected case: ${caseName}`}
            />
            <div className="workflow-list">
              {(pipelineData?.workflow_steps || []).map((step) => (
                <div className="workflow-step" key={step.step_id}>
                  <div className="step-index">{step.step_id}</div>
                  <div className="step-body">
                    <div className="step-title">{step.step_name}</div>
                    <div className="step-meta">
                      <span>{step.layer}</span>
                      <span>TPCS: {step.tpcs_decision}</span>
                      <span>NeMo: {step.nemo_decision}</span>
                      <span>Risk: {Number(step.risk_score || 0).toFixed(2)}</span>
                    </div>
                    <pre>{safeJson({ input: step.input_summary, output: step.output_summary })}</pre>
                  </div>
                </div>
              ))}
              {!pipelineData && <EmptyState text="Run the protected flow to generate a fresh multi-agent round." />}
            </div>
            {pipelineData?.final_protected_teaching_answer && (
              <div className="data-panel">
                <div className="data-panel-title">Final protected teaching answer</div>
                <p className="answer-text">{pipelineData.final_protected_teaching_answer}</p>
              </div>
            )}
          </section>
        )}

        {activeTab === 'mmfopd' && (
          <JsonPanel
            title="MM-FOPD minimum disclosure view"
            icon={EyeOff}
            data={{
              raw_data_summary: pipelineData?.raw_data_summary,
              educational_semantics: pipelineData?.educational_semantics,
              context_card: pipelineData?.generated_context_card,
              privacy_log: pipelineData?.protection_logs?.mm_fopd
            }}
          />
        )}

        {activeTab === 'c2rag' && (
          <JsonPanel
            title="C2-RAG controlled resource view"
            icon={BookOpen}
            data={{
              copyright_agent: pipelineData?.agent_outputs?.CopyrightAwareResourceAgent,
              c2_rag_log: pipelineData?.protection_logs?.c2_rag,
              snippets: pipelineData?.agent_outputs?.CopyrightAwareResourceAgent?.controlled_resource_snippets
            }}
          />
        )}

        {activeTab === 'communications' && (
          <section className="content-stack">
            <HeaderBlock title="TPCS governed agent communications" subtitle="No agent directly calls another agent without controller permission." />
            {(pipelineData?.communication_logs || []).map((log, index) => (
              <div className="comm-card" key={`${log.round_id}-${index}`}>
                <GitBranch size={18} />
                <div>
                  <strong>{log.sender} {'->'} {log.receiver}</strong>
                  <div className="step-meta">
                    <span>{log.message_type}</span>
                    <span>privacy: {log.privacy_level}</span>
                    <span>disclosure: {Number(log.disclosure_score || 0).toFixed(2)}</span>
                    <span>decision: {log.tpcs_decision || 'allow'}</span>
                  </div>
                </div>
              </div>
            ))}
            {!pipelineData && <EmptyState text="Run a case to inspect communication logs." />}
          </section>
        )}

        {activeTab === 'attacks' && (
          <section className="content-stack">
            <HeaderBlock title="Protection attack test cases" subtitle="Expected defenses are mapped to actual TPCS, C2-RAG, and HSW-ST behavior." />
            <div className="attack-grid">
              {attackResults.map((item) => (
                <div className="attack-card" key={item.attack_case_id}>
                  <div className="attack-card-title">{item.attack_case_id}: {item.attack_type}</div>
                  <p>{item.malicious_prompt}</p>
                  <div className="step-meta">
                    <span>{item.target_protection_layer}</span>
                    <span>{item.actual_decision}</span>
                    <span>{item.result}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'audit' && (
          <JsonPanel
            title="HSW-ST audit trace"
            icon={Database}
            data={{
              final_answer: pipelineData?.final_protected_teaching_answer,
              audit_trace: pipelineData?.audit_trace,
              protection_logs: pipelineData?.protection_logs
            }}
          />
        )}
      </main>
    </div>
  );
}

function MetricCard({ title, value, detail, icon: Icon }) {
  return (
    <div className="metric-card">
      <div className="metric-header">
        <Icon size={20} />
        <span>{title}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-desc">{detail}</div>
    </div>
  );
}

function LayerCard({ title, text }) {
  return (
    <div className="status-card">
      <Layers size={18} />
      <h3 className="status-card-title">{title}</h3>
      <p className="status-card-subtitle">{text}</p>
    </div>
  );
}

function HeaderBlock({ title, subtitle }) {
  return (
    <div className="section-header">
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="empty-state">
      <AlertTriangle size={20} />
      <span>{text}</span>
    </div>
  );
}

function JsonPanel({ title, icon: Icon, data }) {
  return (
    <section className="content-stack">
      <HeaderBlock title={title} subtitle="Frontend-safe JSON. Raw multimodal payloads are never exposed to agents." />
      <div className="data-panel">
        <div className="data-panel-title">
          <Icon size={18} />
          <span>{title}</span>
        </div>
        <pre>{safeJson(data)}</pre>
      </div>
    </section>
  );
}

export default App;
