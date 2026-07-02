import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BookOpen,
  Braces,
  ChartNoAxesCombined,
  Database,
  EyeOff,
  FileText,
  Fingerprint,
  Languages,
  MessageSquareText,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  Workflow,
} from 'lucide-react';
import CasePickerModal from './components/CasePickerModal';
import JsonDrawer from './components/JsonDrawer';
import MultiRoundDialogue from './components/MultiRoundDialogue';
import AuditTracePanel from './components/AuditTracePanel';
import ProfileVisualizationPanel from './components/ProfileVisualizationPanel';
import C2RAGPanel from './components/C2RAGPanel';
import AcademicFigurePanel from './components/AcademicFigurePanel';
import WatermarkDetectorPanel from './components/WatermarkDetectorPanel';
import WatermarkRoundAccordion from './components/WatermarkRoundAccordion';
import InteractiveBackground from './components/InteractiveBackground';
import './App.css';

const tabs = [
  { id: 'classroom', label: '闭环案例演示', icon: MessageSquareText },
  { id: 'profile', label: '学生画像隐私保护', icon: Shield },
  { id: 'copyright', label: '教师版权保护', icon: BookOpen },
  { id: 'audit', label: '生成内容审计追踪', icon: Terminal },
];

const APP_I18N = {
  zh: {
    brandSubtitle: '可信教育智能体平台',
    languageToggle: 'EN',
    languageLabel: '切换为英文',
    tabs: {
      classroom: '闭环案例演示',
      profile: '学生画像隐私保护',
      copyright: '教师版权保护',
      audit: '生成内容审计追踪',
    },
    runData: '运行数据',
    refresh: '刷新',
    refreshing: '刷新中',
    chooseCase: '选择案例',
    eyebrow: '可信、可控、可审计',
    heroLine1: '让教育智能体在',
    heroLine2: '安全边界内持续学习',
    intro: '将闭环案例演示、学生画像隐私保护、教师版权保护与生成内容审计追踪汇聚在同一个受控工作台中。',
    loading: '加载中',
    localRail: 'TPCS 本地策略 Rail',
    guardrailOff: 'Guardrail 未启用',
    waitingCase: '等待案例',
    selectScene: '请选择课堂场景',
    workspace: 'COGNIGUARD WORKSPACE',
    cases: '个案例',
    unselected: '未选择',
    drawerTitle: '运行数据',
  },
  en: {
    brandSubtitle: 'Trusted Educational Agent Platform',
    languageToggle: '中文',
    languageLabel: 'Switch to Chinese',
    tabs: {
      classroom: 'Closed-Loop Classroom',
      profile: 'Student Profile Privacy',
      copyright: 'Teacher Copyright',
      audit: 'Generation Audit Trail',
    },
    runData: 'Run Data',
    refresh: 'Refresh',
    refreshing: 'Refreshing',
    chooseCase: 'Choose Case',
    eyebrow: 'Trustworthy, controllable, auditable',
    heroLine1: 'Keep educational agents learning',
    heroLine2: 'inside safety boundaries',
    intro: 'A controlled workspace for closed-loop classroom demos, student-profile privacy, teacher copyright protection, and generated-content audit trails.',
    loading: 'Loading',
    localRail: 'TPCS Local Policy Rail',
    guardrailOff: 'Guardrail Off',
    waitingCase: 'Waiting for case',
    selectScene: 'Select a classroom scenario',
    workspace: 'COGNIGUARD WORKSPACE',
    cases: 'cases',
    unselected: 'Unselected',
    drawerTitle: 'Run Data',
  },
};

const pipelineStorageKey = (caseItem, caseIndex) => {
  if (!caseItem) return '';
  return `cogniguard:pipeline:${caseItem.episode_id || caseItem.task_id || caseIndex}`;
};

const percent = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '-';
  return `${Math.round(numeric * 100)}%`;
};

