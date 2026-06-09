import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle,
  ChevronRight,
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
  Workflow,
  Cpu,
  Clock,
  Eye,
  ArrowRight,
  Info
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
  LineElement,
  PointElement,
  RadialLinearScale,
  Title,
  Tooltip
} from 'chart.js';

// Import newly refactored components
import JsonDrawer from './components/JsonDrawer';
import RuntimeSummary from './components/RuntimeSummary';
import WorkflowFlowMap from './components/WorkflowFlowMap';
import WorkflowTimeline from './components/WorkflowTimeline';
import WorkflowStepDetail from './components/WorkflowStepDetail';
import ProtectionExplanation from './components/ProtectionExplanation';
import MMFOPDPanel from './components/MMFOPDPanel';
import C2RAGPanel from './components/C2RAGPanel';
import AgentCommunicationGraph from './components/AgentCommunicationGraph';
import AuditTracePanel from './components/AuditTracePanel';
import AttackTestPanel from './components/AttackTestPanel';
import LiveExecutionConsole from './components/LiveExecutionConsole';
import CasePickerModal from './components/CasePickerModal';
import FireworksOverlay from './components/FireworksOverlay';

import './App.css';

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  RadialLinearScale,
  Title,
  Tooltip
);

const tabs = [
  { id: 'overview', label: '学术大屏 / Overview', icon: Shield },
  { id: 'workflow', label: '防护流水线 / Live Workflow', icon: Workflow },
  { id: 'mmfopd', label: '画隐私脱敏 / MM-FOPD', icon: EyeOff },
  { id: 'c2rag', label: '版权出库控制 / C²-RAG', icon: BookOpen },
  { id: 'communications', label: '主动中介路由 / Agent Comms', icon: GitBranch },
  { id: 'attacks', label: '模拟攻防沙盘 / Attack Tests', icon: ShieldAlert },
  { id: 'audit', label: '水印审计溯源 / HSW-ST Audit', icon: Terminal }
];

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#cbd5e1', font: { family: 'Outfit', size: 10 } } },
    tooltip: { backgroundColor: '#0f172a' }
  },
  scales: {
    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.04)' } },
    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.04)' } },
    r: {
      ticks: { display: false },
      grid: { color: 'rgba(148, 163, 184, 0.08)' },
      angleLines: { color: 'rgba(148, 163, 184, 0.08)' },
      pointLabels: { color: '#cbd5e1', font: { size: 9 } }
    }
  }
};


function percent(value) {
  const n = Number(value ?? 0);
  return `${(n * 100).toFixed(1)}%`;
}

function summarizeCaseName(item, index) {
  return item?.student_hash 
    ? `${index + 1}. ${item.knowledge_point} (${item.student_hash.substring(0, 8)})`
    : `Student Case ${index + 1}`;
}

const KNOWLEDGE_ICONS = {
  'arithmetic sequence': '📐',
  'proportional relationship': '⚖️',
  'function graph interpretation': '📈',
  'fraction simplification': '🔢',
  'linear equation solving': '✏️',
  'quadratic vertex form': '📊',
};

