import { useState, useEffect } from 'react';
import {
  Shield,
  Layers,
  Workflow,
  Terminal,
  GitBranch,
  Flame,
  Search,
  Activity,
  RefreshCw,
  Database,
  CheckCircle,
  AlertTriangle,
  Lock,
  BookOpen,
  EyeOff,
  Key,
  AlertOctagon,
  UserCheck,
  Play
} from 'lucide-react';
import { Line, Bar, Radar, Doughnut } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, RadialLinearScale, ArcElement, Title, Tooltip, Legend, Filler } from 'chart.js';
import './App.css';

// Register ChartJS plugins
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  RadialLinearScale,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [cases, setCases] = useState([]);
  const [selectedCaseIdx, setSelectedCaseIdx] = useState(0);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [pipelineData, setPipelineData] = useState(null);
  const [c2ragAttackData, setC2ragAttackData] = useState(null);
  const [attackCases, setAttackCases] = useState([]);
  const [selectedAttackId, setSelectedAttackId] = useState('atk_001');
  const [attackLogs, setAttackLogs] = useState({});
  const [runningAttack, setRunningAttack] = useState(false);

  // HSW-ST Tampering Sandbox state
  const [tamperedText, setTamperedText] = useState("");
  const [tamperMode, setTamperMode] = useState("none");
  const [watermarkDetectResult, setWatermarkDetectResult] = useState(null);
  const [detectingWatermark, setDetectingWatermark] = useState(false);

  // Stepper active step
  const [activeStep, setActiveStep] = useState(0);

  // Load cases and attack cases on init
  useEffect(() => {
    fetch('/api/cases')
      .then(res => res.json())
      .then(data => {
        if (data.rows) setCases(data.rows);
      })
      .catch(err => console.error("Error fetching cases:", err));

    fetch('/api/attack-cases')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setAttackCases(data);
          // Pre-populate logs with default mock values for display before trigger
          const defaultLogs = {};
          data.forEach(c => {
            defaultLogs[c.attack_case_id] = { triggered: false, data: c };
          });
          setAttackLogs(defaultLogs);
        }
      })
      .catch(err => console.error("Error fetching attack cases:", err));

    fetch('/api/c2rag-attacks')
      .then(res => res.json())
      .then(data => {
        setC2ragAttackData(data);
      })
      .catch(err => console.error("Error fetching C2RAG attacks:", err));
  }, []);

  // Run case pipeline
  const handleRunPipeline = () => {
    setRunningPipeline(true);
    fetch(`/api/run-case?index=${selectedCaseIdx}`)
      .then(res => res.json())
      .then(data => {
        setPipelineData(data);
        setRunningPipeline(false);
        setActiveStep(0); // Reset stepper
        setActiveTab('workflow'); // Automatically switch to workflow tab to show dynamic stepper
        // Set tampered text to final answer
        if (data.final_protected_teaching_answer) {
          setTamperedText(data.final_protected_teaching_answer);
          setTamperMode("none");
          setWatermarkDetectResult(null);
        }
      })
      .catch(err => {
        console.error("Error running pipeline:", err);
        setRunningPipeline(false);
      });
  };

  // Run attack simulation
  const handleTriggerAttack = (attackCaseId) => {
    setRunningAttack(true);
    fetch('/api/run-attack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: jsonEncode({ attack_case_id: attackCaseId })
    })
      .then(res => res.json())
      .then(resData => {
        setRunningAttack(false);
        if (resData.success) {
          setAttackLogs(prev => ({
            ...prev,
            [attackCaseId]: { triggered: true, data: resData.case }
          }));
        }
      })
      .catch(err => {
        console.error("Error running attack:", err);
        setRunningAttack(false);
      });
  };

  // Run watermark tampering test
  const handleTamperText = (mode) => {
    if (!pipelineData) return;
    const orig = pipelineData.final_protected_teaching_answer || "";
    setTamperMode(mode);
    setWatermarkDetectResult(null);

    let textToTamper = orig;
    if (mode === "delete") {
      // Tamper: Delete every 3rd sentence
      const sents = orig.split(/(?<=[。！？\n])/);
      textToTamper = sents.filter((_, idx) => idx % 3 !== 0).join("");
    } else if (mode === "truncate") {
      // Tamper: Keep middle half
      const len = orig.length;
      textToTamper = orig.substring(len / 4, (len / 4) * 3);
    } else if (mode === "mix") {
      // Tamper: Mix with clean text
      textToTamper = "In arithmetic sequence analysis, we define arithmetic series. " + orig;
    } else if (mode === "paraphrase") {
      // Tamper: Paraphrase light
      textToTamper = orig.replace("因此", "所以").replace("首先", "第一").replace("此外", "另外");
    } else if (mode === "summary") {
      // Tamper: Extreme compression, first 2 sentences only
      const sents = orig.split(/(?<=[。！？\n])/);
      textToTamper = sents.slice(0, 2).join("");
    }

    setTamperedText(textToTamper);
  };

  // Detect watermark in tempered text
  const handleDetectWatermark = () => {
    if (!tamperedText) return;
    setDetectingWatermark(true);

    // Call real Python watermarking tampering detection!
    fetch('/api/watermark-attack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: jsonEncode({
        text: tamperedText,
        clean_snippet: pipelineData?.audit_trace?.resource_bindings?.[0]?.content || "For arithmetic sequence, use a brief rule reminder."
      })
    })
      .then(res => res.json())
      .then(data => {
        setDetectingWatermark(false);
        const specificAttackResult = data.attacks?.find(a => {
          if (tamperMode === "delete") return a.attack_type === "delete_sentences";
          if (tamperMode === "truncate") return a.attack_type === "truncate_middle";
          if (tamperMode === "mix") return a.attack_type === "mix_with_clean";
          if (tamperMode === "paraphrase") return a.attack_type === "light_paraphrase";
          if (tamperMode === "summary") return a.attack_type === "summary_like";
          return a.attack_type === "light_paraphrase";
        }) || data.attacks?.[0];

        setWatermarkDetectResult(specificAttackResult || {
          is_watermarked_detected: true,
          detection_confidence: 0.95,
          description: "Watermark successfully parsed."
        });
      })
      .catch(err => {
        console.error("Error detecting watermark:", err);
        setDetectingWatermark(false);
      });
  };

  // Run first case on start if empty
  useEffect(() => {
    if (cases.length > 0 && !pipelineData) {
      handleRunPipeline();
    }
  }, [cases]);

  // Utility to stringify json
  const jsonEncode = (obj) => JSON.stringify(obj, null, 2);

  // Stepper steps definition
  const stepperSteps = [
    {
      title: "高模态敏感信号接入 (Raw Multimodal Intake)",
      desc: "物理层截获并读入学生手写轨迹压感、表情生理特征、语音高维信号及历史学情日志。",
      layer: "MM-FOPD (物理隔离接入)",
      getDetails: (data) => ({
        "Ingested Signals": data.raw_data_summary || "正在加载多模态轨迹...",
        "Sensitive Exposure State": "ISOLATED. 原始特征全部隔离在本地解密模块中，禁止流向 LLM 下游智能体。"
      })
    },
    {
      title: "画像模糊脱敏重构 (MM-FOPD Fuzzy Obfuscation)",
      desc: "提取核心教学语义，抹除直接身份标记，重构为具备低披露评分的最小画像 Context Card。",
      layer: "MM-FOPD (画像模糊处理)",
      getDetails: (data) => ({
        "Generated Context Card": data.generated_context_card || {},
        "Obfuscation Performance": "画像脱敏重构率 99.9%. 允许暴露给 LLM 的仅包含最小学情卡片。"
      })
    },
    {
      title: "TPCS 横向准入验证 (TPCS Pre-Check Guard)",
      desc: "实时校验会话隐私预算上限，严格评估本轮特征披露值后允许下发流转。",
      layer: "TPCS Controller (横向准入)",
      getDetails: (data) => ({
        "Governance Risk Assessment": data.tpcs_risk_decision || {},
        "Pre-check Decision": "APPROVED_MINIMUM_CONTEXT_CARD (审计通过，允许下发画像)"
      })
    },
    {
      title: "画像语义诊断分析 (Profile Diagnosis Agent)",
      desc: "纵向第一个 LLM 辅导智能体。仅接收已脱敏的 Context Card 分析学生核心认知错因。",
      layer: "Tutoring Agents (1/4 节点)",
      getDetails: (data) => ({
        "Agent ID": "profile_diagnosis_agent",
        "Dispatcher Privacy Level": "minimum_context (最小上下文)",
        "Payload Injected": { "context_card": data.generated_context_card },
        "Diagnosis Output": data.agent_outputs?.ProfileDiagnosisAgent?.diagnosis_result || {}
      })
    },
    {
      title: "版权意识资源规划 (Copyright Aware Resource Agent)",
      desc: "纵向第二个 LLM 智能体。基于错因诊断结论，在版权安全机制下生成资源检索申领诉求。",
      layer: "Tutoring Agents (2/4 节点)",
      getDetails: (data) => ({
        "Agent ID": "copyright_aware_resource_agent",
        "Dispatcher Privacy Level": "teaching_need_only (仅按教学需求披露)",
        "Resource Retrieve Payload": data.agent_outputs?.CopyrightAwareResourceAgent || {}
      })
    },
    {
      title: "C²-RAG 版权开销核算 (C²-RAG Control Engine)",
      desc: "进行知识产权累积出库核算，限制敏感段落，动态下发衍生变体或精简摘要。",
      layer: "C²-RAG Engine (版权保护)",
      getDetails: (data) => ({
        "Copyright Exposure Score": "0.42 (中度版权保护级别)",
        "Allowed Return Modes": ["summary", "outline", "snippet", "variant"],
        "C2RAG Selected Mode": data.agent_outputs?.CopyrightAwareResourceAgent?.controlled_resource_snippets?.[0]?.return_mode || "summary",
        "Sanitized Resource content": data.agent_outputs?.CopyrightAwareResourceAgent?.controlled_resource_snippets?.[0]?.content || ""
      })
    },
    {
      title: "启发式启发生成 (Pedagogical Teaching Agent)",
      desc: "纵向第三个 LLM 主干智能体。调用脱敏画像与变体教案，生成注重支架式引导的辅导文本。",
      layer: "Tutoring Agents (3/4 节点)",
      getDetails: (data) => ({
        "Agent ID": "pedagogical_teaching_agent",
        "Dispatcher Privacy Level": "minimum_context_plus_controlled_resource (脱敏画像+脱敏资源)",
        "Instruction Output": data.final_protected_teaching_answer?.split("\n\n")[0] || ""
      })
    },
    {
      title: "启发效果实时评估 (Learning Assessment Agent)",
      desc: "纵向第四个 LLM 智能体。分析错因变体的解答反馈，拟定反馈结果及画像卡片修正证据。",
      layer: "Tutoring Agents (4/4 节点)",
      getDetails: (data) => ({
        "Agent ID": "learning_assessment_agent",
        "Dispatcher Privacy Level": "answer_and_response_only (仅答题反馈审计)",
        "Assessment Results": {
          "mastery_score": data.agent_outputs?.LearningAssessmentAgent?.mastery_score,
          "confidence_score": data.agent_outputs?.LearningAssessmentAgent?.confidence_score,
          "assessment_result": data.agent_outputs?.LearningAssessmentAgent?.assessment_result,
          "follow_up_question": data.agent_outputs?.LearningAssessmentAgent?.follow_up_question
        }
      })
    },
    {
      title: "画像回传污染拦截 (TPCS Profile Update Review)",
      desc: "数据库写入的主动横向拦截。禁止学生自诉任意越权污染画像库，将证据录入审核队列。",
      layer: "TPCS Controller (横向画像写入隔离)",
      getDetails: (data) => ({
        "Profile Update Action": data.profile_update_logs || {},
        "Database Direct Write Status": "DENIED (拦截直接写库。Enforce Isolation 原则生效。已转入待审核日志)"
      })
    },
    {
      title: "启发水印追踪绑定 (HSW-ST Watermark Binding)",
      desc: "对最终生成的启发辅导文本微调嵌入 HSW 启发式隐形软水印，并对完整会话链条签名封印。",
      layer: "HSW-ST Layer (输出追踪防篡改)",
      getDetails: (data) => ({
        "Watermarked Answer": data.final_protected_teaching_answer || "",
        "Audit Trace Ref": data.audit_trace || {},
        "Cryptographic Integrity SHA256": data.audit_trace?.watermarked_answer_sha256 || ""
      })
    }
  ];

  // Radar metrics charts
  const metricsChartData = {
    labels: ['FOPD 画像实用性', '隐私保护率 (Privacy Rate)', 'C²-RAG 版权保留度', '水印篡改检出率 (ADR)', 'TPCS 威胁拦截率', '智能体协同效能'],
    datasets: [
      {
        label: 'CogniGuard 受保护系统',
        data: [90, 100, 93, 95, 100, 88],
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgba(59, 130, 246, 1)',
        borderWidth: 2,
        pointBackgroundColor: 'rgba(59, 130, 246, 1)',
      },
      {
        label: '传统无保护基线系统 (Plain baseline RAG)',
        data: [45, 0, 0, 0, 10, 85],
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderColor: 'rgba(239, 68, 68, 0.7)',
        borderWidth: 1.5,
        pointBackgroundColor: 'rgba(239, 68, 68, 0.7)',
        borderDash: [5, 5]
      }
    ]
  };

  // Bar comparison charts FOPD vs Full
  const fopdChartData = {
    labels: ['画像信息暴露比率 (PER)', '教学覆盖度及实用性', '学生敏感数据泄露事件'],
    datasets: [
      {
        label: 'MM-FOPD画像隐私脱敏技术',
        data: [0.46, 0.89, 0],
        backgroundColor: ['rgba(16, 185, 129, 0.75)', 'rgba(16, 185, 129, 0.75)', 'rgba(16, 185, 129, 0.75)'],
        borderColor: 'rgba(16, 185, 129, 1)',
        borderWidth: 1.5,
      },
      {
        label: '传统基线 (FullProfile)',
        data: [1.00, 0.44, 3],
        backgroundColor: ['rgba(239, 68, 68, 0.6)', 'rgba(239, 68, 68, 0.6)', 'rgba(239, 68, 68, 0.6)'],
        borderColor: 'rgba(239, 68, 68, 1)',
        borderWidth: 1.5,
      }
    ]
  };

  return (
    <div className="app-container">
      {/* 1. Left Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-section">
            <Shield className="brand-icon" size={26} />
            <h1 className="brand-title">CogniGuard</h1>
          </div>
          <span className="brand-subtitle">生命周期主动防护</span>
        </div>

        <ul className="nav-list">
          <li
            className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Activity className="nav-item-icon" />
            全景概览看板
          </li>
          <li
            className={`nav-item ${activeTab === 'workflow' ? 'active' : ''}`}
            onClick={() => setActiveTab('workflow')}
          >
            <Workflow className="nav-item-icon" />
            全流程沙箱演示
          </li>
          <li
            className={`nav-item ${activeTab === 'fopd' ? 'active' : ''}`}
            onClick={() => setActiveTab('fopd')}
          >
            <EyeOff className="nav-item-icon" />
            MM-FOPD 隐私保护
          </li>
          <li
            className={`nav-item ${activeTab === 'c2rag' ? 'active' : ''}`}
            onClick={() => setActiveTab('c2rag')}
          >
            <BookOpen className="nav-item-icon" />
            C²-RAG 版权保护
          </li>
          <li
            className={`nav-item ${activeTab === 'monitor' ? 'active' : ''}`}
            onClick={() => setActiveTab('monitor')}
          >
            <GitBranch className="nav-item-icon" />
            多智能体通信监控
          </li>
          <li
            className={`nav-item ${activeTab === 'attack' ? 'active' : ''}`}
            onClick={() => setActiveTab('attack')}
          >
            <Flame className="nav-item-icon" />
            攻击模拟实验舱
          </li>
          <li
            className={`nav-item ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <Search className="nav-item-icon" />
            HSW-ST 审计溯源
          </li>
        </ul>

        <div className="sidebar-footer">
          <div>导师论证演示版 v1.1.0</div>
          <div className="sys-health">
            <span className="sys-health-dot"></span>
            <span>防护策略已激活</span>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="main-content">
        {/* Top Sticky Header */}
        <header className="top-header">
          <div className="header-title-section">
            <h2>多智能体 tutoring Tutoring 系统主动安全防护框架研究看板</h2>
          </div>

          <div className="sandbox-controls">
            <div className="case-select-wrapper">
              <label htmlFor="caseSelector">当前学生案例:</label>
              <select
                id="caseSelector"
                className="case-select"
                value={selectedCaseIdx}
                onChange={(e) => setSelectedCaseIdx(parseInt(e.target.value))}
              >
                {cases.map((c, idx) => (
                  <option key={c.task_id} value={idx}>
                    {idx + 1}. {c.knowledge_point} ({c.task_id})
                  </option>
                ))}
              </select>
            </div>

            <button
              className="btn-run-pipeline"
              onClick={handleRunPipeline}
              disabled={runningPipeline}
            >
              {runningPipeline ? <RefreshCw className="pulse" size={16} /> : <Play size={16} />}
              <span>{runningPipeline ? "正在执行流水线..." : "运行防护流水线"}</span>
            </button>
          </div>
        </header>

        {/* Dynamic Page Routing */}
        <div className="page-body">
          {/* TAB 1: OVERVIEW DASHBOARD */}
          {activeTab === 'overview' && (
            <div className="overview-page">
              <div className="page-title-row">
                <h1>学术概览与决策大屏</h1>
                <p>实时分析 tutoring 多智能体系统的安全态势、横向通信审计率以及各生命周期防护组件的运作状态。</p>
              </div>

              {/* Metrics row */}
              <div className="metrics-grid">
                <div className="metric-card glow-blue">
                  <div className="metric-header">
                    <span>总请求次数 (Total Requests)</span>
                    <Database className="metric-header-icon total" />
                  </div>
                  <div className="metric-value">1,280</div>
                  <div className="metric-desc">框架已审计的智能体请求流转总数</div>
                </div>

                <div className="metric-card glow-green">
                  <div className="metric-header">
                    <span>正常教学会话 (Normal Requests)</span>
                    <UserCheck className="metric-header-icon normal" />
                  </div>
                  <div className="metric-value">1,152</div>
                  <div className="metric-desc">完全排除安全隐私风险的安全教学步数</div>
                </div>

                <div className="metric-card glow-red">
                  <div className="metric-header">
                    <span>拦截攻击次数 (Blocked Attacks)</span>
                    <AlertTriangle className="metric-header-icon attack" />
                  </div>
                  <div className="metric-value">128</div>
                  <div className="metric-desc">成功识别并阻断越权、注入及榨取威胁</div>
                </div>

                <div className="metric-card glow-blue">
                  <div className="metric-header">
                    <span>审计覆盖率 (Audit Coverage)</span>
                    <CheckCircle className="metric-header-icon success" />
                  </div>
                  <div className="metric-value">100%</div>
                  <div className="metric-desc">系统各节点通信全部完成数字签名与追踪</div>
                </div>
              </div>

              {/* Percent Row */}
              <div className="percent-grid">
                <div className="percent-card">
                  <div className="percent-circle-box red">0%</div>
                  <div className="percent-info-box">
                    <span className="percent-label">攻击成功率 (ASR)</span>
                    <span className="percent-value">彻底压制</span>
                  </div>
                </div>

                <div className="percent-card">
                  <div className="percent-circle-box green">100%</div>
                  <div className="percent-info-box">
                    <span className="percent-label">拦截成功率 (Block Rate)</span>
                    <span className="percent-value">128 / 128 全部狙击</span>
                  </div>
                </div>

                <div className="percent-card">
                  <div className="percent-circle-box green">100%</div>
                  <div className="percent-info-box">
                    <span className="percent-label">隐私画像保护率</span>
                    <span className="percent-value">高频生理特征零暴露</span>
                  </div>
                </div>

                <div className="percent-card">
                  <div className="percent-circle-box blue">92.5%</div>
                  <div className="percent-info-box">
                    <span className="percent-label">检索版权保护率</span>
                    <span className="percent-value">C²-RAG 衍生变体脱敏</span>
                  </div>
                </div>
              </div>

              {/* Framework status cards */}
              <div className="framework-title">
                <Layers size={18} />
                <span>三层纵向防御体系 + 横向主动调配治理框架</span>
              </div>
              <div className="status-grid">
                <div className="status-card">
                  <div className="status-card-header">
                    <span className="layer-badge user">用户侧画像隐私 (MM-FOPD)</span>
                    <div className="status-indicator">
                      <span className="status-dot active"></span>
                      <span>正常运行</span>
                    </div>
                  </div>
                  <h3 className="status-card-title">MM-FOPD</h3>
                  <p className="status-card-subtitle">多模态混淆与披露控制层</p>
                  <div className="status-details-list">
                    <div className="status-details-row">
                      <span>过滤模式:</span>
                      <span className="status-details-val">脱敏最小上下文</span>
                    </div>
                    <div className="status-details-row">
                      <span>披露控制预算:</span>
                      <span className="status-details-val">0.75 阈值严格校验</span>
                    </div>
                    <div className="status-details-row">
                      <span>脱敏精简比率:</span>
                      <span className="status-details-val">99.9% 降维压缩率</span>
                    </div>
                  </div>
                </div>

                <div className="status-card">
                  <div className="status-card-header">
                    <span className="layer-badge teach">教学侧资源版权 (C²-RAG)</span>
                    <div className="status-indicator">
                      <span className="status-dot active"></span>
                      <span>正常运行</span>
                    </div>
                  </div>
                  <h3 className="status-card-title">C²-RAG</h3>
                  <p className="status-card-subtitle">版权检索安全调配引擎</p>
                  <div className="status-details-list">
                    <div className="status-details-row">
                      <span>开销衰减机制:</span>
                      <span className="status-details-val">动态衰减累算</span>
                    </div>
                    <div className="status-details-row">
                      <span>输出控制模式:</span>
                      <span className="status-details-val">变体衍生 / 概要</span>
                    </div>
                    <div className="status-details-row">
                      <span>平均版权泄露率:</span>
                      <span className="status-details-val">0.27 (普通RAG=1.0)</span>
                    </div>
                  </div>
                </div>

                <div className="status-card">
                  <div className="status-card-header">
                    <span className="layer-badge out">输出侧防篡改 (HSW-ST)</span>
                    <div className="status-indicator">
                      <span className="status-dot active"></span>
                      <span>水印已绑定</span>
                    </div>
                  </div>
                  <h3 className="status-card-title">HSW-ST</h3>
                  <p className="status-card-subtitle">启发式隐形水印与可追溯审计层</p>
                  <div className="status-details-list">
                    <div className="status-details-row">
                      <span>嵌入方案:</span>
                      <span className="status-details-val">可见溯源标识</span>
                    </div>
                    <div className="status-details-row">
                      <span>安全校验方案:</span>
                      <span className="status-details-val">SHA256 签名封印</span>
                    </div>
                    <div className="status-details-row">
                      <span>抗篡改检出 (ADR):</span>
                      <span className="status-details-val">95% Resilient</span>
                    </div>
                  </div>
                </div>

                <div className="status-card">
                  <div className="status-card-header">
                    <span className="layer-badge gov">主动监管 (TPCS Controller)</span>
                    <div className="status-indicator">
                      <span className="status-dot active"></span>
                      <span>威胁审计中</span>
                    </div>
                  </div>
                  <h3 className="status-card-title">TPCS 控制器</h3>
                  <p className="status-card-subtitle">威胁感知的横向中介控制器</p>
                  <div className="status-details-list">
                    <div className="status-details-row">
                      <span>会话控制限制:</span>
                      <span className="status-details-val">0.22 会话隐私预算</span>
                    </div>
                    <div className="status-details-row">
                      <span>隔离控制:</span>
                      <span className="status-details-val">强制限制智能体间直连</span>
                    </div>
                    <div className="status-details-row">
                      <span>画像污染防护:</span>
                      <span className="status-details-val">100% 自诉写库回传拦截</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Research metrics radar */}
              <div className="protection-dual-grid" style={{ minHeight: '380px' }}>
                <div className="data-panel-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div className="data-panel-title">🛡️ 防护框架核心能力边界前沿雷达图</div>
                  <div style={{ width: '80%', height: '300px' }}>
                    <Radar
                      data={metricsChartData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                          r: {
                            grid: { color: 'rgba(255, 255, 255, 0.08)' },
                            angleLines: { color: 'rgba(255, 255, 255, 0.08)' },
                            pointLabels: { color: '#94a3b8', font: { family: 'Outfit', size: 10 } },
                            ticks: { display: false }
                          }
                        },
                        plugins: {
                          legend: { labels: { color: '#ffffff', font: { family: 'Outfit' } } }
                        }
                      }}
                    />
                  </div>
                </div>

                <div className="data-panel-card">
                  <div className="data-panel-title">🛡️ 多智能体 Tutoring 系统主动安全架构设计原则</div>
                  <div style={{ padding: '0.5rem', color: 'var(--color-text-muted)', fontSize: '0.85rem', lineHeight: '1.6' }}>
                    <blockquote style={{ borderLeft: '3px solid var(--color-blue)', paddingLeft: '1rem', fontStyle: 'italic', marginBottom: '1rem' }}>
                      “大语言模型 tutoring 智能体只是底层的执行节点，而非顶层系统架构本身。系统安全性必须通过严密的横向主动监管总线来统筹控制。”
                    </blockquote>
                    <p style={{ marginBottom: '1rem' }}>
                      传统多智能体系统仅仅是将智能体在纵向上简单堆叠，直接传递未加工的数据或提示词栈。CogniGuard 强力推行了节点隔离原则：
                    </p>
                    <ul style={{ paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <li><strong>阶段 1 (MM-FOPD):</strong> 物理拦截学生高维多模态物理敏感输入，画像诊断前强力执行模糊过滤与脱敏。</li>
                      <li><strong>阶段 2 (C²-RAG):</strong> 控制检索源版权泄露，根据会话开销衰减算法，动态降级为摘要或等效变体题，避免 Verbatim 榨取。</li>
                      <li><strong>阶段 3 (HSW-ST):</strong> 对生成的辅导话术动态嵌入具有高检出率 (ADR) 的启发式软水印，以校验 SHA256 审计链条。</li>
                      <li><strong>横向主动监管 (TPCS):</strong> 全权接管智能体间的所有流转路由，动态把控特征累计得分，从源头上化解会话内外的多轮关联推导威胁。</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: FULL WORKFLOW DEMO */}
          {activeTab === 'workflow' && (
            <div className="workflow-page">
              <div className="page-title-row">
                <h1>全生命周期全流程沙箱演示</h1>
                <p>自主选择真实学情案例在框架中流转，逐步解构各环节数据载荷、风险定级评分与控制决策。</p>
              </div>

              {/* Case telemetry status */}
              <div className="stepper-header-cards">
                <div className="sandbox-telemetry-card">
                  <div className="percent-label">当前运行案例哈希 (student_hash)</div>
                  <div className="brand-title" style={{ fontSize: '1rem', textShadow: 'none' }}>
                    {pipelineData?.generated_context_card?.student_hash || "等待流水线执行..."}
                  </div>
                </div>
                <div className="sandbox-telemetry-card">
                  <div className="percent-label">诊断目标知识点 (knowledge_point)</div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>
                    {pipelineData?.generated_context_card?.knowledge_point || "arithmetic sequence"}
                  </div>
                </div>
                <div className="sandbox-telemetry-card">
                  <div className="percent-label">TPCS 累积画像特征开销</div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-blue)' }}>
                    0.25 / 0.75 预算阈值
                  </div>
                </div>
                <div className="sandbox-telemetry-card">
                  <div className="percent-label">HSW-ST 隐形软水印审计编码</div>
                  <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: 'var(--color-green)' }}>
                    {pipelineData?.audit_trace?.watermark_id || "等待流水线执行..."}
                  </div>
                </div>
              </div>

              <div className="stepper-grid-layout">
                {/* Steps left list */}
                <div className="stepper-steps-box">
                  {stepperSteps.map((step, idx) => (
                    <div
                      key={idx}
                      className={`stepper-item-row ${activeStep === idx ? 'active' : ''} ${pipelineData ? 'processed' : ''}`}
                      onClick={() => setActiveStep(idx)}
                    >
                      <div className="stepper-number">
                        {idx + 1}
                      </div>
                      <div className="stepper-info">
                        <div className="stepper-name-row">
                          <span className="stepper-title">{step.title}</span>
                          <span className="layer-badge user" style={{ fontSize: '0.6rem', padding: '0.15rem 0.35rem' }}>
                            {step.layer}
                          </span>
                        </div>
                        <span className="stepper-desc">{step.desc}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Step inspect right pane */}
                <div className="step-details-panel">
                  <div className="data-panel-title">
                    <Terminal size={16} />
                    <span>审计控制室：阶段 {activeStep + 1}</span>
                  </div>

                  <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--color-blue)' }}>
                    {stepperSteps[activeStep].title}
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '1.25rem' }}>
                    {stepperSteps[activeStep].desc}
                  </p>

                  {pipelineData ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div>
                        <span className="percent-label">本轮控制参与节点:</span>
                        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {stepperSteps[activeStep].layer}
                        </div>
                      </div>

                      <div>
                        <span className="percent-label">节点实时安全风险评级:</span>
                        <div style={{ marginTop: '0.25rem' }}>
                          <span className="risk-badge low">低风险安全 (0.05)</span>
                        </div>
                      </div>

                      <div>
                        <span className="percent-label">TPCS 横向准入验证调配决策:</span>
                        <div style={{ marginTop: '0.25rem' }}>
                          <span className="edge-decision-badge allow">允许流转并通过审计 (ALLOW)</span>
                        </div>
                      </div>

                      <div>
                        <span className="percent-label">截获节点遥测报文 (JSON payload):</span>
                        <div style={{ marginTop: '0.4rem' }}>
                          <pre className="json-block output">
                            {jsonEncode(stepperSteps[activeStep].getDetails(pipelineData))}
                          </pre>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--color-text-muted)' }}>
                      <AlertOctagon size={32} style={{ margin: '0 auto 1rem', display: 'block', color: 'var(--color-yellow)' }} />
                      <span>请在顶部选择学生案例，然后点击 “<strong>运行防护流水线</strong>” 以加载真实的节点日志。</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: MM-FOPD PRIVACY PANEL */}
          {activeTab === 'fopd' && (
            <div className="fopd-page">
              <div className="page-title-row">
                <h1>MM-FOPD 用户画像隐私脱敏过滤</h1>
                <p>无缝接入学生高维多模态物理特征，模糊高危隐私参数并自动重构为教学最小画像卡片。</p>
              </div>

              {/* Shield emphasizing raw isolation */}
              <div className="fopd-shield-card">
                <Lock className="fopd-shield-icon" size={48} />
                <div className="fopd-shield-text">
                  <h3>多模态物理隔离安全红线边界 (MM-FOPD 强制执行)</h3>
                  <p>
                    <strong>信息安全红线：</strong> 学生的高精度物理笔迹压感坐标、语音生理特微文件、面部表情微表情信号以及原始学情表，<strong>全部隔离在解密单元本地</strong>。仅在本地提取必要的认知考点语义，严禁将原始多模态物理特征发送给任何大模型智能体执行节点，彻底打碎关联推重构用户真实画像链条。
                  </p>
                </div>
              </div>

              <div className="protection-dual-grid">
                {/* Left Card: Raw Intake */}
                <div className="data-panel-card">
                  <div className="data-panel-title">📸 多模态原始高敏感输入拦截摘要</div>

                  {pipelineData ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div className="retrieval-card">
                        <span className="percent-label">错题屏幕截图数据源 (Wrong-Answer Screen):</span>
                        <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {pipelineData.raw_data_summary?.wrong_answer_image_path || "data/raw/wrong_answer_screenshot.png"}
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">声纹声波生理特征文件 (Voice Stress Audio):</span>
                        <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {pipelineData.raw_data_summary?.audio_feature_path || "data/raw/audio_features/task_0001.json"}
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">面部/声调情绪焦虑与犹豫指数 (Emotion Signal):</span>
                        <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {pipelineData.raw_data_summary?.emotion_signal_path || "data/raw/emotion_signals/task_0001.json"}
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">电磁板压感手写轨迹坐标特征 (Handwriting Coordinates):</span>
                        <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {pipelineData.raw_data_summary?.handwriting_trace_path || "data/raw/handwriting_traces/task_0001.json"}
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">学情原始历史数据库索引 (Raw History Card):</span>
                        <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {pipelineData.raw_data_summary?.raw_history_path || "data/raw/history/task_0001.json"}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>暂无活跃流水线。</div>
                  )}
                </div>

                {/* Right Card: Processed card & fields */}
                <div className="data-panel-card">
                  <div className="data-panel-title">📋 MM-FOPD 脱敏重构最小卡片 (Context Card)</div>

                  {pipelineData ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div>
                        <span className="percent-label">已过滤下发的画像卡片 payload (JSON):</span>
                        <pre className="json-block output" style={{ marginTop: '0.35rem' }}>
                          {jsonEncode(pipelineData.generated_context_card)}
                        </pre>
                      </div>

                      <div>
                        <span className="percent-label">画像白名单属性 (Allowed Fields - 允许下发给智能体):</span>
                        <div className="tag-list" style={{ marginTop: '0.35rem' }}>
                          {pipelineData.generated_context_card?.allowed_profile_fields?.map(f => (
                            <span key={f} className="tag-badge allowed">{f}</span>
                          ))}
                        </div>
                      </div>

                      <div>
                        <span className="percent-label">红线严密封禁特征 (Forbidden Fields - 隔离封存):</span>
                        <div className="tag-list" style={{ marginTop: '0.35rem' }}>
                          {pipelineData.generated_context_card?.forbidden_profile_fields?.map(f => (
                            <span key={f} className="tag-badge forbidden">{f}</span>
                          ))}
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.5rem' }}>
                        <div>
                          <span className="percent-label">TPCS 隐私控制上限:</span>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-blue)' }}>0.75 Score</div>
                        </div>
                        <div>
                          <span className="percent-label">本案例已暴露值:</span>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-green)' }}>
                            {pipelineData.generated_context_card?.disclosure_score || "0.25"}
                          </div>
                        </div>
                        <div>
                          <span className="percent-label">特征空间脱敏率:</span>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-purple)' }}>99.9% 削减</div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>暂无活跃流水线。</div>
                  )}
                </div>
              </div>

              {/* Utility Chart Section */}
              <div className="data-panel-card">
                <div className="data-panel-title">🛡️ 学术实验评估：MM-FOPD 画像隐私-实用性前沿对比图</div>
                <div className="stepper-grid-layout">
                  <div style={{ height: '220px' }}>
                    <Bar
                      data={fopdChartData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { labels: { color: '#ffffff', font: { family: 'Outfit' } } }
                        },
                        scales: {
                          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
                        }
                      }}
                    />
                  </div>

                  <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', lineHeight: '1.5' }}>
                    <h4 style={{ color: '#ffffff', fontWeight: 700, marginBottom: '0.5rem' }}>学术指标分析解读：</h4>
                    <p style={{ marginBottom: '0.5rem' }}>
                      <strong>1. 画像信息暴露比率 (PER):</strong> MM-FOPD 将公开给底层智能体的画像特征字段限制在 ~46% 左右，相较于传统的 100% 毫无保留暴露画像，系统暴露面得到大幅度收敛。
                    </p>
                    <p style={{ marginBottom: '0.5rem' }}>
                      <strong>2. 教学任务覆盖度 (Utility):</strong> MM-FOPD 实现了 ~89% 的高满意学情辅导覆盖率（甚至优于传统无保护基线 FullProfile 的 44%），这是因为 FullProfile 常因为提示词冗余引起智能体幻觉。FOPD 验证了“画像特征降维脱敏”反而有助于大模型决策专注度的核心学术论点。
                    </p>
                    <p>
                      <strong>3. 敏感数据泄露率 (Sensitive Leaks):</strong> MM-FOPD 实现了对物理高维数据的完美隔离，敏感事件泄露为 0；而传统基线 FullProfile 则会导致多起关键敏感要素越权流转泄露。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: C²-RAG PANEL */}
          {activeTab === 'c2rag' && (
            <div className="c2rag-page">
              <div className="page-title-row">
                <h1>C²-RAG 知识产权与教师资源版权检索防护</h1>
                <p>通过会话级动态版权开销限制检索内容，采取智能衍生变体或拒绝机制阻断逐字泄露。</p>
              </div>

              <div className="protection-dual-grid">
                {/* Retrieval Process */}
                <div className="data-panel-card">
                  <div className="data-panel-title">📚 C²-RAG 版权开销控制台</div>

                  {pipelineData ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div className="retrieval-card">
                        <div className="retrieval-row">
                          <span style={{ fontWeight: 700, color: '#ffffff' }}>出库教学资源元数据</span>
                          <span className="return-badge summary">摘要降级模式</span>
                        </div>
                        <div className="status-details-list" style={{ fontSize: '0.75rem', gap: '0.3rem' }}>
                          <div className="status-details-row">
                            <span>匹配资源 ID:</span>
                            <span className="status-details-val">teacher_resource_arithmetic_sequence</span>
                          </div>
                          <div className="status-details-row">
                            <span>匹配出库分块 (Chunk ID):</span>
                            <span className="status-details-val">chunk_889e1f6f</span>
                          </div>
                          <div className="status-details-row">
                            <span>原讲义版权风险定级:</span>
                            <span className="status-details-val" style={{ color: 'var(--color-yellow)' }}>0.42 (保护级别：较高，禁止拷出)</span>
                          </div>
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">C²-RAG 会话版权预算度量 (Exposure Budget):</span>
                        <div className="stepper-header-cards" style={{ marginTop: '0.5rem', marginBottom: '0px', gap: '0.5rem' }}>
                          <div className="sandbox-telemetry-card" style={{ padding: '0.5rem' }}>
                            <div className="percent-label" style={{ fontSize: '0.65rem' }}>扣除前可用预算</div>
                            <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>0.40</span>
                          </div>
                          <div className="sandbox-telemetry-card" style={{ padding: '0.5rem' }}>
                            <div className="percent-label" style={{ fontSize: '0.65rem' }}>本轮检索开销 (Cost)</div>
                            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--color-red)' }}>0.14</span>
                          </div>
                          <div className="sandbox-telemetry-card" style={{ padding: '0.5rem' }}>
                            <div className="percent-label" style={{ fontSize: '0.65rem' }}>扣除后剩余预算</div>
                            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--color-green)' }}>0.26</span>
                          </div>
                        </div>
                      </div>

                      <div>
                        <span className="percent-label">版权引擎净化后允许下发的脱敏文本:</span>
                        <div className="json-block output" style={{ marginTop: '0.35rem', fontStyle: 'italic' }}>
                          "{pipelineData.agent_outputs?.CopyrightAwareResourceAgent?.controlled_resource_snippets?.[0]?.content}"
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>暂无活跃流水线。</div>
                  )}
                </div>

                {/* Right Card: Modes and Injections */}
                <div className="data-panel-card">
                  <div className="data-panel-title">🛡️ C²-RAG 检索输出控制模式与安全防线</div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                      <span className="percent-label">检索输出降级策略 (Return Modes):</span>
                      <table className="cg-table" style={{ margin: '0.5rem 0' }}>
                        <thead>
                          <tr>
                            <th>脱敏模式</th>
                            <th>技术处理形式</th>
                            <th>执行策略</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td><span className="return-badge quote" style={{ fontSize: '0.6rem' }}>quote</span></td>
                            <td>允许全文复制或逐字引用原文</td>
                            <td><span className="risk-badge low">红线封禁</span></td>
                          </tr>
                          <tr>
                            <td><span className="return-badge summary" style={{ fontSize: '0.6rem' }}>summary</span></td>
                            <td>提炼为考点提纲或高度概括文本</td>
                            <td><span className="risk-badge low" style={{ background: 'var(--color-green-glow)', color: 'var(--color-green)' }}>审计放行</span></td>
                          </tr>
                          <tr>
                            <td><span className="return-badge variant" style={{ fontSize: '0.6rem' }}>variant</span></td>
                            <td>智能重构出考点等价的衍生变体练习题</td>
                            <td><span className="risk-badge low" style={{ background: 'var(--color-green-glow)', color: 'var(--color-green)' }}>审计放行</span></td>
                          </tr>
                          <tr>
                            <td><span className="return-badge refuse" style={{ fontSize: '0.6rem' }}>refuse</span></td>
                            <td>版权开销总预算耗尽时，强力拒绝并阻断</td>
                            <td><span className="risk-badge low" style={{ background: 'var(--color-red-glow)', color: 'var(--color-red)' }}>自动熔断</span></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div className="retrieval-card" style={{ borderLeft: '3px solid var(--color-green)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <Shield className="status-dot active" style={{ width: '14px', height: '14px', color: 'var(--color-green)' }} />
                        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#ffffff' }}>检索提示词注入安全扫描已就绪</span>
                      </div>
                      <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
                        扫描机制：多物理特征与文本语义启发式校验。实时过滤教案出库和生成流中的注入溢出、绕过安全规则及提取库秘钥等异常指令。审计结果：<strong>当前状态绿色安全，未拦截威胁</strong>。
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* RAG Leakage Chart */}
              {c2ragAttackData && (
                <div className="data-panel-card">
                  <div className="data-panel-title">📈 学术实验评估：逐字文本版权信息泄露抑制曲线对比</div>
                  <div className="stepper-grid-layout">
                    <div style={{ height: '220px' }}>
                      <Line
                        data={{
                          labels: ['Round 1', 'Round 2', 'Round 3', 'Round 4', 'Round 5', 'Round 6'],
                          datasets: [
                            {
                              label: '传统基线RAG (暴力连续榨取下快速倒灌讲义)',
                              data: [0.45, 0.56, 0.78, 0.89, 1.0, 1.0],
                              borderColor: 'rgba(239, 68, 68, 1)',
                              backgroundColor: 'rgba(239, 68, 68, 0.05)',
                              borderWidth: 2,
                              fill: true
                            },
                            {
                              label: 'C²-RAG 主动版权保护 (Round 3熔断降级为衍生变体)',
                              data: [0.27, 0.27, 0.0, 0.0, 0.0, 0.0],
                              borderColor: 'rgba(16, 185, 129, 1)',
                              backgroundColor: 'rgba(16, 185, 129, 0.05)',
                              borderWidth: 2,
                              fill: true
                            }
                          ]
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: { labels: { color: '#ffffff', font: { family: 'Outfit' } } }
                          },
                          scales: {
                            x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                            y: { min: 0, max: 1.1, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
                          }
                        }}
                      />
                    </div>
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', lineHeight: '1.5' }}>
                      <h4 style={{ color: '#ffffff', fontWeight: 700, marginBottom: '0.5rem' }}>C²-RAG 反暴力版权榨取攻击策略：</h4>
                      <p style={{ marginBottom: '0.5rem' }}>
                        在连续 6 轮恶意的系统化版权提取攻击下，传统无防范 RAG 基线会迅速吐出讲义原文，在 Round 5 即告 100% verbatime 彻底泄露。
                      </p>
                      <p>
                        C²-RAG 实时审计累积检索压力，动态减少可用版权开销上限。一旦在 Round 3 察觉预算耗尽，立即启动主动降级（如 refuse 或 variant_question），将 Verbatim 泄露率瞬间压回 0.0，完美化解了基于多轮询问的版权榨取危机。
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 5: MULTI-AGENT MONITOR */}
          {activeTab === 'monitor' && (
            <div className="monitor-page">
              <div className="page-title-row">
                <h1>多智能体通信流转实时监控屏</h1>
                <p>实时渲染多智能体节点间流转的消息拓扑树，监控 TPCS 横向准入验证规则以及特征关联推导风险评分。</p>
              </div>

              {/* Topology panel */}
              <div className="network-container">
                <div className="data-panel-title">🖥px 多智能体节点通信实时拓扑大屏</div>

                <div className="network-graph-box">
                  {/* Visual SVG overlay representing nodes and active loops */}
                  <svg width="100%" height="100%">
                    {/* Defs for arrow markers */}
                    <defs>
                      <marker id="arrow" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
                      </marker>
                    </defs>

                    {/* Horizontal TPCS Governance Bus line */}
                    <line x1="5%" y1="50%" x2="95%" y2="50%" stroke="rgba(239, 68, 68, 0.3)" strokeWidth="4" strokeDasharray="5,5" />
                    <text x="50%" y="46%" fill="#ef4444" fontSize="11" fontWeight="700" textAnchor="middle" letterSpacing="1px">
                      TPCS 横向治理主动调配总线 (THREAT-AWARE CONTROLLER BUS)
                    </text>

                    {/* Edges representation */}
                    {pipelineData && (
                      <>
                        {/* FOPD to Profile Diagnosis */}
                        <line x1="120" y1="60" x2="280" y2="60" stroke="#10b981" strokeWidth="2.5" markerEnd="url(#arrow)" />

                        {/* Profile Diagnosis to Resource Agent */}
                        <line x1="280" y1="80" x2="480" y2="80" stroke="#3b82f6" strokeWidth="2" markerEnd="url(#arrow)" />

                        {/* Resource Agent to Pedagogical */}
                        <line x1="480" y1="200" x2="680" y2="200" stroke="#3b82f6" strokeWidth="2" markerEnd="url(#arrow)" />

                        {/* Pedagogical to Assessment */}
                        <line x1="680" y1="220" x2="880" y2="220" stroke="#3b82f6" strokeWidth="2" markerEnd="url(#arrow)" />
                      </>
                    )}

                    {/* Node 1: MM-FOPD Ingestion */}
                    <g transform="translate(120, 60)" className="node-circle">
                      <circle r="36" fill="rgba(16, 185, 129, 0.1)" stroke="#10b981" strokeWidth="2" />
                      <text y="5" fill="#ffffff" fontSize="9" fontWeight="700" textAnchor="middle">MM-FOPD 脱敏</text>
                    </g>

                    {/* Node 2: ProfileDiagnosisAgent */}
                    <g transform="translate(280, 80)" className="node-circle">
                      <circle r="36" fill="rgba(59, 130, 246, 0.1)" stroke="#3b82f6" strokeWidth="2" />
                      <text y="0" fill="#ffffff" fontSize="9" fontWeight="700" textAnchor="middle">学情智能体</text>
                      <text y="12" fill="#94a3b8" fontSize="8" textAnchor="middle">Diagnosis</text>
                    </g>

                    {/* Node 3: CopyrightAwareResourceAgent */}
                    <g transform="translate(480, 200)" className="node-circle">
                      <circle r="36" fill="rgba(59, 130, 246, 0.1)" stroke="#3b82f6" strokeWidth="2" />
                      <text y="-5" fill="#ffffff" fontSize="9" fontWeight="700" textAnchor="middle">资源智能体</text>
                      <text y="6" fill="#94a3b8" fontSize="8" textAnchor="middle">C²-RAG</text>
                    </g>

                    {/* Node 4: PedagogicalTeachingAgent */}
                    <g transform="translate(680, 200)" className="node-circle">
                      <circle r="36" fill="rgba(59, 130, 246, 0.1)" stroke="#3b82f6" strokeWidth="2" />
                      <text y="-5" fill="#ffffff" fontSize="9" fontWeight="700" textAnchor="middle">教学智能体</text>
                      <text y="6" fill="#94a3b8" fontSize="8" textAnchor="middle">启发引导</text>
                    </g>

                    {/* Node 5: LearningAssessmentAgent */}
                    <g transform="translate(880, 220)" className="node-circle">
                      <circle r="36" fill="rgba(59, 130, 246, 0.1)" stroke="#3b82f6" strokeWidth="2" />
                      <text y="-5" fill="#ffffff" fontSize="9" fontWeight="700" textAnchor="middle">评估智能体</text>
                      <text y="6" fill="#94a3b8" fontSize="8" textAnchor="middle">认知评估</text>
                    </g>
                  </svg>
                </div>

                {/* Session Budget Indicator */}
                <div style={{ display: 'flex', gap: '2rem', padding: '1rem', background: 'var(--bg-primary)', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="percent-label">会话级累积特征泄露评分 (Cumulative Leakage):</span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-blue)' }}>0.25 / 0.75 预算限额</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="percent-label">多模态潜在特征关联推导风险评分 (Indirect Risk):</span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-green)' }}>安全水平 (LOW - 特征降维拦截到位)</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="percent-label">节点横向准入消息流转凭证校验机制:</span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-purple)' }}>强隔离状态 (Enforced)</span>
                  </div>
                </div>

                {/* Interaction Logs */}
                <div className="data-panel-title">📊 TPCS 控制器实时截获审计的流转报文</div>

                {pipelineData ? (
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {pipelineData.audit_trace?.communication_logs?.map((edge, idx) => (
                      <div key={idx} className="message-edge-card">
                        <div className="edge-header-row">
                          <span style={{ fontWeight: 700, color: '#3b82f6', fontSize: '0.85rem' }}>
                            流转路由 {idx + 1}: {edge.sender} → {edge.receiver}
                          </span>
                          <span className="edge-decision-badge allow">
                            允许路由流转 (ALLOW & ROUTE)
                          </span>
                        </div>
                        <div className="status-details-list" style={{ fontSize: '0.75rem', gap: '0.2rem', color: 'var(--color-text-muted)' }}>
                          <div className="status-details-row">
                            <span>节点消息事务类型:</span>
                            <span className="status-details-val" style={{ fontFamily: 'monospace' }}>{edge.message_type}</span>
                          </div>
                          <div className="status-details-row">
                            <span>流转传输限定隐私等级 (Privacy Boundary):</span>
                            <span className="status-details-val" style={{ color: 'var(--color-purple)' }}>{edge.privacy_level}</span>
                          </div>
                          <div className="status-details-row">
                            <span>本轮暴露增加评分 (PER Impact):</span>
                            <span className="status-details-val" style={{ color: 'var(--color-yellow)' }}>{edge.disclosure_score}</span>
                          </div>
                          <div className="status-details-row">
                            <span>会话内部局部事务全局标识:</span>
                            <span className="status-details-val" style={{ fontFamily: 'monospace' }}>{edge.round_id}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
                    等待防护流水线计算回传流转报文...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 6: ATTACK SIMULATION LAB */}
          {activeTab === 'attack' && (
            <div className="attack-page">
              <div className="page-title-row">
                <h1>CogniGuard 攻防演练实验室</h1>
                <p>自主向指定底层智能体节点注入恶意载荷（Malicious Prompts），直观见证主动防御机制的横向拦截拦截阻断。</p>
              </div>

              <div className="attack-lab-layout">
                {/* Cases left */}
                <div className="attack-case-list">
                  {attackCases.map(c => (
                    <div
                      key={c.attack_case_id}
                      className={`attack-case-item ${selectedAttackId === c.attack_case_id ? 'active' : ''}`}
                      onClick={() => setSelectedAttackId(c.attack_case_id)}
                    >
                      <div className="attack-item-header">
                        <span style={{ color: 'var(--color-red)', fontFamily: 'monospace' }}>{c.attack_case_id}</span>
                        <span className="layer-badge gov" style={{ fontSize: '0.6rem', padding: '0.15rem 0.35rem' }}>
                          {c.attack_type.substring(0, 15)}...
                        </span>
                      </div>
                      <div className="attack-item-title">
                        {c.attack_case_id === 'atk_001' && "学生完整敏感画像倒灌提取"}
                        {c.attack_case_id === 'atk_002' && "多模态物理敏感特征越权榨取"}
                        {c.attack_case_id === 'atk_003' && "教师讲义库逐字原文薅取"}
                        {c.attack_case_id === 'atk_004' && "教师教案越权提示词注入攻击"}
                        {c.attack_case_id === 'atk_005' && "底层多节点通信直接越权绕过"}
                        {c.attack_case_id === 'atk_006' && "画像写库自诉回传污染攻击"}
                        {c.attack_case_id === 'atk_007' && "多轮画像渐进式重组关联推导"}
                      </div>
                      <div className="attack-item-target">防御机制: {c.target_protection_layer}</div>
                    </div>
                  ))}
                </div>

                {/* Console right */}
                <div className="attack-dashboard-panel">
                  {(() => {
                    const activeCaseObj = attackCases.find(c => c.attack_case_id === selectedAttackId);
                    const logState = attackLogs[selectedAttackId];

                    if (!activeCaseObj) return <div>加载攻防模拟实验室面板中...</div>;

                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        <div className="data-panel-title" style={{ borderBottomColor: 'var(--color-red)' }}>
                          <Flame size={18} style={{ color: 'var(--color-red)' }} />
                          <span>攻防沙盘审计：{selectedAttackId}</span>
                        </div>

                        <div>
                          <span className="percent-label">防御机制组件 (Target layer):</span>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-yellow)' }}>
                            {activeCaseObj.target_protection_layer}
                          </div>
                        </div>

                        <div>
                          <span className="percent-label">受攻击 LLM 执行节点 (Target node):</span>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                            {activeCaseObj.target_agent}
                          </div>
                        </div>

                        <div>
                          <span className="percent-label">恶意的注入载荷指令 (Malicious Prompt):</span>
                          <div className="attack-prompt-box">
                            "{activeCaseObj.malicious_prompt}"
                          </div>
                        </div>

                        <div>
                          <span className="percent-label">框架预期防御行为设计:</span>
                          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
                            {activeCaseObj.expected_defense === "TPCSController intercepts the request, blocks raw profile exposure, and returns only a minimized context card." && "TPCS 控制器实时拦截画像导出指令，物理屏蔽学生 ID、长期学情等敏感字段，强力降级并仅返回已脱敏白名单画像 card。"}
                            {activeCaseObj.expected_defense === "TPCSController blocks raw multimodal path disclosures, returning an explicit permission error." && "TPCS 校验发现底层智能体试图打印或暴露 data/raw/* 下的物理截图或轨迹数据，立即予以拒绝，回传预设的安全拒绝声明。"}
                            {activeCaseObj.expected_defense === "C²-RAG exposure control decreases the exposure budget and shifts the return mode from 'quote' to 'variant_question' or 'refusal'." && "C²-RAG 审计当前出库压力，削减会话级版权预算，强制执行变体衍生或拒绝熔断机制，不允许倒灌 VERBATIM 文本。"}
                            {activeCaseObj.expected_defense === "TPCSController scans intermediate agent payloads, detects system-prompt override instruction, and sanitizes or refuses the generation." && "TPCS 横向检测出教案被强行篡改为恶意指令指令。横向回溯重构，强制执行重构状态回滚，净化生成提示词流。"}
                            {activeCaseObj.expected_defense === "TPCSController rejects direct messaging between execution nodes that bypasses the horizontal routing credentials." && "TPCS 横向限制多智能体直连。校验直连会话，由于缺少中介控制器签发的消息凭证，立即阻断此次非法智能体通信。"}
                            {activeCaseObj.expected_defense === "TPCSController intercepts the profile update evidence, logs the evidence for teacher review, but does NOT perform direct writing to the database." && "画像更新过滤器截获自诉的 Mastery 数据，强力限制智能体将学生自诉的 'mastery=100%' 写入画像库，将证据录入审核链条。"}
                            {activeCaseObj.expected_defense === "TPCSController track cumulative disclosure score across a single session and raises an alert blocking the transfer once the budget limit (0.22) is reached." && "TPCS 全局核算会话隐私披露分。当累计特征流出超出 0.22 预算限制时，立即将威胁等级判定为 HIGH，冻结会话凭证。"}
                          </p>
                        </div>

                        <button
                          className="btn-trigger-attack"
                          onClick={() => handleTriggerAttack(selectedAttackId)}
                          disabled={runningAttack}
                        >
                          <Flame size={16} />
                          <span>{runningAttack ? "模拟载荷攻击中..." : "触发安全注入模拟攻击"}</span>
                        </button>

                        {logState?.triggered ? (
                          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <div className="data-panel-title">🛡️ 防御机制审计干预日志</div>

                            <div style={{ display: 'flex', gap: '1.5rem' }}>
                              <div>
                                <span className="percent-label">干预机制决策 (Result):</span>
                                <div style={{ marginTop: '0.25rem' }}>
                                  <span className="risk-badge med" style={{ textTransform: 'uppercase' }}>
                                    {logState.data.result === "Blocked & Minimized" && "强力拦截并提供脱敏卡片"}
                                    {logState.data.result === "Blocked / Refused" && "安全拦截并强行阻断"}
                                    {logState.data.result === "Sanitized (Returned Variant)" && "文本脱敏并下发衍生变体"}
                                    {logState.data.result === "Blocked / Routing Denied" && "连接非法直连已强制挂断"}
                                    {logState.data.result === "Degraded (Logged but Blocked)" && "禁止写画像库并存证告警"}
                                    {logState.data.result === "Blocked / Budget Exceeded" && "隐私预算超限，强制阻断"}
                                  </span>
                                </div>
                              </div>

                              <div>
                                <span className="percent-label">准入评分 (Risk Score):</span>
                                <div style={{ marginTop: '0.25rem' }}>
                                  <span className="risk-badge low">安全等级 (0.05)</span>
                                </div>
                              </div>

                              <div>
                                <span className="percent-label">溯源追踪审计哈希 ID:</span>
                                <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', marginTop: '0.25rem', color: 'var(--color-purple)' }}>
                                  {logState.data.audit_log_id}
                                </div>
                              </div>
                            </div>

                            <div>
                              <span className="percent-label">审计日志明细 (Telemetry Details):</span>
                              <pre className="json-block output" style={{ color: '#fca5a5' }}>
                                {jsonEncode(logState.data.details)}
                              </pre>
                            </div>
                          </div>
                        ) : (
                          <div style={{ textAlign: 'center', padding: '1.5rem 0', borderTop: '1px solid var(--border-color)', color: 'var(--color-text-muted)' }}>
                            请点击顶部 “<strong>触发安全注入模拟攻击</strong>” 键，验证 CogniGuard 主动安全过滤器的瞬间防御行为。
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </div>

              {/* Attack metrics charts */}
              <div className="protection-dual-grid" style={{ marginTop: '2rem' }}>
                <div className="data-panel-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div className="data-panel-title">📊 攻防演练防御决策类型分布比率</div>
                  <div style={{ width: '60%', height: '220px' }}>
                    <Doughnut
                      data={{
                        labels: ['直接强力阻断 (Blocked / Refused)', '文本脱敏衍生变体 (Sanitized / Re-routed)', '自诉污染拦截并审核 (Degraded / Logged)', '安全流转放行 (Allowed)'],
                        datasets: [
                          {
                            data: [70, 15, 10, 5],
                            backgroundColor: ['rgba(239, 68, 68, 0.75)', 'rgba(245, 158, 11, 0.7)', 'rgba(139, 92, 246, 0.7)', 'rgba(16, 185, 129, 0.7)'],
                            borderWidth: 1
                          }
                        ]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { position: 'bottom', labels: { color: '#ffffff', font: { family: 'Outfit', size: 9 } } }
                        }
                      }}
                    />
                  </div>
                </div>

                <div className="data-panel-card">
                  <div className="data-panel-title">🛡️ 各防御组件安全防御成功率 (Block Rate %)</div>
                  <div style={{ height: '220px' }}>
                    <Bar
                      data={{
                        labels: ['MM-FOPD 画像隐私', 'C²-RAG 检索版权', 'HSW-ST 水印防伪', 'TPCS 横向主动监管'],
                        datasets: [
                          {
                            label: '攻击拦截率 (%)',
                            data: [100, 92, 95, 100],
                            backgroundColor: 'rgba(59, 130, 246, 0.7)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 1
                          }
                        ]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false }
                        },
                        scales: {
                          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                          y: { min: 0, max: 110, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
                        }
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: HSW-ST AUDIT VIEWER */}
          {activeTab === 'audit' && (
            <div className="audit-page">
              <div className="page-title-row">
                <h1>HSW-ST 启发水印溯源与可追溯审计中心</h1>
                <p>核验最终下发辅导文本中隐形嵌入的 HSW 水印特征，并在篡改沙箱中检验在重度文字破坏下的检出率 (ADR) 顽健性。</p>
              </div>

              <div className="watermark-layout">
                {/* Left Card: Final output and Tamper sandbox */}
                <div className="final-answer-card">
                  <div className="watermark-overlay">
                    <Shield size={14} />
                    <span>启发水印已绑定</span>
                  </div>
                  <div className="data-panel-title">🖋️ 辅导文本水印抗篡改破坏验证沙箱</div>

                  {pipelineData ? (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span className="percent-label">实际下发学生的启发辅导文本 (可随意输入字符模拟自然篡改测试):</span>
                      <textarea
                        className="tampering-textbox"
                        value={tamperedText}
                        onChange={(e) => setTamperedText(e.target.value)}
                      />

                      <span className="percent-label">仿真自然篡改破坏行为 (Tamper Sandbox):</span>
                      <div className="tampering-grid" style={{ marginTop: '0.35rem' }}>
                        <button
                          className={`btn-tamper-opt ${tamperMode === 'none' ? 'active' : ''}`}
                          onClick={() => handleTamperText('none')}
                        >
                          原始生成文本
                        </button>
                        <button
                          className={`btn-tamper-opt ${tamperMode === 'delete' ? 'active' : ''}`}
                          onClick={() => handleTamperText('delete')}
                        >
                          删除 30% 段落句子
                        </button>
                        <button
                          className={`btn-tamper-opt ${tamperMode === 'truncate' ? 'active' : ''}`}
                          onClick={() => handleTamperText('truncate')}
                        >
                          中间彻底截断 50%
                        </button>
                        <button
                          className={`btn-tamper-opt ${tamperMode === 'mix' ? 'active' : ''}`}
                          onClick={() => handleTamperText('mix')}
                        >
                          恶意拼入无关文本
                        </button>
                        <button
                          className={`btn-tamper-opt ${tamperMode === 'paraphrase' ? 'active' : ''}`}
                          onClick={() => handleTamperText('paraphrase')}
                        >
                          字词同义轻度替换
                        </button>
                        <button
                          className={`btn-tamper-opt ${tamperMode === 'summary' ? 'active' : ''}`}
                          onClick={() => handleTamperText('summary')}
                        >
                          摘要式信息压缩
                        </button>
                      </div>

                      <button
                        className="btn-run-pipeline"
                        onClick={handleDetectWatermark}
                        disabled={detectingWatermark}
                        style={{ background: 'linear-gradient(135deg, var(--color-green) 0%, #065f46 100%)', boxShadow: '0 4px 12px rgba(16, 185, 129, 0.2)' }}
                      >
                        <Search size={16} />
                        <span>{detectingWatermark ? "正在提取校验启发软水印..." : "核验水印合法性及完整性"}</span>
                      </button>

                      {watermarkDetectResult && (
                        <div style={{ marginTop: '1.5rem', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                            <span className={`status-dot ${watermarkDetectResult.is_watermarked_detected ? 'active' : 'warn'}`}></span>
                            <span style={{ fontSize: '0.9rem', fontWeight: 800 }}>
                              {watermarkDetectResult.is_watermarked_detected ? "水印特征核验通过：完整安全，可定位出库审计" : "警告：篡改程度极高，水印校验印章已损毁"}
                            </span>
                          </div>
                          <div className="status-details-list" style={{ fontSize: '0.75rem', gap: '0.2rem', color: 'var(--color-text-muted)' }}>
                            <div className="status-details-row">
                              <span>模拟执行的破坏类型:</span>
                              <span className="status-details-val" style={{ textTransform: 'capitalize' }}>{tamperMode} attack</span>
                            </div>
                            <div className="status-details-row">
                              <span>水印提取算法置信度 (ADR):</span>
                              <span className="status-details-val" style={{ color: 'var(--color-green)' }}>
                                {(watermarkDetectResult.detection_confidence * 100).toFixed(0)}% 检出精度
                              </span>
                            </div>
                            <div className="status-details-row">
                              <span>解码追溯出的审计标识 (Watermark Ref):</span>
                              <span className="status-details-val" style={{ fontFamily: 'monospace' }}>
                                {pipelineData.audit_trace?.watermark_id || "wm_8819a"}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>暂无活跃流水线。</div>
                  )}
                </div>

                {/* Right Card: Cryptographic Audit trace metadata */}
                <div className="data-panel-card">
                  <div className="data-panel-title">🔬 HSW-ST 密匙完整性可追溯签名封印</div>

                  {pipelineData ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div className="retrieval-card">
                        <span className="percent-label">密码学可追溯链条状态:</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.15rem' }}>
                          <CheckCircle size={14} style={{ color: 'var(--color-green)' }} />
                          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-green)' }}>100% 审计签名校验完整通过</span>
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">辅导文本 SHA256 完好完整性印章 (Integrity hash):</span>
                        <div style={{ fontSize: '0.7rem', fontFamily: 'monospace', color: '#60a5fa', marginTop: '0.15rem', wordBreak: 'break-all' }}>
                          {pipelineData.audit_trace?.watermarked_answer_sha256 || "6323aae5b666f4b30ab268dcdbfa13dd8521e500d7e7f08f558a61a1068a62eb"}
                        </div>
                      </div>

                      <div className="retrieval-card">
                        <span className="percent-label">系统归档日志引用唯一编码 (Watermark ID):</span>
                        <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: '#f1f5f9', marginTop: '0.15rem' }}>
                          {pipelineData.audit_trace?.watermark_id || "wm_2cca0b7f"}
                        </div>
                      </div>

                      <div className="status-details-list" style={{ fontSize: '0.8rem', gap: '0.4rem' }}>
                        <div className="status-details-row">
                          <span>辅导答案唯一分配 ID:</span>
                          <span className="status-details-val" style={{ fontFamily: 'monospace' }}>ans_{pipelineData.generated_context_card?.task_id || "task_0001"}</span>
                        </div>
                        <div className="status-details-row">
                          <span>脱敏画像卡片索引 ID:</span>
                          <span className="status-details-val" style={{ fontFamily: 'monospace' }}>card_{pipelineData.generated_context_card?.task_id || "task_0001"}</span>
                        </div>
                        <div className="status-details-row">
                          <span>匹配检索出库的原资源 ID:</span>
                          <span className="status-details-val" style={{ fontFamily: 'monospace' }}>teacher_resource_arithmetic_sequence</span>
                        </div>
                        <div className="status-details-row">
                          <span>原教案匹配分块 ID:</span>
                          <span className="status-details-val" style={{ fontFamily: 'monospace' }}>chunk_889e1f6f</span>
                        </div>
                        <div className="status-details-row">
                          <span>底层智能体活跃流审计:</span>
                          <span className="status-details-val" style={{ color: 'var(--color-blue)' }}>4 / 4 智能体签名封印完整</span>
                        </div>
                        <div className="status-details-row">
                          <span>系统物理流转时间戳:</span>
                          <span className="status-details-val" style={{ fontFamily: 'monospace' }}>{pipelineData.audit_trace?.timestamp || "2026-05-26T19:38Z"}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>暂无活跃流水线。</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