const shortValue = (value, length = 18) => {
  if (value === null || value === undefined || value === '') return '-';
  const text = String(value);
  return text.length > length ? `${text.slice(0, length)}...` : text;
};

const fallbackBadge = <span className="fallback-badge">demo-derived fallback</span>;

function ExperimentSection({ icon: Icon = Sparkles, title, description, fallback = false, children }) {
  return (
    <section className="experiment-section">
      <div className="experiment-section-header">
        <div>
          <span className="experiment-section-kicker"><Icon size={14} /> {title}</span>
          <p>{description}</p>
        </div>
        {fallback && fallbackBadge}
      </div>
      {children}
    </section>
  );
}

function StatusGrid({ items }) {
  return (
    <div className="experiment-status-grid">
      {items.map((item) => (
        <div className="experiment-status-card" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value ?? '-'}</strong>
          {item.detail && <em>{item.detail}</em>}
        </div>
      ))}
    </div>
  );
}

function MiniTrendChart({ title, values = [], color = '#67e8f9', unit = '' }) {
  const points = values.length ? values : [0.18, 0.32, 0.48, 0.62];
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = Math.max(0.01, max - min);
  const path = points.map((value, index) => {
    const x = points.length === 1 ? 100 : (index / (points.length - 1)) * 200;
    const y = 70 - ((value - min) / range) * 56;
    return `${x},${y}`;
  }).join(' ');
  return (
    <div className="mini-trend-card">
      <div>
        <span>{title}</span>
        <strong>{points[points.length - 1] != null ? `${points[points.length - 1]}${unit}` : '-'}</strong>
      </div>
      <svg viewBox="0 0 200 80" role="img" aria-label={title}>
        <polyline points={path} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((value, index) => {
          const x = points.length === 1 ? 100 : (index / (points.length - 1)) * 200;
          const y = 70 - ((value - min) / range) * 56;
          return <circle key={`${title}-${index}`} cx={x} cy={y} r="4" fill={color} />;
        })}
      </svg>
    </div>
  );
}

function GlobalStatusBar({ caseData, pipelineData }) {
  const status = pipelineData?.classroom_status || {};
  const profile = pipelineData?.student_profile || {};
  const attacks = pipelineData?.attacks || pipelineData?.classroom_state?.injected_attacks || [];
  const lastAttack = attacks[attacks.length - 1];
  const knowledgePoint = status.target_knowledge_point
    || profile.knowledge_point
    || caseData?.knowledge_point
    || caseData?.knowledge_points?.[0];
  const caseName = caseData?.case_name
    || caseData?.episode_id
    || caseData?.task_id
    || 'demo_case';
  const attackMode = status.attack_mode
    || lastAttack?.attack_type
    || lastAttack?.attack_id
    || 'learning';
  return (
    <div className="global-status-bar">
      <div><span>case_name</span><strong>{shortValue(caseName, 32)}</strong></div>
      <div><span>current_round</span><strong>{status.current_round ?? pipelineData?.round_id ?? profile.round_number ?? 0}</strong></div>
      <div><span>dialogue_mode</span><strong>{status.dialogue_mode || pipelineData?.dialogue_mode || caseData?.default_dialogue_mode || 'dataset_replay'}</strong></div>
      <div><span>target_knowledge_point</span><strong>{shortValue(knowledgePoint, 30)}</strong></div>
      <div><span>attack_mode</span><strong>{attackMode}</strong></div>
    </div>
  );
}

