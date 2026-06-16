import { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  Braces,
  MessageSquareText,
  RefreshCw,
  Shield,
  ShieldCheck,
  Sparkles,
  Terminal,
} from 'lucide-react';
import CasePickerModal from './components/CasePickerModal';
import JsonDrawer from './components/JsonDrawer';
import MultiRoundDialogue from './components/MultiRoundDialogue';
import AuditTracePanel from './components/AuditTracePanel';
import ProfileVisualizationPanel from './components/ProfileVisualizationPanel';
import InteractiveBackground from './components/InteractiveBackground';
import './App.css';

const tabs = [
  { id: 'classroom', label: '多轮课堂', icon: MessageSquareText },
  { id: 'audit', label: '水印审计', icon: Terminal },
  { id: 'profile', label: '画像面板', icon: Sparkles },
];

function App() {
  const [activeTab, setActiveTab] = useState('classroom');
  const [cases, setCases] = useState([]);
  const [selectedCaseIdx, setSelectedCaseIdx] = useState(0);
  const [selectedCase, setSelectedCase] = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [isCasePickerOpen, setIsCasePickerOpen] = useState(false);
  const [isJsonDrawerOpen, setIsJsonDrawerOpen] = useState(false);

  const apiGet = async (path) => {
    const res = await fetch(`${path}${path.includes('?') ? '&' : '?'}_=${Date.now()}`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`接口 ${path} 返回 HTTP ${res.status}`);
    return res.json();
  };

  const loadAppData = async ({ quiet = false } = {}) => {
    setRefreshing(true);
    setError('');
    try {
      const [status, caseData] = await Promise.all([
        apiGet('/api/runtime/status'),
        apiGet('/api/cases'),
      ]);
      const rows = caseData.rows || [];
      setRuntimeStatus(status);
      setCases(rows);
      if (rows.length > 0) {
        setSelectedCaseIdx((current) => Math.min(current, rows.length - 1));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAppData();
  }, []);

  useEffect(() => {
    setSelectedCase(cases[selectedCaseIdx] || null);
    setPipelineData(null);
  }, [cases, selectedCaseIdx]);

  useEffect(() => {
    const updateButtonLight = (event) => {
      const button = event.target.closest('button');
      if (!button) return;
      const rect = button.getBoundingClientRect();
      button.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`);
      button.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`);
    };

    const addRipple = (event) => {
      const button = event.target.closest('button');
      if (!button || button.disabled) return;
      const rect = button.getBoundingClientRect();
      const ripple = document.createElement('span');
      ripple.className = 'button-ripple';
      ripple.style.left = `${event.clientX - rect.left}px`;
      ripple.style.top = `${event.clientY - rect.top}px`;
      button.appendChild(ripple);
      window.setTimeout(() => ripple.remove(), 620);
    };

    document.addEventListener('pointermove', updateButtonLight, { passive: true });
    document.addEventListener('pointerdown', addRipple);
    return () => {
      document.removeEventListener('pointermove', updateButtonLight);
      document.removeEventListener('pointerdown', addRipple);
    };
  }, []);

  useEffect(() => {
    const surfaces = [...document.querySelectorAll('.site-header, .main-panel')];
    if (!surfaces.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;

    let previousScrollY = window.scrollY;
    let previousScrollTime = performance.now();
    let displacement = 0;
    let velocity = 0;
    let frameId = 0;

    const animateJellyScroll = () => {
      velocity += -displacement * 0.2;
      velocity *= 0.62;
      displacement += velocity;

      if (Math.abs(displacement) < 0.025 && Math.abs(velocity) < 0.025) {
        displacement = 0;
        velocity = 0;
      }

      const stretch = 1 + Math.min(Math.abs(displacement), 12) * 0.00075;
      const skew = Math.max(-0.28, Math.min(0.28, displacement * -0.018));
      surfaces.forEach((surface) => {
        surface.style.setProperty('--jelly-offset', `${displacement.toFixed(3)}px`);
        surface.style.setProperty('--jelly-stretch', stretch.toFixed(4));
        surface.style.setProperty('--jelly-skew', `${skew.toFixed(3)}deg`);
      });

      if (displacement || velocity) {
        frameId = requestAnimationFrame(animateJellyScroll);
      } else {
        frameId = 0;
      }
    };

    const onScroll = () => {
      const now = performance.now();
      const delta = window.scrollY - previousScrollY;
      const elapsed = Math.max(12, now - previousScrollTime);
      const scrollSpeed = Math.abs(delta) / elapsed;
      previousScrollY = window.scrollY;
      previousScrollTime = now;

      // Keep ordinary mouse-wheel scrolling rigid. The elastic response only
      // appears during a fast flick or a rapid trackpad gesture.
      if (Math.abs(delta) < 72 || scrollSpeed < 1.45) return;

      displacement = Math.max(-7, Math.min(7, -delta * 0.055));
      velocity = Math.max(-1.8, Math.min(1.8, -delta * 0.009));
      if (!frameId) frameId = requestAnimationFrame(animateJellyScroll);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('scroll', onScroll);
      surfaces.forEach((surface) => {
        surface.style.removeProperty('--jelly-offset');
        surface.style.removeProperty('--jelly-stretch');
        surface.style.removeProperty('--jelly-skew');
      });
    };
  }, []);

  const selectedCaseSummary = useMemo(() => {
    if (!selectedCase) return null;
    const knowledgeText = (selectedCase.knowledge_points || []).join(' · ');
    return {
      title: knowledgeText || selectedCase.scenario_type || selectedCase.episode_id,
      subtitle: `${selectedCase.student_level || '学段未知'} · ${selectedCase.attack_type || '未配置攻击'}`,
    };
  }, [selectedCase]);

  return (
    <>
      <InteractiveBackground />
      <div className="app-shell">
        <header className="site-header">
          <div className="brand-block">
            <div className="brand-mark"><ShieldCheck size={23} /></div>
            <div>
              <div className="brand-title">CogniGuard</div>
              <div className="brand-subtitle">可信教育智能体平台</div>
            </div>
          </div>
          <div className="tab-list">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <Icon size={16} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
          <div className="topbar-actions">
            <button className="ghost-button" onClick={() => setIsJsonDrawerOpen(true)} disabled={!pipelineData}>
              <Braces size={16} /><span>运行数据</span>
            </button>
            <button className="ghost-button" onClick={() => loadAppData({ quiet: true })} disabled={refreshing}>
              <RefreshCw size={16} className={refreshing ? 'spin' : ''} />
              <span>{refreshing ? '刷新中' : '刷新'}</span>
            </button>
            <button className="primary-button" onClick={() => setIsCasePickerOpen(true)} disabled={!cases.length}>
              <BookOpen size={16} /><span>选择案例</span>
            </button>
          </div>
        </header>

        <main className="main-panel">
          <section className="landing-intro">
            <div className="topbar-eyebrow"><Sparkles size={14} /> 可信、可控、可审计</div>
            <h1>让教育智能体在<br /><span>安全边界内持续学习</span></h1>
            <p>将多轮课堂、攻击注入、学生画像与水印审计汇聚在同一个受控工作台中。</p>
            <div className="intro-meta">
              <span><i className="runtime-dot" /> {runtimeStatus?.runtime_mode || '加载中'}</span>
              <span>
                {runtimeStatus?.guardrail_backend === 'nemo_llmrails'
                  ? 'NeMo LLMRails'
                  : runtimeStatus?.guardrail_backend === 'tpcs_deterministic_adapter'
                    ? 'TPCS 本地策略 Rail'
                    : 'Guardrail 未启用'}
              </span>
              <span>{selectedCaseSummary?.title || '等待案例'}</span>
              <span>{selectedCaseSummary?.subtitle || '请选择课堂场景'}</span>
            </div>
          </section>

          {error && (
            <section className="error-banner">
              <Shield size={16} />
              <span>{error}</span>
            </section>
          )}

          <section className="workspace-shell">
            <div className="workspace-header">
              <div>
                <span>COGNIGUARD WORKSPACE</span>
                <strong>{tabs.find((tab) => tab.id === activeTab)?.label}</strong>
              </div>
              <div className="workspace-status">
                <span>{cases.length} 个案例</span>
                <span>{selectedCase?.episode_id || '未选择'}</span>
              </div>
            </div>

            <section className="content-panel">
              {activeTab === 'classroom' && selectedCase && (
                <MultiRoundDialogue caseData={{ ...selectedCase, case_index: selectedCaseIdx }} onSessionUpdate={setPipelineData} />
              )}

              {activeTab === 'audit' && (
                <AuditTracePanel
                  data={{
                    final_answer: pipelineData?.final_protected_teaching_answer,
                    audit_trace: pipelineData?.audit_trace,
                    protection_logs: pipelineData?.protection_logs,
                    communication_logs: pipelineData?.communication_logs,
                    profile_update_decision: pipelineData?.profile_update_decision,
                    watermark_preview: pipelineData?.watermark_preview,
                  }}
                />
              )}

              {activeTab === 'profile' && (
                <ProfileVisualizationPanel
                  profileEncoding={pipelineData?.profile_encoding || selectedCase?.profile_encoding}
                  abstractProfile={pipelineData?.abstract_profile || selectedCase?.abstract_profile}
                  studentProfile={pipelineData?.student_profile}
                  runtimeStatus={runtimeStatus}
                />
              )}
            </section>
          </section>
        </main>

      <JsonDrawer
        isOpen={isJsonDrawerOpen}
        onClose={() => setIsJsonDrawerOpen(false)}
        data={pipelineData}
        title={`运行数据 · ${selectedCase?.episode_id || '未选择案例'}`}
      />

      <CasePickerModal isOpen={isCasePickerOpen} cases={cases} selectedIdx={selectedCaseIdx} onSelect={setSelectedCaseIdx} onClose={() => setIsCasePickerOpen(false)} />
        </div>
    </>
  );
}

export default App;