function getKnowledgeIcon(kp) {
  if (!kp) return '📝';
  const lower = kp.toLowerCase();
  for (const [key, icon] of Object.entries(KNOWLEDGE_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return '📝';
}

async function readNdjsonStream(response, onEvent) {
  if (!response.body) {
    throw new Error('Streaming response body is unavailable in this browser.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      onEvent(JSON.parse(line));
    }

    if (done) break;
  }

  if (buffer.trim()) {
    onEvent(JSON.parse(buffer));
  }
}

function upsertWorkflowStep(data, step) {
  const current = data || { workflow_steps: [], communication_logs: [] };
  const steps = [...(current.workflow_steps || [])];
  const index = steps.findIndex((item) => item.step_id === step.step_id);
  if (index >= 0) steps[index] = step;
  else steps.push(step);
  steps.sort((left, right) => left.step_id - right.step_id);
  return { ...current, workflow_steps: steps };
}

function appendCommunication(data, event) {
  const current = data || { workflow_steps: [], communication_logs: [] };
  const message = {
    ...(event.message || {}),
    payload: event.payload,
    stream_direction: event.direction,
  };
  return {
    ...current,
    communication_logs: [...(current.communication_logs || []), message],
  };
}

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [cases, setCases] = useState([]);
  const [selectedCaseIdx, setSelectedCaseIdx] = useState(0);
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [attackResults, setAttackResults] = useState([]);
  const [streamEvents, setStreamEvents] = useState([]);
  const [liveConversations, setLiveConversations] = useState([]);
  const [streamStatus, setStreamStatus] = useState('idle');
  
  // App States
  const [activeStep, setActiveStep] = useState(0);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [error, setError] = useState('');
  const [isJsonDrawerOpen, setIsJsonDrawerOpen] = useState(false);
  
  // New dynamic interaction states
  const [isCasePickerOpen, setIsCasePickerOpen] = useState(false);
  const [showFireworks, setShowFireworks] = useState(false);
  const [runningAttackBatch, setRunningAttackBatch] = useState(false);
  const prevStreamStatusRef = useRef('idle');

  const apiGet = async (path) => {
    const res = await fetch(`${path}${path.includes('?') ? '&' : '?'}_=${Date.now()}`, {
      cache: 'no-store'
    });
    if (!res.ok) throw new Error(`${path} returned HTTP status ${res.status}`);
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

  const runProtectedFlowStream = async () => {
    setRunningPipeline(true);
    setPipelineData(null);
    setStreamEvents([]);
    setLiveConversations([]);
    setStreamStatus('connecting');
    setActiveStep(0);
    setActiveTab('workflow');
    setError('');

    const handleStreamEvent = (event) => {
      setStreamEvents((current) => [...current, event]);

      if (event.type === 'stream_opened') {
        setStreamStatus('connected');
      } else if (event.type === 'run_started') {
        setStreamStatus('running');
        setRuntimeStatus(event.runtime_status || runtimeStatus);
        setPipelineData({
          round_id: event.round_id,
          runtime_status: event.runtime_status,
          workflow_steps: [],
          communication_logs: [],
          task_id: event.task_id,
          knowledge_point: event.knowledge_point,
        });
      } else if (event.type === 'workflow_step') {
        setPipelineData((current) => upsertWorkflowStep(current, event.step));
        setActiveStep(event.step.step_id);
      } else if (event.type === 'tpcs_message') {
        setPipelineData((current) => appendCommunication(current, event));
      } else if (event.type === 'llm_call_started') {
        setLiveConversations((current) => [
          ...current,
          {
            call_id: event.call_id,
            agent_id: event.agent_id,
            agent_name: event.agent_name,
            payload: event.payload,
            prompt: event.prompt,
            responseText: '',
            status: 'streaming',
            mode: 'real_llm',
          },
        ]);
      } else if (event.type === 'llm_response_delta') {
        setLiveConversations((current) => current.map((call) => (
          call.call_id === event.call_id
            ? { ...call, responseText: `${call.responseText || ''}${event.delta || ''}` }
            : call
        )));
      } else if (event.type === 'llm_call_completed') {
        setLiveConversations((current) => current.map((call) => (
          call.call_id === event.call_id
            ? {
                ...call,
                responseText: call.responseText || event.response_text || '',
                response: event.response,
                status: 'completed',
                mode: event.mode,
                error: event.error,
              }
            : call
        )));
      } else if (event.type === 'run_completed') {
        setStreamStatus('completed');
        setPipelineData(event.result);
        setRuntimeStatus(event.result?.runtime_status || runtimeStatus);
        const finalSteps = event.result?.workflow_steps || [];
        if (finalSteps.length) {
          setActiveStep(finalSteps[finalSteps.length - 1].step_id);
        }
      } else if (event.type === 'error') {
        setStreamStatus('error');
        setError(`Backend pipeline execution failed: ${event.error}`);
      }
    };

    try {
      const response = await fetch('/api/run-case/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({
          case_index: selectedCaseIdx,
          runtime_mode: runtimeStatus?.runtime_mode || 'guarded_llm',
          enable_nemo: runtimeStatus?.nemo_guardrails_enabled ?? true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP status ${response.status}.`);
      }

      await readNdjsonStream(response, handleStreamEvent);
      await loadInitialData();
    } catch (err) {
      setStreamStatus('error');
      setError(err.message);
    } finally {
      setRunningPipeline(false);
    }
  };

  const runProtectedFlow = async () => {
    setRunningPipeline(true);
    setPipelineData(null); // Clear previous runs on click to reflect live progress
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

      if (!res.ok) {
        throw new Error(`Server returned HTTP error status ${res.status}. (后端接口返回错误)`);
      }

      const data = await res.json();
      
      if (data.error) {
        throw new Error(`Backend pipeline execution failed: ${data.error}. (防护流水线运行失败，请查看完整报文)`);
      }

      if (!data.workflow_steps || data.workflow_steps.length === 0) {
        setPipelineData(data); // Set anyway so they can inspect raw JSON
        throw new Error("Backend returned no workflow_steps. Click 'View Raw Response' to inspect the transaction details.");
      }

      setPipelineData(data);
      setRuntimeStatus(data.runtime_status || runtimeStatus);
      setActiveStep(0); // Reset stepper highlight
      setActiveTab('workflow'); // Auto switch on success!
      
      // Refresh metrics dynamically
      await loadInitialData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningPipeline(false);
    }
  };

  // Trigger fireworks when stream completes
  useEffect(() => {
    if (prevStreamStatusRef.current === 'running' && streamStatus === 'completed') {
      setShowFireworks(true);
    }
    prevStreamStatusRef.current = streamStatus;
  }, [streamStatus]);

  const dismissFireworks = useCallback(() => {
    setShowFireworks(false);
  }, []);

  // Attack batch runner
  const runAttackBatch = async () => {
    setRunningAttackBatch(true);
    setError('');
    try {
      const res = await fetch('/api/attacks/run-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
      });
      if (!res.ok) throw new Error(`Attack batch returned HTTP ${res.status}`);
      const data = await res.json();
      if (data.success) {
        setAttackResults(data.results || attackResults);
        await loadInitialData(); // Refresh metrics
      } else {
        setError(data.error || 'Attack batch failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningAttackBatch(false);
    }
  };

  // Single attack runner
  const runSingleAttack = async (caseId) => {
    setError('');
    try {
      const res = await fetch('/api/run-attack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attack_case_id: caseId }),
      });
      if (!res.ok) throw new Error(`Attack returned HTTP ${res.status}`);
      await loadInitialData(); // Refresh metrics
    } catch (err) {
      setError(err.message);
    }
  };

  // NeMo safety rail checkers passed to nodes
  const getRailStateForStep = (stepIdx, rail, data) => {
    if (!data) return 'not_enabled';
    const nemoLogs = data.protection_logs?.nemo_guardrails?.rails || {};
    if (rail === 'input_rail' && stepIdx === 2) {
      const dec = nemoLogs.input_rail?.decision;
      return dec === 'block' ? 'blocked' : dec === 'allow' ? 'passed' : dec === 'sanitize' ? 'sanitized' : 'not_enabled';
    }
    if (rail === 'retrieval_rail' && stepIdx === 5) {
      const dec = nemoLogs.retrieval_rail?.decision;
      return dec === 'block' ? 'blocked' : dec === 'allow' ? 'passed' : dec === 'sanitize' ? 'sanitized' : 'not_enabled';
    }
    if (rail === 'output_rail' && stepIdx === 6) {
      const dec = nemoLogs.output_rail?.decision;
      return dec === 'block' ? 'blocked' : dec === 'allow' ? 'passed' : dec === 'sanitize' ? 'sanitized' : 'not_enabled';
    }
    if (rail === 'execution_rail' && (stepIdx === 3 || stepIdx === 4 || stepIdx === 6 || stepIdx === 7)) {
      return 'passed';
    }
    return 'not_enabled';
  };

  const getRailStateLabel = (state) => {
    const labels = {
      'not_enabled': '未启用 / Not Enabled',
      'passed': '已通过 / Passed',
      'blocked': '已拦截 / Blocked',
      'sanitized': '已脱敏 / Sanitized',
      'rewritten': '已重写 / Rewritten'
    };
    return labels[state] || '未启用 / Not Enabled';
  };

  const defenseChart = useMemo(() => ({
    labels: ['阻断拦截 (Blocked)', '文本净化 (Sanitized)', '凭证降级 (Degraded)', '漏过逃逸 (ASR Escaped)'],
    datasets: [{
      label: 'Attack outcomes',
      data: [
        metrics?.blocked_attacks || 0,
        metrics?.sanitized_attacks || 0,
        metrics?.degraded_attacks || 0,
        metrics?.successful_attacks || 0
      ],
      backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'],
      borderWidth: 1,
      borderColor: 'rgba(255, 255, 255, 0.05)'
    }]
  }), [metrics]);

  const radarChart = useMemo(() => ({
    labels: ['画像隐私 (Privacy)', '课件版权 (Copyright)', '水印审计 (Audit)', '防御拦截 (Defense)', '横向控制器 (TPCS)'],
    datasets: [{
      label: 'CogniGuard protection rate (%)',
      data: [
        (metrics?.privacy_protection_rate || 0) * 100,
        (metrics?.copyright_protection_rate || 0) * 100,
        (metrics?.audit_coverage_rate || 0) * 100,
        (metrics?.defense_success_rate || 0) * 100,
        100
      ],
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.18)',
      pointBackgroundColor: '#3b82f6',
      borderWidth: 1.5
    }]
  }), [metrics]);

  const caseName = cases.length > 0 ? summarizeCaseName(cases[selectedCaseIdx], selectedCaseIdx) : 'Loading...';
  const runtimeMessage = runtimeStatus?.api_key_loaded
    ? `Current active mode: ${runtimeStatus.runtime_mode}. Call mode: ${runtimeStatus.agent_call_mode}.`
    : 'System currently operating in DETERMINISTIC_FALLBACK mock mode. No real LLM call is being made.';
  const selectedWorkflowStep = pipelineData?.workflow_steps?.find(
    (step) => step.step_id === activeStep
  ) || pipelineData?.workflow_steps?.[0];

  return (
    <div className="app-container">
      {/* Sidebar Nav */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-section">
            <ShieldCheck className="brand-icon" size={32} />
            <div>
              <div className="brand-title">CogniGuard</div>
              <div className="brand-subtitle">tutoring safety platform</div>
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
                <Icon size={16} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', lineHeight: '1.3' }}>Three protection layers + TPCS governance controller</div>
          <div className="status-indicator active" style={{ marginTop: '0.5rem' }}>
            <span className="dot" />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>{runtimeStatus?.runtime_mode || 'loading'}</span>
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <main className="main-content">
        <header className="topbar">
          <div>
            <h2>CogniGuard： tutoring 多智能体主动安全防护大屏</h2>
            <p>基于 MM-FOPD 画像隔离隐私、C²-RAG 课件版权保护、HSW-ST 水印防伪以及 TPCS 横向中介控制的主动安全科研演示看板</p>
          </div>
          <div className="topbar-actions">
            {/* Case selector badge — click to open card picker */}
            <div
              className="case-selector-badge"
              onClick={() => setIsCasePickerOpen(true)}
              title="点击选择诊断案例"
            >
              <span className="case-selector-badge-icon">
                {cases.length > 0 ? getKnowledgeIcon(cases[selectedCaseIdx]?.knowledge_point) : '📝'}
              </span>
              <div className="case-selector-badge-text">
                <div className="case-selector-badge-kp">
                  {cases.length > 0 ? (cases[selectedCaseIdx]?.knowledge_point || `Case #${selectedCaseIdx + 1}`) : 'Loading...'}
                </div>
                <div className="case-selector-badge-sub">
                  案例 #{selectedCaseIdx + 1} / {cases.length} — 点击切换
                </div>
              </div>
              <ChevronRight size={16} className="case-selector-badge-arrow" />
            </div>
            
            <button className="run-btn" onClick={runProtectedFlowStream} disabled={runningPipeline}>
              {runningPipeline ? <RefreshCw size={16} className="spin" /> : <Play size={16} />}
              <span>{runningPipeline ? '正在执行防护流...' : 'Run Protected Flow'}</span>
            </button>
          </div>
        </header>

        {/* Global Error Banner */}
        {error && (
          <section className="alert-card" style={{ margin: '1rem 2rem', padding: '1rem', backgroundColor: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '8px', display: 'flex', gap: '0.75rem', alignItems: 'center', color: 'var(--color-red)' }}>
            <AlertTriangle size={20} style={{ flexShrink: 0 }} />
            <div style={{ flexGrow: 1, fontSize: '0.8rem' }}>
              <strong>系统拦截或报错：</strong> {error}
            </div>
            <button
              onClick={() => setIsJsonDrawerOpen(true)}
              style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', color: '#ffffff', borderRadius: '4px', padding: '0.25rem 0.5rem', fontSize: '0.7rem', cursor: 'pointer' }}
            >
              View Raw Response
            </button>
          </section>
        )}

        {/* Main tabs routing */}
        <div className="page-body" style={{ padding: '1.5rem 2rem' }}>
          
          {/* TAB 1: OVERVIEW DASHBOARD */}
          {activeTab === 'overview' && (
            <section className="dashboard-grid">
              <MetricCard title="总请求次数 (Total requests)" value={metrics?.total_requests ?? 0} detail="系统已审计的正常教学与攻击流量合集" icon={Activity} />
              <MetricCard title="拦截安全攻击 (Blocked attacks)" value={metrics?.blocked_attacks ?? 0} detail="已成功识别并阻断越权、注入及榨取威胁" icon={Shield} />
              <MetricCard title="安全防御成功率 (ADR)" value={percent(metrics?.defense_success_rate)} detail="已成功拦截、脱敏或降级限制的比率" icon={CheckCircle} />
              <MetricCard title="追踪审计覆盖率 (Audit coverage)" value={percent(metrics?.audit_coverage_rate)} detail="出库话术全量嵌入软水印并关联审计链" icon={Terminal} />

              {/* Warning/Status banner */}
              <div className="data-panel wide" style={{ padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(18, 24, 39, 0.6)' }}>
                <div style={{ fontSize: '0.8rem' }}>
                  <strong>{runtimeMessage}</strong>
                  <span style={{ display: 'block', color: 'var(--color-text-muted)', fontSize: '0.7rem', marginTop: '0.15rem' }}>
                    API provider: {runtimeStatus?.llm_provider || 'Xiaomi MiMo'} | Key loaded: {String(Boolean(runtimeStatus?.api_key_loaded))} | NeMo guardrails: {runtimeStatus?.nemo_guardrails_enabled ? 'Active (装载)' : 'Inactive'}
                  </span>
                </div>
                <Lock size={20} style={{ color: 'var(--color-blue)' }} />
              </div>

              {/* Layer principles summary */}
              <div className="data-panel wide">
                <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Layers size={16} /> <span>CogniGuard 三层纵向主动防护体系 + TPCS 控制总线架构</span></div>
                <div className="layer-row">
                  <div className="status-card" style={{ borderLeft: '3px solid var(--color-blue)' }}>
                    <h3 className="status-card-title" style={{ color: 'var(--color-blue)' }}>1. MM-FOPD 画像隐私层</h3>
                    <p className="status-card-subtitle">物理隔离敏感特征，提取认知语义，输出低暴露画像 context card 供智能体调度。</p>
                  </div>
                  <div className="status-card" style={{ borderLeft: '3px solid var(--color-purple)' }}>
                    <h3 className="status-card-title" style={{ color: 'var(--color-purple)' }}>2. C²-RAG 课件版权层</h3>
                    <p className="status-card-subtitle">控制教案 verbatim 出库泄露。动态降级为大纲、概要或衍生等效变体题。</p>
                  </div>
                  <div className="status-card" style={{ borderLeft: '3px solid #10b981' }}>
                    <h3 className="status-card-title" style={{ color: '#10b981' }}>3. HSW-ST 水印防伪层</h3>
                    <p className="status-card-subtitle">对出库话术进行 Heuristic 隐形水印嵌入，绑定 SHA256 审计链条实现溯源。</p>
                  </div>
                  <div className="status-card" style={{ borderLeft: '3px solid var(--color-yellow)' }}>
                    <h3 className="status-card-title" style={{ color: 'var(--color-yellow)' }}>TPCS 横向控制中介</h3>
                    <p className="status-card-subtitle">隔离智能体直连通信。验证握手路由准入凭证，二次核算累积画像隐私泄露开销。</p>
                  </div>
                </div>
              </div>

              {/* Dynamic Analytics Charts */}
              <div className="data-panel">
                <div className="data-panel-title">攻防决策分布 (Defensive Outcome Distribution)</div>
                <div className="chart-box" style={{ height: '220px', position: 'relative' }}><Doughnut data={defenseChart} options={chartOptions} /></div>
              </div>
              
              <div className="data-panel">
                <div className="data-panel-title">防御能力边界前沿图 (Security Frontier Rates)</div>
                <div className="chart-box" style={{ height: '220px', position: 'relative' }}><Radar data={radarChart} options={chartOptions} /></div>
              </div>
            </section>
          )}

          {/* TAB 2: LIVE WORKFLOW STREAMING */}
          {activeTab === 'workflow' && (
            <section className="content-stack">
              {/* If no pipeline run yet, show elegant prompt */}
              {!pipelineData ? (
                <div style={{ padding: '3rem 2rem', textAlign: 'center', backgroundColor: 'var(--bg-secondary)', border: '1px dashed var(--border-color)', borderRadius: '12px' }}>
                  <Workflow size={48} style={{ margin: '0 auto 1.5rem', display: 'block', color: 'var(--color-yellow)' }} />
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem', color: '#ffffff' }}>等待流水线激活 / Waiting for Ingestions</h3>
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem', maxWidth: '32rem', marginInline: 'auto' }}>
                    请先在右上角选择学生案例，并点击 <strong>“Run Protected Flow”</strong> 按钮以触发 CogniGuard 主动安全防护框架的多阶段流转遥测。
                  </p>
                </div>
              ) : (
                <>
                  {/* Top: Summary row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                    <div>
                      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>流水线流转详情：会话 ID {pipelineData.round_id}</h2>
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>案例归属: {caseName}</span>
                    </div>

                    <button
                      onClick={() => setIsJsonDrawerOpen(true)}
                      style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', color: '#ffffff', borderRadius: '6px', padding: '0.4rem 0.85rem', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                    >
                      <Terminal size={14} />
                      <span>View Raw Backend Response</span>
                    </button>
                  </div>

                  {/* Top Summary details */}
                  <RuntimeSummary pipelineData={pipelineData} runtimeStatus={runtimeStatus} />

                  <LiveExecutionConsole
                    conversations={liveConversations}
                    events={streamEvents}
                    pipelineData={pipelineData}
                    running={runningPipeline}
                    streamStatus={streamStatus}
                  />

                  {/* Middle: Folding/Horizontal flow map */}
                  <WorkflowFlowMap
                    pipelineData={pipelineData}
                    activeStep={activeStep}
                    onSelectStep={setActiveStep}
                    getRailStateForStep={getRailStateForStep}
                    getRailStateLabel={getRailStateLabel}
                  />

                  {/* Bottom: Three Column Detail */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr 1.2fr', gap: '1.5rem', alignItems: 'start' }}>
                    
                    {/* Left Column: Timeline list */}
                    <WorkflowTimeline
                      steps={pipelineData.workflow_steps || []}
                      activeStep={activeStep}
                      onSelectStep={setActiveStep}
                    />

                    {/* Middle Column: Active Step detail JSON */}
                    <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem' }}>
                      <WorkflowStepDetail step={selectedWorkflowStep} />
                    </div>

                    {/* Right Column: Dynamic protection explanations */}
                    <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem' }}>
                      <ProtectionExplanation step={selectedWorkflowStep} pipelineData={pipelineData} />
                    </div>
                  </div>
                </>
              )}
            </section>
          )}

          {/* TAB 3: MM-FOPD */}
          {activeTab === 'mmfopd' && (
            <MMFOPDPanel
              data={{
                raw_data_summary: pipelineData?.raw_data_summary,
                educational_semantics: pipelineData?.educational_semantics,
                context_card: pipelineData?.generated_context_card,
                privacy_log: pipelineData?.protection_logs?.mm_fopd
              }}
            />
          )}

          {/* TAB 4: C2-RAG */}
          {activeTab === 'c2rag' && (
            <C2RAGPanel
              data={{
                copyright_agent: pipelineData?.agent_outputs?.CopyrightAwareResourceAgent,
                c2_rag_log: pipelineData?.protection_logs?.c2_rag,
                snippets: pipelineData?.agent_outputs?.CopyrightAwareResourceAgent?.controlled_resource_snippets
              }}
            />
          )}

          {/* TAB 5: AGENT COMMUNICATIONS */}
          {activeTab === 'communications' && (
            <AgentCommunicationGraph
              communicationLogs={pipelineData?.communication_logs}
              pipelineData={pipelineData}
            />
          )}

          {/* TAB 6: SIMULATION ATTACKS */}
          {activeTab === 'attacks' && (
            <AttackTestPanel
              attackResults={attackResults}
              metrics={metrics}
              onRunAttackBatch={runAttackBatch}
              runningAttackBatch={runningAttackBatch}
              onRunSingleAttack={runSingleAttack}
            />
          )}

          {/* TAB 7: HSW-ST AUDIT VIEWER */}
          {activeTab === 'audit' && (
            <AuditTracePanel
              data={{
                final_answer: pipelineData?.final_protected_teaching_answer,
                audit_trace: pipelineData?.audit_trace,
                protection_logs: pipelineData?.protection_logs,
                communication_logs: pipelineData?.communication_logs,
                profile_update_decision: pipelineData?.profile_update_decision
              }}
            />
          )}

        </div>
      </main>

      {/* Global Raw JSON Inspect Drawer */}
      <JsonDrawer
        isOpen={isJsonDrawerOpen}
        onClose={() => setIsJsonDrawerOpen(false)}
        data={pipelineData}
        title={`Audit raw transaction context: round_${pipelineData?.round_id || 'not_started'}`}
      />

      {/* Case Picker Modal */}
      <CasePickerModal
        isOpen={isCasePickerOpen}
        cases={cases}
        selectedIdx={selectedCaseIdx}
        onSelect={setSelectedCaseIdx}
        onClose={() => setIsCasePickerOpen(false)}
      />

      {/* Fireworks Celebration Overlay */}
      <FireworksOverlay
        visible={showFireworks}
        onDismiss={dismissFireworks}
      />
    </div>
  );
}

function MetricCard({ title, value, detail, icon: Icon }) {
  return (
    <div className="metric-card">
      <div className="metric-header">
        <span>{title}</span>
        {Icon && <Icon className="metric-header-icon" size={18} />}
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-desc">{detail}</div>
    </div>
  );
}

export default App;