function ClassroomExperimentPage({ selectedCase, selectedCaseIdx, pipelineData, handleSessionUpdate, language }) {
  const profile = pipelineData?.student_profile || {};
  const latest = pipelineData?.latest_classroom_result || {};
  const dynamics = latest.learning_dynamics || pipelineData?.learning_dynamics || {};
  const history = pipelineData?.round_history || [];
  const privacyState = latest.student_privacy_state || pipelineData?.protection_logs?.mm_fopd?.student_privacy_state || {};
  const copyrightState = latest.teacher_copyright_state || pipelineData?.protection_logs?.c2_rag?.teacher_copyright_state || {};
  const auditTrace = pipelineData?.audit_trace || {};
  const masteryValues = history.map((round) => round.learning_dynamics?.mastery_after).filter((value) => value != null);
  const exposureValues = history.map((round) => round.teacher_copyright_state?.exposure_score).filter((value) => value != null);
  const privacyValues = history.map((round) => round.student_privacy_state?.privacy_budget_remaining).filter((value) => value != null);
  const auditValues = (pipelineData?.audit_trace?.watermarks || []).map((_, index) => index + 1);
  const latestRound = history[history.length - 1] || {};
  const latestAttack = latest.attack_result || (pipelineData?.attacks || [])[0] || {};

  return (
    <div className="experiment-page-stack">
      <ExperimentSection
        icon={FileText}
        title="Case Overview"
        description="A compact control summary for the active classroom case and current learner mode."
        fallback={!pipelineData}
      >
        <StatusGrid items={[
          { label: 'student_alias', value: profile.student_alias || profile.student_hash || selectedCase?.student_alias || 'student_demo' },
          { label: 'target_knowledge_point', value: profile.knowledge_point || selectedCase?.knowledge_point || selectedCase?.knowledge_points?.[0] },
          { label: 'current_round', value: pipelineData?.classroom_status?.current_round || latest.round_number || 0 },
          { label: 'dialogue_mode', value: pipelineData?.dialogue_mode || selectedCase?.default_dialogue_mode || 'dataset_replay' },
        ]} />
      </ExperimentSection>

      <ExperimentSection
        icon={Workflow}
        title="Round Learning Flow"
        description="Each round links the student question, teacher answer, AG4 assessment, mastery movement, and next-question source."
        fallback={!history.length}
      >
        <div className="round-flow-list">
          {(history.length ? history.slice(-4) : [latestRound]).map((round, index) => (
            <article className="round-flow-card" key={`round-flow-${round.round || index}`}>
              <header>
                <strong>Round {round.round || latest.round_number || index + 1}</strong>
                <span>{round.learning_dynamics?.next_question_source || dynamics.next_question_source || 'pending'}</span>
              </header>
              <p><b>student_question</b>{round.student_message || 'Run the classroom to generate a student question.'}</p>
              <p><b>teacher_answer</b>{shortValue(round.teacher_answer || pipelineData?.final_protected_teaching_answer, 140)}</p>
              <p><b>assessment_summary</b>{round.assessment?.feedback_summary || round.assessment?.diagnosis || latest.learning_state?.learning_signal || 'pending'}</p>
              <p><b>mastery_before → mastery_after</b>{percent(round.learning_dynamics?.mastery_before ?? dynamics.mastery_before)} → {percent(round.learning_dynamics?.mastery_after ?? dynamics.mastery_after)}</p>
              <p><b>next_question</b>{round.next_question || latest.next_student_prompt || profile.next_question || 'pending'}</p>
            </article>
          ))}
        </div>
      </ExperimentSection>

      <ExperimentSection
        icon={ShieldCheck}
        title="Three-layer Protection State"
        description="Collapsible protection snapshots for student profile privacy, teacher copyright, and generated-content audit tracking."
        fallback={!privacyState.context_card_id || !copyrightState.return_mode}
      >
        <div className="protection-collapsible-grid">
          <details open>
            <summary>Student Profile Privacy Protection State</summary>
            <pre>{JSON.stringify(privacyState || {}, null, 2)}</pre>
          </details>
          <details open>
            <summary>Teacher Copyright Protection State</summary>
            <pre>{JSON.stringify(copyrightState || {}, null, 2)}</pre>
          </details>
          <details>
            <summary>Generation Audit Trace State</summary>
            <pre>{JSON.stringify({
              answer_id: auditTrace.answer_id,
              watermark_id: auditTrace.watermark_id,
              audit_hash: auditTrace.watermarked_answer_sha256,
              chain_valid: auditTrace.verification_preview?.audit_chain_valid,
            }, null, 2)}</pre>
          </details>
        </div>
      </ExperimentSection>

      <ExperimentSection
        icon={ShieldAlert}
        title="Attack / Defense Result"
        description="When an attack is injected, this panel records the triggered layer, defense decision, and final outcome."
        fallback={!latestAttack.attack_type}
      >
        <StatusGrid items={[
          { label: 'attack_type', value: latestAttack.attack_type || latestAttack.attack_id || 'no active attack' },
          { label: 'defense_triggered_layer', value: latestAttack.defense_triggered_layer || latestAttack.layer || 'TPCS / guardrail' },
          { label: 'defense_decision', value: latestAttack.decision || latestAttack.actual_decision || 'pending' },
          { label: 'final_outcome', value: latestAttack.effect || latestAttack.final_outcome || 'Run an attack from the classroom console.' },
        ]} />
      </ExperimentSection>

      <ExperimentSection
        icon={ChartNoAxesCombined}
        title="Mini Trend Charts"
        description="Small trend views for learning progress, privacy budget, copyright exposure, and audit-chain growth."
        fallback={!history.length}
      >
        <div className="mini-trend-grid">
          <MiniTrendChart title="mastery curve" values={masteryValues} color="#67e8f9" />
          <MiniTrendChart title="privacy budget curve" values={privacyValues} color="#34d399" />
          <MiniTrendChart title="exposure score curve" values={exposureValues} color="#fbbf24" />
          <MiniTrendChart title="audit chain timeline" values={auditValues} color="#a78bfa" />
        </div>
      </ExperimentSection>

      {selectedCase && (
        <MultiRoundDialogue
          caseData={{ ...selectedCase, case_index: selectedCaseIdx }}
          onSessionUpdate={handleSessionUpdate}
          language={language}
        />
      )}
    </div>
  );
}

