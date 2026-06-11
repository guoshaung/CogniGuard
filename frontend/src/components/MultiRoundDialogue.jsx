import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  Braces,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Database,
  Fingerprint,
  LockKeyhole,
  Play,
  RotateCcw,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  Square,
  User,
  Waves,
} from 'lucide-react';
import './MultiRoundDialogue.css';

const ATTACK_TYPES = [
  { id: 'prompt_injection', label: 'Prompt Injection', detail: 'Override trusted instructions' },
  { id: 'privacy_extraction', label: 'Privacy Extraction', detail: 'Extract raw student profile' },
  { id: 'copyright_reconstruction', label: 'Copyright Reconstruction', detail: 'Rebuild teacher source' },
  { id: 'permission_bypass', label: 'Permission Bypass', detail: 'Skip TPCS authorization' },
  { id: 'profile_pollution', label: 'Profile Pollution', detail: 'Write false mastery evidence' },
  { id: 'watermark_tampering', label: 'Watermark Tampering', detail: 'Remove provenance marks' },
  { id: 'multi_turn_inference', label: 'Multi-turn Inference', detail: 'Infer hidden attributes' },
];

const ROLE_META = {
  student: { label: '学生提问', icon: User },
  teacher: { label: '教师 AI', icon: Bot },
  learner: { label: '学生代理回应', icon: BrainCircuit },
  attacker: { label: '第三方攻击者', icon: ShieldAlert },
  security: { label: 'TPCS 防御', icon: Shield },
  feedback: { label: '能力评估反馈', icon: Waves },
  goal: { label: '能力达标', icon: CheckCircle2 },
};

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function MultiRoundDialogue({ caseData }) {
  const [messages, setMessages] = useState([]);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [sessionState, setSessionState] = useState(null);
  const [roleSnapshots, setRoleSnapshots] = useState({});
  const [running, setRunning] = useState(false);
  const [statusText, setStatusText] = useState('Ready to start continuous learning');
  const [roundNumber, setRoundNumber] = useState(0);
  const [attackQueue, setAttackQueue] = useState([]);
  const [attackActivity, setAttackActivity] = useState({
    phase: 'idle',
    attackType: null,
    message: 'Select an attack to inject it into the protected classroom.',
  });
  const [manualQuestion, setManualQuestion] = useState('');
  const [queuedQuestion, setQueuedQuestion] = useState('');
  const [targetMastery, setTargetMastery] = useState(85);
  const [error, setError] = useState('');
  const stopRef = useRef(false);
  const attackQueueRef = useRef([]);
  const attackBusyRef = useRef(false);
  const sessionStateRef = useRef(null);
  const queuedQuestionRef = useRef('');
  const messageListRef = useRef(null);

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTo({
        top: messageListRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messages, statusText]);

  const resetSession = () => {
    stopRef.current = true;
    attackQueueRef.current = [];
    attackBusyRef.current = false;
    sessionStateRef.current = null;
    queuedQuestionRef.current = '';
    setMessages([]);
    setSelectedDetail(null);
    setSessionState(null);
    setRoleSnapshots({});
    setRunning(false);
    setStatusText('Ready to start continuous learning');
    setRoundNumber(0);
    setAttackQueue([]);
    setAttackActivity({
      phase: 'idle',
      attackType: null,
      message: 'Select an attack to inject it into the protected classroom.',
    });
    setQueuedQuestion('');
    setManualQuestion('');
    setError('');
  };

  useEffect(() => {
    resetSession();
  }, [caseData?.task_id]);

  const callTurn = async ({
    turnKind,
    round,
    question = '',
    attackType = null,
    currentState = null,
  }) => {
    const response = await fetch('/api/dialogue/next-round', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      body: JSON.stringify({
        case_index: caseData?.case_index ?? 0,
        turn_kind: turnKind,
        round_number: round,
        student_message: question,
        attack_type: attackType,
        session_state: currentState,
        target_mastery: targetMastery / 100,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.error || `Dialogue API returned HTTP ${response.status}`);
    }
    return result;
  };

  const revealMessages = async (items) => {
    for (const message of items || []) {
      if (stopRef.current) return;
      setMessages((current) => [...current, message]);
      await sleep(message.role === 'teacher' ? 950 : 520);
    }
  };

  const applyResult = (result) => {
    sessionStateRef.current = result.session_state;
    setSessionState(result.session_state);
    setRoleSnapshots(result.role_snapshots || {});
    setRoundNumber(result.round_number || 0);
  };

  const syncAttackQueue = (nextQueue) => {
    attackQueueRef.current = nextQueue;
    setAttackQueue(nextQueue);
  };

  const executeAttack = async (attackType, state, round) => {
    const attack = ATTACK_TYPES.find((item) => item.id === attackType);
    setAttackActivity({
      phase: 'running',
      attackType,
      message: `${attack?.label || attackType} is entering the TPCS checkpoint now.`,
    });
    setStatusText(`Attack checkpoint: handling ${attackType}`);
    const attackResult = await callTurn({
      turnKind: 'attack',
      round,
      attackType,
      currentState: state,
    });
    applyResult(attackResult);
    await revealMessages(attackResult.messages);
    const decision = attackResult.attack_result?.decision || 'audited';
    setAttackActivity({
      phase: 'completed',
      attackType,
      message: `TPCS ${decision}: ${attackResult.attack_result?.effect || 'attack evidence recorded in the audit chain'}`,
    });
    await sleep(650);
    return attackResult.session_state;
  };

  const injectQueuedAttacks = async (state, round) => {
    if (stopRef.current || attackQueueRef.current.length === 0) return state;
    attackBusyRef.current = true;
    let nextState = state;
    try {
      while (attackQueueRef.current.length > 0 && !stopRef.current) {
        const [attackType, ...remaining] = attackQueueRef.current;
        syncAttackQueue(remaining);
        nextState = await executeAttack(attackType, nextState, round);
      }
      return nextState;
    } finally {
      attackBusyRef.current = false;
    }
  };

  const startContinuousLesson = async () => {
    if (roleSnapshots.goal?.goal_met) return;
    stopRef.current = false;
    setRunning(true);
    setError('');
    let localState = sessionState;
    let nextQuestion = localState?.student_profile?.next_question || '';
    let round = Number(localState?.round_number || roundNumber || 0);

    try {
      while (!stopRef.current) {
        round += 1;
        localState = await injectQueuedAttacks(localState, round);
        if (stopRef.current) break;

        const userQuestion = queuedQuestionRef.current;
        if (userQuestion) {
          nextQuestion = userQuestion;
          queuedQuestionRef.current = '';
          setQueuedQuestion('');
        }

        setStatusText(`Round ${round}: student asks, teacher responds, learner reflects`);
        const result = await callTurn({
          turnKind: 'learning',
          round,
          question: nextQuestion,
          currentState: localState,
        });
        localState = result.session_state;
        applyResult(result);
        await revealMessages(result.messages);

        if (result.goal?.goal_met) {
          setStatusText(
            `Target reached at round ${round}: ${Math.round(result.session_state.student_profile.mastery_estimate * 100)}% mastery`,
          );
          break;
        }

        nextQuestion = result.next_student_prompt || '';
        setStatusText(`Round ${round}: closed-loop evidence committed; preparing next question`);
        localState = await injectQueuedAttacks(localState, round);
        await sleep(900);
      }

      if (stopRef.current) {
        setStatusText(`Stopped by user after round ${roundNumber || round}`);
      }
    } catch (caughtError) {
      setError(caughtError.message);
      setStatusText('Continuous session stopped because the dialogue API failed');
    } finally {
      setRunning(false);
    }
  };

  const stopSession = () => {
    stopRef.current = true;
    setStatusText('Stopping after the current protected operation...');
  };

  const runImmediateAttack = async (attackType) => {
    if (attackBusyRef.current) {
      const nextQueue = [...attackQueueRef.current, attackType];
      syncAttackQueue(nextQueue);
      setAttackActivity({
        phase: 'queued',
        attackType,
        message: `Queued as attack ${nextQueue.length}; it will run after the active checkpoint.`,
      });
      return;
    }

    stopRef.current = false;
    setError('');
    attackBusyRef.current = true;
    try {
      let nextState = await executeAttack(
        attackType,
        sessionStateRef.current || sessionState,
        Math.max(1, roundNumber),
      );
      while (attackQueueRef.current.length > 0) {
        const [queuedType, ...remaining] = attackQueueRef.current;
        syncAttackQueue(remaining);
        nextState = await executeAttack(
          queuedType,
          nextState,
          Math.max(1, roundNumber),
        );
      }
      setStatusText(`${attackType} handled; future turns now use the updated controls`);
    } catch (caughtError) {
      setError(caughtError.message);
      setAttackActivity({
        phase: 'error',
        attackType,
        message: caughtError.message,
      });
    } finally {
      attackBusyRef.current = false;
    }
  };

  const queueAttack = (attackType) => {
    if (!running && !attackBusyRef.current) {
      void runImmediateAttack(attackType);
      return;
    }
    const nextQueue = [...attackQueueRef.current, attackType];
    syncAttackQueue(nextQueue);
    const attack = ATTACK_TYPES.find((item) => item.id === attackType);
    setAttackActivity({
      phase: 'queued',
      attackType,
      message: `${attack?.label || attackType} queued at position ${nextQueue.length}; it will run after the current protected operation.`,
    });
    setStatusText(`${attackType} queued for the next TPCS checkpoint`);
  };

  const submitQuestion = async () => {
    const question = manualQuestion.trim();
    if (!question) return;
    setManualQuestion('');
    if (running) {
      queuedQuestionRef.current = question;
      setQueuedQuestion(question);
      setStatusText('Your student question will replace the next agent-generated question');
      return;
    }

    setError('');
    try {
      const nextRound = Math.max(1, roundNumber + 1);
      const result = await callTurn({
        turnKind: 'learning',
        round: nextRound,
        question,
        currentState: sessionState,
      });
      applyResult(result);
      await revealMessages(result.messages);
      setStatusText(`Manual round ${nextRound} completed; press Resume to continue automatically`);
    } catch (caughtError) {
      setError(caughtError.message);
    }
  };

  const selectRole = (role, title) => {
    setSelectedDetail({
      title,
      data: roleSnapshots[role] || { status: 'Start the session to generate live role data.' },
    });
  };

  const studentSnapshot = roleSnapshots.student || {};
  const teacherSnapshot = roleSnapshots.teacher || {};
  const auditSnapshot = roleSnapshots.audit || {};
  const goalSnapshot = roleSnapshots.goal || {};
  const masteryPercent = studentSnapshot.mastery_estimate != null
    ? Math.round(studentSnapshot.mastery_estimate * 100)
    : 0;

  return (
    <section className="classroom-lab">
      <div className="classroom-hero">
        <div>
          <div className="classroom-eyebrow"><Sparkles size={14} /> Continuous Closed-loop Learning</div>
          <h1>持续迭代的师生代理课堂与攻击实验台</h1>
          <p>
            学生代理在每次教师回答后进行回应、接受能力评估并生成下一问。
            会话持续到能力标准连续两轮达标，或由你手动停止。
          </p>
        </div>
        <div className="classroom-actions">
          <label className="mastery-target-control">
            <span>Target</span>
            <input
              type="number"
              min="60"
              max="98"
              value={targetMastery}
              disabled={running || Boolean(sessionState)}
              onChange={(event) => setTargetMastery(Number(event.target.value))}
            />
            <em>%</em>
          </label>
          <button className="classroom-secondary-button" onClick={resetSession} disabled={running}>
            <RotateCcw size={16} /> Reset
          </button>
          {running ? (
            <button className="classroom-stop-button" onClick={stopSession}>
              <Square size={15} /> Stop
            </button>
          ) : (
            <button
              className="classroom-primary-button"
              onClick={startContinuousLesson}
              disabled={Boolean(goalSnapshot.goal_met)}
            >
              <Play size={16} /> {roundNumber > 0 ? 'Resume learning' : 'Start continuous learning'}
            </button>
          )}
        </div>
      </div>

      <div className="classroom-status-strip">
        <div className={`classroom-live-dot ${running ? 'active' : ''}`} />
        <strong>{statusText}</strong>
        <span><Clock3 size={14} /> Round {roundNumber}</span>
        <span><LockKeyhole size={14} /> TPCS governed</span>
      </div>

      <section className={`classroom-attack-dock ${attackActivity.phase}`}>
        <div className="attack-dock-header">
          <div>
            <span className="attack-dock-icon"><ShieldAlert size={18} /></span>
            <div>
              <strong>Third-party attack console</strong>
              <small>Click any action to inject it into this classroom session.</small>
            </div>
          </div>
          <div className="attack-dock-state">
            <span>{attackActivity.phase.toUpperCase()}</span>
            {attackQueue.length > 0 && <b>{attackQueue.length} queued</b>}
          </div>
        </div>
        <div className="attack-dock-actions">
          {ATTACK_TYPES.map((attack) => (
            <button
              key={attack.id}
              type="button"
              data-testid={`classroom-attack-${attack.id}`}
              className={attackQueue.includes(attack.id) ? 'queued' : ''}
              onClick={() => queueAttack(attack.id)}
              aria-label={`Inject ${attack.label} attack`}
            >
              <span>{attack.label}</span>
              <small>{attack.detail}</small>
              <em>{attackQueue.includes(attack.id) ? 'Queued' : 'Inject now'}</em>
            </button>
          ))}
        </div>
        <div className="attack-dock-feedback" aria-live="polite">
          <AlertTriangle size={14} />
          <span>{attackActivity.message}</span>
        </div>
      </section>

      {queuedQuestion && (
        <div className="classroom-queued-note">
          Next user question: {queuedQuestion}
        </div>
      )}
      {error && <div className="classroom-error"><AlertTriangle size={16} /> {error}</div>}

      <div className="classroom-grid">
        <aside className="classroom-role-column">
          <button className="classroom-role-card student-card" onClick={() => selectRole('student', 'Student agent and profile JSON')}>
            <div className="role-card-icon"><BrainCircuit size={22} /></div>
            <div>
              <span>Student Agent / 学生代理</span>
              <strong>{studentSnapshot.student_agent?.model || 'mimo-v2-flash / fallback'}</strong>
            </div>
            <Braces size={16} />
          </button>

          <div className="classroom-mini-metrics">
            <div><span>Knowledge</span><strong>{caseData?.knowledge_point || '-'}</strong></div>
            <div><span>Level</span><strong>{studentSnapshot.student_level || 'pending'}</strong></div>
            <div><span>Mastery</span><strong>{masteryPercent || '-'}%</strong></div>
            <div><span>Target</span><strong>{targetMastery}%</strong></div>
            <div><span>Confirmed</span><strong>{goalSnapshot.consecutive_passes || 0}/{goalSnapshot.required_consecutive_passes || 2}</strong></div>
          </div>

          <div className="mastery-progress">
            <div style={{ width: `${Math.min(100, masteryPercent)}%` }} />
            <span style={{ left: `${targetMastery}%` }} />
          </div>

          <div className="classroom-layer-note">
            <Fingerprint size={18} />
            <div>
              <strong>MM-FOPD + Student Agent</strong>
              <span>The student sees only the teacher answer and bounded assessment feedback.</span>
            </div>
          </div>
        </aside>

        <main className="classroom-conversation-panel">
          <div className="conversation-panel-header">
            <div>
              <strong>Continuous protected classroom transcript</strong>
              <span>{messages.length} live events</span>
            </div>
            <div className="feedback-pills">
              <span>Student reflection</span>
              <span>Ability assessment</span>
              <span>Attack recovery</span>
            </div>
          </div>

          <div className="classroom-message-list" ref={messageListRef}>
            {messages.length === 0 && (
              <div className="classroom-empty-state">
                <Waves size={42} />
                <h3>The continuous classroom is waiting</h3>
                <p>Start learning, inject attacks at any time, or provide the next student question.</p>
              </div>
            )}
            {messages.map((message) => {
              const meta = ROLE_META[message.role] || ROLE_META.feedback;
              const Icon = meta.icon;
              return (
                <button
                  key={message.id}
                  className={`classroom-message ${message.role}`}
                  onClick={() => setSelectedDetail({
                    title: `${meta.label} message JSON`,
                    data: message.payload,
                  })}
                >
                  <div className="classroom-message-avatar"><Icon size={17} /></div>
                  <div className="classroom-message-body">
                    <div className="classroom-message-meta">
                      <strong>{meta.label}</strong>
                      <span>{new Date(message.timestamp).toLocaleTimeString('zh-CN')}</span>
                    </div>
                    <p>{message.content}</p>
                    <span className="inspect-json"><Braces size={12} /> Click to inspect JSON</span>
                  </div>
                </button>
              );
            })}
            {running && (
              <div className="classroom-thinking">
                <span /><span /><span />
                <em>{statusText}</em>
              </div>
            )}
          </div>

          <div className="classroom-input-row">
            <textarea
              value={manualQuestion}
              onChange={(event) => setManualQuestion(event.target.value)}
              placeholder={running ? '输入后将覆盖学生代理的下一问...' : '输入一个学生问题并继续本次会话...'}
              rows={2}
            />
            <button onClick={submitQuestion} disabled={!manualQuestion.trim()}>
              <Send size={17} />
            </button>
          </div>
        </main>

        <aside className="classroom-control-column">
          <button className="classroom-role-card teacher-card" onClick={() => selectRole('teacher', 'Teacher resource JSON')}>
            <div className="role-card-icon"><Bot size={22} /></div>
            <div>
              <span>Teacher AI / 教师</span>
              <strong>{teacherSnapshot.return_mode || 'protected response'}</strong>
            </div>
            <Braces size={16} />
          </button>

          <div className="classroom-mini-metrics teacher-metrics">
            <div><span>Return mode</span><strong>{teacherSnapshot.return_mode || 'pending'}</strong></div>
            <div><span>Exposure budget</span><strong>{teacherSnapshot.exposure_budget != null ? teacherSnapshot.exposure_budget.toFixed(2) : '-'}</strong></div>
            <div><span>Resource fit</span><strong>{teacherSnapshot.resource_fit != null ? `${Math.round(teacherSnapshot.resource_fit * 100)}%` : '-'}</strong></div>
            <div><span>Audit risk</span><strong>{auditSnapshot.multi_turn_reconstruction_risk != null ? auditSnapshot.multi_turn_reconstruction_risk.toFixed(2) : '-'}</strong></div>
          </div>

          <button className="attacker-profile-button" onClick={() => selectRole('attacker', 'Third-party attacker JSON')}>
            <ShieldAlert size={19} />
            <div><strong>Third-party Attacker</strong><span>Attack history and active controls</span></div>
            <Braces size={16} />
          </button>

          <button className="audit-snapshot-button" onClick={() => selectRole('audit', 'Audit and hash-chain JSON')}>
            <Database size={17} />
            Audit snapshot
            <CheckCircle2 size={15} />
          </button>
        </aside>
      </div>

      {selectedDetail && (
        <div className="classroom-json-backdrop" onClick={() => setSelectedDetail(null)}>
          <aside className="classroom-json-panel" onClick={(event) => event.stopPropagation()}>
            <div className="classroom-json-header">
              <div><Braces size={18} /><strong>{selectedDetail.title}</strong></div>
              <button onClick={() => setSelectedDetail(null)}>Close</button>
            </div>
            <pre>{JSON.stringify(selectedDetail.data, null, 2)}</pre>
          </aside>
        </div>
      )}
    </section>
  );
}

export default MultiRoundDialogue;
