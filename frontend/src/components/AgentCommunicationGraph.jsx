import { useEffect, useMemo, useRef, useState } from 'react';
import { Atom, Globe2, GitBranch, Orbit, Rotate3d } from 'lucide-react';
import DecisionBadge from './DecisionBadge';

const AGENTS = [
  { id: 'profile_diagnosis_agent', label: '画像诊断代理', logLabel: 'ProfileDiagnosis', color: '#60a5fa', angle: 215, radius: 210 },
  { id: 'copyright_aware_resource_agent', label: '版权资源代理', logLabel: 'CopyrightAwareResource', color: '#38bdf8', angle: 325, radius: 225 },
  { id: 'pedagogical_teaching_agent', label: '教学代理', logLabel: 'PedagogicalTeaching', color: '#34d399', angle: 35, radius: 220 },
  { id: 'learning_assessment_agent', label: '学习评估代理', logLabel: 'LearningAssessment', color: '#22d3ee', angle: 145, radius: 205 },
];

const DOCK_OFFSETS = [
  { x: -39, y: -30 },
  { x: 14, y: -34 },
  { x: -32, y: 20 },
  { x: 22, y: 17 },
];

const toRadians = (degrees) => (degrees * Math.PI) / 180;
const toDegrees = (radians) => (radians * 180) / Math.PI;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export default function AgentCommunicationGraph({ communicationLogs, pipelineData, onAblationChange }) {
  const logs = communicationLogs || pipelineData?.communication_logs || [];
  const stageRef = useRef(null);
  const animationRef = useRef(null);
  const lastFrameRef = useRef(0);
  const dragRef = useRef(null);
  const globeDragRef = useRef(null);
  const [selectedRow, setSelectedRow] = useState(null);
  const [stageSize, setStageSize] = useState({ width: 760, height: 520 });
  const [globeRotation, setGlobeRotation] = useState({ x: -12, y: 24 });
  const [agents, setAgents] = useState(() =>
    Object.fromEntries(AGENTS.map((agent) => [
      agent.id,
      {
        mode: 'docked',
        angle: agent.angle,
        radius: agent.radius,
        speed: 0,
        x: 0,
        y: 0,
      },
    ])),
  );

  const center = useMemo(
    () => ({ x: stageSize.width / 2, y: stageSize.height / 2 }),
    [stageSize],
  );

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return undefined;
    const updateSize = () => {
      const rect = stage.getBoundingClientRect();
      setStageSize({ width: rect.width, height: rect.height });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const animate = (timestamp) => {
      const elapsed = lastFrameRef.current ? Math.min(40, timestamp - lastFrameRef.current) : 16;
      lastFrameRef.current = timestamp;
      setAgents((current) => {
        let changed = false;
        const next = { ...current };
        AGENTS.forEach((agent) => {
          const state = current[agent.id];
          if (state.mode !== 'orbit') return;
          changed = true;
          next[agent.id] = {
            ...state,
            angle: (state.angle + (state.speed * elapsed) / 1000 + 360) % 360,
          };
        });
        return changed ? next : current;
      });
      animationRef.current = requestAnimationFrame(animate);
    };
    animationRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationRef.current);
  }, []);

  const dockedIds = useMemo(
    () => AGENTS.filter((agent) => agents[agent.id].mode === 'docked').map((agent) => agent.id),
    [agents],
  );

  const experimentSummary = useMemo(() => {
    const orbitingAgents = AGENTS
      .filter((agent) => agents[agent.id].mode !== 'docked')
      .map((agent) => agent.label);
    return {
      cut_nodes: orbitingAgents,
      tpcs_active_links: dockedIds.length,
      experiment_mode: dockedIds.length === AGENTS.length ? 'full_topology' : 'orbital_ablation',
    };
  }, [agents, dockedIds.length]);

  useEffect(() => {
    onAblationChange?.(experimentSummary);
  }, [experimentSummary, onAblationChange]);

  const getAgentPosition = (agent, index) => {
    const state = agents[agent.id];
    if (state.mode === 'dragging') return { x: state.x, y: state.y };
    if (state.mode === 'docked') {
      const dockIndex = dockedIds.indexOf(agent.id);
      const offset = DOCK_OFFSETS[Math.max(0, dockIndex)] || DOCK_OFFSETS[index];
      return { x: center.x + offset.x - 28, y: center.y + offset.y - 28 };
    }
    const angle = toRadians(state.angle);
    return {
      x: center.x + Math.cos(angle) * state.radius - 32,
      y: center.y + Math.sin(angle) * state.radius * 0.53 - 32,
    };
  };

  const beginAgentDrag = (event, agent) => {
    const rect = stageRef.current.getBoundingClientRect();
    const position = getAgentPosition(agent, AGENTS.indexOf(agent));
    dragRef.current = {
      id: agent.id,
      originMode: agents[agent.id].mode,
      offsetX: event.clientX - rect.left - position.x,
      offsetY: event.clientY - rect.top - position.y,
      x: position.x,
      y: position.y,
      clientX: event.clientX,
      clientY: event.clientY,
      minPointerDistance: Math.hypot(
        event.clientX - rect.left - center.x,
        event.clientY - rect.top - center.y,
      ),
      time: event.timeStamp,
      velocity: { x: 0, y: 0 },
    };
    setAgents((current) => ({
      ...current,
      [agent.id]: { ...current[agent.id], mode: 'dragging', x: position.x, y: position.y },
    }));
  };

  const moveAgent = (event, agentId) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== agentId) return;
    const rect = stageRef.current.getBoundingClientRect();
    const x = clamp(event.clientX - rect.left - drag.offsetX, 4, rect.width - 68);
    const y = clamp(event.clientY - rect.top - drag.offsetY, 4, rect.height - 68);
    const elapsed = Math.max(8, event.timeStamp - drag.time);
    drag.velocity = {
      x: ((x - drag.x) / elapsed) * 16,
      y: ((y - drag.y) / elapsed) * 16,
    };
    drag.x = x;
    drag.y = y;
    drag.clientX = event.clientX;
    drag.clientY = event.clientY;
    drag.minPointerDistance = Math.min(
      drag.minPointerDistance,
      Math.hypot(
        event.clientX - rect.left - center.x,
        event.clientY - rect.top - center.y,
      ),
    );
    drag.time = event.timeStamp;
    setAgents((current) => ({
      ...current,
      [agentId]: { ...current[agentId], x, y },
    }));
  };

  const finishAgentDrag = (agentId) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== agentId) return;
    dragRef.current = null;
    const ballCenter = { x: drag.x + 32, y: drag.y + 32 };
    const dx = ballCenter.x - center.x;
    const dy = ballCenter.y - center.y;
    const distance = Math.hypot(dx, dy);
    const stageRect = stageRef.current.getBoundingClientRect();
    const pointerDistance = Math.hypot(
      drag.clientX - stageRect.left - center.x,
      drag.clientY - stageRect.top - center.y,
    );

    const enteredCoreFromOrbit =
      drag.originMode !== 'docked' && drag.minPointerDistance < 108;
    if (distance < 118 || pointerDistance < 118 || enteredCoreFromOrbit) {
      setAgents((current) => ({
        ...current,
        [agentId]: { ...current[agentId], mode: 'docked', speed: 0 },
      }));
      return;
    }

    const radius = clamp(distance, 155, Math.min(270, stageSize.width * 0.38));
    const angle = toDegrees(Math.atan2(dy / 0.53, dx));
    const tangentX = -dy;
    const tangentY = dx;
    const tangentLength = Math.max(1, Math.hypot(tangentX, tangentY));
    const tangentialVelocity =
      (drag.velocity.x * tangentX + drag.velocity.y * tangentY) / tangentLength;
    const fallbackDirection = agents[agentId].speed < 0 ? -1 : 1;
    const direction = Math.abs(tangentialVelocity) > 0.25
      ? Math.sign(tangentialVelocity)
      : fallbackDirection;
    const speed = direction * clamp(Math.abs(tangentialVelocity) * 13, 7, 58);

    setAgents((current) => ({
      ...current,
      [agentId]: {
        ...current[agentId],
        mode: 'orbit',
        angle,
        radius,
        speed,
      },
    }));
  };

  const beginGlobeDrag = (event) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    globeDragRef.current = {
      x: event.clientX,
      y: event.clientY,
      rotation: globeRotation,
    };
  };

  const rotateGlobe = (event) => {
    const drag = globeDragRef.current;
    if (!drag) return;
    setGlobeRotation({
      x: clamp(drag.rotation.x - (event.clientY - drag.y) * 0.35, -55, 55),
      y: drag.rotation.y + (event.clientX - drag.x) * 0.42,
    });
  };

  const stopGlobeDrag = () => {
    globeDragRef.current = null;
  };

  return (
    <section className="content-stack communications-panel-container">
      <div className="section-header tpcs-orbit-heading">
        <div>
          <span className="tpcs-orbit-kicker"><GitBranch size={15} /> 核式主动中介路由</span>
          <h1>TPCS 地球仪与代理轨道实验台</h1>
          <p>
            拖动地球仪可旋转观察 TPCS 核心。把代理核子拖入地球仪会接入为内部模块；
            从核心向外甩出时，代理会沿释放方向并按拖动速度进入持续轨道。
          </p>
        </div>
      </div>

      <div className="tpcs-orbit-layout">
        <div
          className="tpcs-orbit-stage"
          ref={stageRef}
          onPointerMove={(event) => {
            if (dragRef.current) moveAgent(event, dragRef.current.id);
            if (globeDragRef.current) rotateGlobe(event);
          }}
          onPointerUp={() => {
            if (dragRef.current) finishAgentDrag(dragRef.current.id);
            stopGlobeDrag();
          }}
          onPointerCancel={() => {
            if (dragRef.current) finishAgentDrag(dragRef.current.id);
            stopGlobeDrag();
          }}
          onPointerLeave={() => {
            if (dragRef.current) finishAgentDrag(dragRef.current.id);
            stopGlobeDrag();
          }}
        >
          <div className="orbit-starfield" aria-hidden="true" />
          {[175, 220, 265].map((radius) => (
            <div
              className="agent-orbit-ring"
              key={radius}
              style={{ width: radius * 2, height: radius * 1.06 }}
            />
          ))}

          <button
            type="button"
            className="tpcs-globe"
            style={{
              '--globe-rotate-x': `${globeRotation.x}deg`,
              '--globe-rotate-y': `${globeRotation.y}deg`,
            }}
            onPointerDown={beginGlobeDrag}
            onPointerMove={rotateGlobe}
            onPointerUp={stopGlobeDrag}
            onPointerCancel={stopGlobeDrag}
            aria-label="拖动旋转 TPCS 地球仪"
          >
            <span className="globe-halo" />
            <span className="globe-sphere">
              <span className="globe-grid globe-grid-longitude" />
              <span className="globe-grid globe-grid-latitude" />
              <span className="globe-continent continent-a" />
              <span className="globe-continent continent-b" />
              <span className="globe-continent continent-c" />
              <span className="globe-shine" />
            </span>
            <span className="globe-label"><Globe2 size={18} /> TPCS 核心</span>
          </button>

          {AGENTS.map((agent, index) => {
            const state = agents[agent.id];
            const position = getAgentPosition(agent, index);
            const isDocked = state.mode === 'docked';
            return (
              <button
                key={agent.id}
                type="button"
                className={`agent-nucleon ${state.mode}`}
                style={{
                  '--agent-color': agent.color,
                  transform: `translate3d(${position.x}px, ${position.y}px, 0)`,
                }}
                onPointerDown={(event) => beginAgentDrag(event, agent)}
                onPointerUp={() => finishAgentDrag(agent.id)}
                onPointerCancel={() => finishAgentDrag(agent.id)}
                aria-label={`拖动${agent.label}`}
              >
                <span className="nucleon-shell">
                  <span className="nucleon-core"><Atom size={isDocked ? 15 : 20} /></span>
                  <span className="nucleon-orbit orbit-one" />
                  <span className="nucleon-orbit orbit-two" />
                </span>
                {!isDocked && <strong>{agent.label}</strong>}
              </button>
            );
          })}

          <div className="orbit-help">
            <Rotate3d size={15} /> 拖动地球旋转
            <span />
            <Orbit size={15} /> 甩出速度决定公转速度
          </div>
        </div>

        <aside className="tpcs-orbit-status">
          <div className="orbit-summary-card">
            <span>核心拓扑状态</span>
            <strong>{dockedIds.length}/{AGENTS.length} 个代理已接入</strong>
            <div className="orbit-summary-bar">
              <i style={{ width: `${(dockedIds.length / AGENTS.length) * 100}%` }} />
            </div>
            <p>{dockedIds.length === AGENTS.length ? '完整拓扑已形成' : '轨道中的代理处于消融运行态'}</p>
          </div>

          {AGENTS.map((agent) => {
            const state = agents[agent.id];
            const docked = state.mode === 'docked';
            return (
              <div className={`orbit-agent-status ${docked ? 'docked' : 'orbiting'}`} key={agent.id}>
                <span className="status-nucleon" style={{ '--agent-color': agent.color }} />
                <div>
                  <strong>{agent.label}</strong>
                  <span>
                    {docked
                      ? '已进入 TPCS，作为内部受控模块运行'
                      : `轨道运行 · ${Math.abs(state.speed).toFixed(0)}°/秒 · ${state.speed >= 0 ? '顺时针' : '逆时针'}`}
                  </span>
                </div>
                <b>{docked ? '核心接入' : '轨道消融'}</b>
              </div>
            );
          })}
        </aside>
      </div>

      <div className="data-panel tpcs-log-panel">
        <div className="data-panel-title">TPCS 路由日志</div>
        <div style={{ overflowX: 'auto' }}>
          <table className="cg-table" style={{ margin: 0 }}>
            <thead>
              <tr>
                <th>发送方</th>
                <th>接收方</th>
                <th>消息类型</th>
                <th>隐私等级</th>
                <th>披露风险</th>
                <th>决策</th>
              </tr>
            </thead>
            <tbody>
              {logs.length > 0 ? (
                logs.map((log, index) => (
                  <tr
                    key={`${log.sender || 'route'}-${index}`}
                    onClick={() => setSelectedRow(selectedRow === index ? null : index)}
                    style={{ cursor: 'pointer', background: selectedRow === index ? 'rgba(14,165,233,0.08)' : undefined }}
                  >
                    <td>{log.sender}</td>
                    <td>{log.receiver}</td>
                    <td>{log.message_type}</td>
                    <td>{log.privacy_level}</td>
                    <td>{Number(log.disclosure_score ?? 0).toFixed(2)}</td>
                    <td><DecisionBadge decision={log.tpcs_decision || 'allow'} /></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', color: 'var(--muted)' }}>
                    运行一轮课堂后，这里会显示真实的 TPCS 路由与审计记录。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