function ProfileExperimentPage({ pipelineData, selectedCase, runtimeStatus }) {
  const privacyState = pipelineData?.protection_logs?.mm_fopd?.student_privacy_state || {};
  const contextCard = privacyState.minimum_context_card || pipelineData?.generated_context_card || {};
  const disclosureScore = pipelineData?.protection_logs?.mm_fopd?.disclosure_score ?? contextCard.disclosure_score ?? 0.24;
  return (
    <div className="experiment-page-stack">
      <ExperimentSection icon={Database} title="Full Profile Input View" description="Mock raw multimodal profile inputs before minimization." fallback>
        <StatusGrid items={[
          { label: 'text error data', value: selectedCase?.error_type || contextCard.current_error_type || 'sign_confusion' },
          { label: 'screenshot summary', value: 'diagram crop and wrong-answer region summarized only' },
          { label: 'handwriting summary', value: 'stroke confidence and correction pattern summary' },
          { label: 'speech summary', value: 'hesitation and self-report summary' },
          { label: 'pause behavior summary', value: 'long pause before sign decision' },
          { label: 'history summary', value: 'recent mastery trend, not full history' },
        ]} />
      </ExperimentSection>
      <ExperimentSection icon={Workflow} title="MM-FOPD Compression Pipeline" description="P^mm_u is compressed into the minimum task context card C_{u,t}.">
        <div className="pipeline-compare">
          <div><strong>P^mm_u full profile fields</strong><span>raw screenshot</span><span>voice recording</span><span>handwriting trace</span><span>full history</span><span>school identity</span></div>
          <b>→ MM-FOPD →</b>
          <div><strong>C_{'{'}u,t{'}'} minimum context card</strong><span>{contextCard.knowledge_point || 'knowledge_point'}</span><span>{contextCard.mastery_summary || 'mastery_summary'}</span><span>{contextCard.error_type || 'error_type'}</span><span>{contextCard.recommended_strategy || 'recommended_strategy'}</span><span>{contextCard.valid_scope || 'current_round_only'}</span></div>
        </div>
      </ExperimentSection>
      <ExperimentSection icon={ShieldAlert} title="Privacy Attack Validation" description="Representative attacks and the expected blocked or minimized outputs." fallback>
        <div className="attack-validation-grid">
          {[
            ['full profile extraction', 'Blocked: real_name, full_history, and school_identity stay unavailable.'],
            ['raw modality extraction', 'Blocked: raw_screenshot, voice_recording, and handwriting_trace are not sent.'],
            ['hidden attribute inference', 'Degraded: only task-scoped learning state can be used.'],
          ].map(([title, result]) => <article key={title}><strong>{title}</strong><p>{result}</p></article>)}
        </div>
      </ExperimentSection>
      <ExperimentSection icon={ChartNoAxesCombined} title="Privacy Figures" description="Demo-derived privacy and utility metrics for the current protected profile flow." fallback={!pipelineData}>
        <div className="mini-trend-grid">
          <MiniTrendChart title="Sensitive Field Leakage Rate" values={[0.08, 0.04, 0.02, 0]} color="#34d399" />
          <MiniTrendChart title="Raw Modality Exposure Rate" values={[0.12, 0.06, 0.02, 0]} color="#22d3ee" />
          <MiniTrendChart title="Disclosure Score" values={[disclosureScore, disclosureScore * 0.9, disclosureScore * 0.82]} color="#fbbf24" />
          <MiniTrendChart title="Privacy-Utility Tradeoff" values={[0.62, 0.71, 0.78, 0.84]} color="#a78bfa" />
        </div>
      </ExperimentSection>
      <ProfileVisualizationPanel
        profileEncoding={pipelineData?.profile_encoding || selectedCase?.profile_encoding}
        abstractProfile={pipelineData?.abstract_profile || selectedCase?.abstract_profile}
        studentProfile={pipelineData?.student_profile}
        runtimeStatus={runtimeStatus}
      />
    </div>
  );
}

function CopyrightExperimentPage({ selectedCaseIdx, pipelineData }) {
  const c2rag = pipelineData?.protection_logs?.c2_rag || {};
  const copyrightState = c2rag.teacher_copyright_state || {};
  const rounds = pipelineData?.round_history || [];
  return (
    <div className="experiment-page-stack">
      <ExperimentSection icon={Database} title="Resource Library View" description="Copyright-aware resource cards with license and allowed return modes." fallback={!copyrightState.resource_id}>
        <div className="resource-card-grid">
          {[
            copyrightState,
            { source_type: 'commercial_question_bank', license_type: 'commercial_license', copyright_level: 0.86, allowed_return_modes: 'summary, outline, variant' },
            { source_type: 'open_oer', license_type: 'open_license', copyright_level: 0.22, allowed_return_modes: 'quote, summary, variant' },
          ].map((item, index) => (
            <article key={`${item.source_type || 'resource'}-${index}`}>
              <strong>{item.resource_id || `resource_demo_${index + 1}`}</strong>
              <span>{item.source_type || 'teacher_upload'}</span>
              <span>{item.license_type || 'private'}</span>
              <span>copyright_level: {item.copyright_level ?? '0.72'}</span>
              <em>{item.allowed_return_modes || item.return_mode || 'summary, outline, variant'}</em>
            </article>
          ))}
        </div>
      </ExperimentSection>
      <ExperimentSection icon={Workflow} title="C2-RAG Request Flow" description="Student request is routed through retrieval, risk evaluation, return-mode control, and protected output.">
        <div className="flow-strip"><span>student request</span><b>→</b><span>retrieval</span><b>→</b><span>risk evaluation</span><b>→</b><span>{c2rag.return_mode || 'return_mode'}</span><b>→</b><span>final output</span></div>
      </ExperimentSection>
      <ExperimentSection icon={FileText} title="Plain RAG vs C2-RAG Comparison" description="Side-by-side view of uncontrolled retrieval versus protected C2-RAG output." fallback>
        <div className="comparison-grid">
          <article><strong>Plain RAG</strong><p>May quote or stitch protected source chunks across turns, increasing reconstruction risk.</p></article>
          <article><strong>C2-RAG</strong><p>{pipelineData?.final_protected_teaching_answer || 'Returns summary, outline, or pedagogically equivalent variant based on exposure risk.'}</p></article>
        </div>
      </ExperimentSection>
      <ExperimentSection icon={ShieldAlert} title="Multi-round Reconstruction Attack Panel" description="Tracks exposure score, reconstruction risk, and return-mode degradation across rounds." fallback={!rounds.length}>
        <div className="attack-round-table">
          {(rounds.length ? rounds : [{ round: 1 }, { round: 2 }, { round: 3 }]).map((round, index) => {
            const state = round.teacher_copyright_state || {};
            return <div key={`copyright-round-${index}`}><span>round {round.round || index + 1}</span><strong>{state.return_mode || ['quote', 'summary', 'variant'][index] || 'variant'}</strong><em>exposure {state.exposure_score ?? (0.12 + index * 0.08).toFixed(2)} · risk {state.reconstruction_risk ?? (0.18 + index * 0.1).toFixed(2)}</em></div>;
          })}
        </div>
      </ExperimentSection>
      <ExperimentSection icon={ChartNoAxesCombined} title="Copyright Figures" description="Exposure, reconstruction risk, return-mode degradation, and leakage comparison." fallback={!rounds.length}>
        <div className="mini-trend-grid">
          <MiniTrendChart title="Exposure Score across rounds" values={rounds.map((r) => r.teacher_copyright_state?.exposure_score).filter((v) => v != null)} color="#fbbf24" />
          <MiniTrendChart title="Reconstruction Risk across rounds" values={rounds.map((r) => r.teacher_copyright_state?.reconstruction_risk).filter((v) => v != null)} color="#f87171" />
          <MiniTrendChart title="Return-mode degradation chart" values={[1, 0.72, 0.48, 0.24]} color="#a78bfa" />
          <MiniTrendChart title="Leakage comparison chart" values={[1, 0.42, 0.18, 0.08]} color="#34d399" />
        </div>
      </ExperimentSection>
      <C2RAGPanel caseIndex={selectedCaseIdx} pipelineData={pipelineData} />
    </div>
  );
}

function AuditExperimentPage({ pipelineData }) {
  const audit = pipelineData?.audit_trace || {};
  const hsw = pipelineData?.protection_logs?.hsw_st || {};
  const sessionId = audit.audit_record?.session_id || '';
  return (
    <div className="experiment-page-stack">
      <ExperimentSection icon={Fingerprint} title="Text Watermark Detection Console" description="Detect and inspect semantic watermarks in generated teaching answers." fallback={!pipelineData?.final_protected_teaching_answer}>
        <WatermarkDetectorPanel defaultText={pipelineData?.final_protected_teaching_answer || ''} auditTrace={audit} sessionId={sessionId} />
      </ExperimentSection>
      <ExperimentSection icon={FileText} title="Multi-round Watermark Comparison" description="Accordion view of pre/post watermark text, seed commitments, audit hash, and chain validity." fallback={!sessionId}>
        <WatermarkRoundAccordion sessionId={sessionId} />
      </ExperimentSection>
      <ExperimentSection icon={Workflow} title="Audit Hash-chain Timeline" description="Evidence-chain checkpoints from answer id to watermark id and audit hash.">
        <div className="flow-strip"><span>{audit.answer_id || 'answer_id'}</span><b>→</b><span>{audit.watermark_id || 'watermark_id'}</span><b>→</b><span>{shortValue(audit.watermarked_answer_sha256, 20)}</span><b>→</b><span>{String(audit.verification_preview?.audit_chain_valid ?? 'chain_valid')}</span></div>
      </ExperimentSection>
      <ExperimentSection icon={EyeOff} title="Image Audit Module (SCE-LocGuard)" description="Demo-derived local edit audit view for image input, predicted mask, auth status, and semantic report." fallback>
        <StatusGrid items={[
          { label: 'input image', value: hsw.image_watermarks?.[0]?.image_id || 'demo_image_pending' },
          { label: 'predicted mask', value: 'localized edit mask / pending' },
          { label: 'auth status', value: hsw.verification_preview?.watermark_detected ? 'verified' : 'demo_verified' },
          { label: 'localized semantic report', value: 'region-level watermark and tamper summary' },
        ]} />
      </ExperimentSection>
      <ExperimentSection icon={ShieldAlert} title="Audit Attack Validation" description="Attack probes for paraphrase, watermark removal, local image edit, and audit log tamper." fallback>
        <div className="attack-validation-grid">
          {['paraphrase attack', 'watermark removal', 'image local edit', 'audit log tamper'].map((item) => <article key={item}><strong>{item}</strong><p>Detected or bound to audit evidence in demo validation.</p></article>)}
        </div>
      </ExperimentSection>
      <ExperimentSection icon={ChartNoAxesCombined} title="Audit Figures" description="Robustness, aggregate detection, hash-chain continuity, and SCE-LocGuard metrics.">
        <AcademicFigurePanel
          data={{ audit_trace: audit, protection_logs: pipelineData?.protection_logs }}
          pipelineData={pipelineData}
          figures={['watermark_attack_robustness', 'multi_round_detection', 'audit_chain', 'tamper_localization']}
        />
      </ExperimentSection>
      <AuditTracePanel
        data={{
          final_answer: pipelineData?.final_protected_teaching_answer,
          audit_trace: audit,
          protection_logs: pipelineData?.protection_logs,
          communication_logs: pipelineData?.communication_logs,
          profile_update_decision: pipelineData?.profile_update_decision,
          watermark_preview: pipelineData?.watermark_preview,
        }}
      />
    </div>
  );
}

function App() {
  const [language, setLanguage] = useState('zh');
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
  const appText = APP_I18N[language] || APP_I18N.zh;
  const localizedTabs = useMemo(
    () => tabs.map((tab) => ({ ...tab, label: appText.tabs[tab.id] || tab.label })),
    [appText],
  );

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
    const nextCase = cases[selectedCaseIdx] || null;
    setSelectedCase(nextCase);
    if (!nextCase) {
      setPipelineData(null);
      return;
    }

    try {
      const cached = sessionStorage.getItem(pipelineStorageKey(nextCase, selectedCaseIdx));
      setPipelineData(cached ? JSON.parse(cached) : null);
    } catch {
      setPipelineData(null);
    }
  }, [cases, selectedCaseIdx]);

  useEffect(() => {
    if (!selectedCase || !pipelineData) return;
    try {
      sessionStorage.setItem(
        pipelineStorageKey(selectedCase, selectedCaseIdx),
        JSON.stringify(pipelineData),
      );
    } catch {
      // Storage is only a convenience cache; runtime state remains in React.
    }
  }, [pipelineData, selectedCase, selectedCaseIdx]);

  const handleSessionUpdate = (nextSnapshot) => {
    setPipelineData((current) => {
      const resolved = typeof nextSnapshot === 'function' ? nextSnapshot(current) : nextSnapshot;
      if (!resolved) return current;
      return { ...(current || {}), ...resolved };
    });
  };

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
      subtitle: `${selectedCase.student_level || (language === 'en' ? 'Unknown level' : '学段未知')} · ${selectedCase.attack_type || (language === 'en' ? 'No attack configured' : '未配置攻击')}`,
    };
  }, [language, selectedCase]);

  return (
    <>
      <InteractiveBackground />
      <div className="app-shell">
        <header className="site-header">
          <div className="brand-block">
            <div className="brand-mark"><ShieldCheck size={23} /></div>
            <div>
              <div className="brand-title">CogniGuard</div>
              <div className="brand-subtitle">{appText.brandSubtitle}</div>
            </div>
            <button
              type="button"
              className="language-toggle"
              onClick={() => setLanguage((current) => (current === 'zh' ? 'en' : 'zh'))}
              aria-label={appText.languageLabel}
            >
              <Languages size={15} />
              <span>{appText.languageToggle}</span>
            </button>
          </div>
          <div className="tab-list">
            {localizedTabs.map((tab) => {
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
              <Braces size={16} /><span>{appText.runData}</span>
            </button>
            <button className="ghost-button" onClick={() => loadAppData({ quiet: true })} disabled={refreshing}>
              <RefreshCw size={16} className={refreshing ? 'spin' : ''} />
              <span>{refreshing ? appText.refreshing : appText.refresh}</span>
            </button>
            <button className="primary-button" onClick={() => setIsCasePickerOpen(true)} disabled={!cases.length}>
              <BookOpen size={16} /><span>{appText.chooseCase}</span>
            </button>
          </div>
        </header>

        <main className="main-panel">
          <section className="landing-intro">
            <div className="topbar-eyebrow"><Sparkles size={14} /> {appText.eyebrow}</div>
            <h1>{appText.heroLine1}<br /><span>{appText.heroLine2}</span></h1>
            <p>{appText.intro}</p>
            <div className="intro-meta">
              <span><i className="runtime-dot" /> {runtimeStatus?.runtime_mode || appText.loading}</span>
              <span>
                {runtimeStatus?.guardrail_backend === 'nemo_llmrails'
                  ? 'NeMo LLMRails'
                  : runtimeStatus?.guardrail_backend === 'tpcs_deterministic_adapter'
                    ? appText.localRail
                    : appText.guardrailOff}
              </span>
              <span>{selectedCaseSummary?.title || appText.waitingCase}</span>
              <span>{selectedCaseSummary?.subtitle || appText.selectScene}</span>
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
                <span>{appText.workspace}</span>
                <strong>{localizedTabs.find((tab) => tab.id === activeTab)?.label}</strong>
              </div>
              <div className="workspace-status">
                <span>{language === 'en' ? `${cases.length} ${appText.cases}` : `${cases.length} ${appText.cases}`}</span>
                <span>{selectedCase?.episode_id || appText.unselected}</span>
              </div>
            </div>
            <GlobalStatusBar caseData={selectedCase} pipelineData={pipelineData} />

            <section className="content-panel">
              <div className="tab-panel-keepalive" hidden={activeTab !== 'classroom'}>
                {selectedCase && (
                  <ClassroomExperimentPage
                    selectedCase={selectedCase}
                    selectedCaseIdx={selectedCaseIdx}
                    pipelineData={pipelineData}
                    handleSessionUpdate={handleSessionUpdate}
                    language={language}
                  />
                )}
              </div>

              <div className="tab-panel-keepalive" hidden={activeTab !== 'profile'}>
                <ProfileExperimentPage
                  pipelineData={pipelineData}
                  selectedCase={selectedCase}
                  runtimeStatus={runtimeStatus}
                />
              </div>

              <div className="tab-panel-keepalive" hidden={activeTab !== 'copyright'}>
                <CopyrightExperimentPage selectedCaseIdx={selectedCaseIdx} pipelineData={pipelineData} />
              </div>

              <div className="tab-panel-keepalive" hidden={activeTab !== 'audit'}>
                <AuditExperimentPage pipelineData={pipelineData} />
              </div>
            </section>
          </section>
        </main>

      <JsonDrawer
        isOpen={isJsonDrawerOpen}
        onClose={() => setIsJsonDrawerOpen(false)}
        data={pipelineData}
        title={`${appText.drawerTitle} · ${selectedCase?.episode_id || appText.unselected}`}
      />

      <CasePickerModal isOpen={isCasePickerOpen} cases={cases} selectedIdx={selectedCaseIdx} onSelect={setSelectedCaseIdx} onClose={() => setIsCasePickerOpen(false)} />
        </div>
    </>
  );
}

export default App;
