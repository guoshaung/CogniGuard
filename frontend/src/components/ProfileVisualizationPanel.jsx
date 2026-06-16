import { useEffect, useMemo, useRef, useState } from 'react';
import { Atom, ShieldCheck, Sparkles, Move3d, Layers3, Orbit, Maximize2 } from 'lucide-react';

const POCKETS = [
  {
    id: 'abstract',
    title: '抽象画像层',
    subtitle: '稳定中间表示',
    detail: '融合多源输入后的统一表示，用于缓存、版本化与下游解耦。',
    color: '#60a5fa',
  },
  {
    id: 'learning',
    title: '学习子空间',
    subtitle: '掌握与错误模式',
    detail: '聚焦知识掌握、错误类型、学习阶段与进步趋势。',
    color: '#34d399',
  },
  {
    id: 'privacy',
    title: '隐私子空间',
    subtitle: '敏感度与可披露范围',
    detail: '控制哪些字段可被记录、审计与传递，确保最小披露。',
    color: '#22d3ee',
  },
  {
    id: 'teaching',
    title: '教学子空间',
    subtitle: '提示与支架策略',
    detail: '决定提示深度、变式偏好和讲解风格，服务于教师生成。',
    color: '#f59e0b',
  },
];

const CARD_STYLE = {
  abstract: { rotate: -4, depth: 18, tilt: 9, glow: 0.22 },
  learning: { rotate: 4, depth: 36, tilt: 11, glow: 0.24 },
  privacy: { rotate: 4, depth: 46, tilt: 10, glow: 0.26 },
  teaching: { rotate: -4, depth: 30, tilt: 10, glow: 0.23 },
};

const SNAP_OFFSETS = {
  abstract: { x: -265, y: -72 },
  learning: { x: -265, y: 78 },
  privacy: { x: 45, y: -72 },
  teaching: { x: 45, y: 78 },
};

const CARD_WIDTH = 240;
const CARD_HEIGHT = 158;
const STAGE_INSET = 34;
const SNAP_RADIUS = 190;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const createLayout = (width, height) => {
  const right = Math.max(STAGE_INSET, width - CARD_WIDTH - STAGE_INSET);
  const bottom = Math.max(STAGE_INSET, height - CARD_HEIGHT - STAGE_INSET);
  return {
    abstract: { ...CARD_STYLE.abstract, x: STAGE_INSET, y: STAGE_INSET },
    learning: { ...CARD_STYLE.learning, x: STAGE_INSET, y: bottom },
    privacy: { ...CARD_STYLE.privacy, x: right, y: STAGE_INSET },
    teaching: { ...CARD_STYLE.teaching, x: right, y: bottom },
  };
};

export default function ProfileVisualizationPanel({ profileEncoding, abstractProfile, studentProfile, runtimeStatus }) {
  const stageRef = useRef(null);
  const dragRef = useRef(null);
  const animationRef = useRef(null);
  const [draggingId, setDraggingId] = useState(null);
  const [positions, setPositions] = useState(() => createLayout(920, 500));
  const [stageSize, setStageSize] = useState({ width: 920, height: 500 });
  const [snappedId, setSnappedId] = useState(null);

  const labels = profileEncoding?.labels || {};
  const cards = useMemo(() => {
    const textualCards = profileEncoding?.textual_cards || {};
    return POCKETS.map((item) => ({
      ...item,
      text: textualCards[`${item.id}_card`] || item.detail,
    }));
  }, [profileEncoding]);

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

  useEffect(() => () => cancelAnimationFrame(animationRef.current), []);

  useEffect(() => {
    if (!dragRef.current) {
      setPositions(createLayout(stageSize.width, stageSize.height));
    }
  }, [stageSize.width, stageSize.height]);

  useEffect(() => {
    setPositions(createLayout(stageSize.width, stageSize.height));
    setSnappedId(null);
  }, [abstractProfile?.profile_id]);

  const getCore = () => ({
    x: stageSize.width / 2,
    y: stageSize.height / 2,
  });

  const getSnappedPosition = (id) => {
    const core = getCore();
    const offset = SNAP_OFFSETS[id];
    return {
      x: clamp(core.x + offset.x, STAGE_INSET, stageSize.width - CARD_WIDTH - STAGE_INSET),
      y: clamp(core.y + offset.y, STAGE_INSET, stageSize.height - CARD_HEIGHT - STAGE_INSET),
    };
  };

  const isNearCore = (position) => {
    const core = getCore();
    const cardCenterX = position.x + CARD_WIDTH / 2;
    const cardCenterY = position.y + CARD_HEIGHT / 2;
    return Math.hypot(cardCenterX - core.x, cardCenterY - core.y) < SNAP_RADIUS;
  };

  const settleCard = (id, position) => {
    const shouldSnap = isNearCore(position);
    const target = shouldSnap ? getSnappedPosition(id) : position;
    setSnappedId(shouldSnap ? id : null);
    setPositions((current) => ({
      ...current,
      [id]: {
        ...current[id],
        ...target,
        glow: shouldSnap ? 0.42 : CARD_STYLE[id].glow,
      },
    }));
  };

  const startInertia = (id, startPosition, velocity) => {
    cancelAnimationFrame(animationRef.current);
    let position = { ...startPosition };
    let nextVelocity = { ...velocity };

    const tick = () => {
      nextVelocity = { x: nextVelocity.x * 0.9, y: nextVelocity.y * 0.9 };
      position = {
        x: clamp(position.x + nextVelocity.x, STAGE_INSET, stageSize.width - CARD_WIDTH - STAGE_INSET),
        y: clamp(position.y + nextVelocity.y, STAGE_INSET, stageSize.height - CARD_HEIGHT - STAGE_INSET),
      };
      setPositions((current) => ({
        ...current,
        [id]: { ...current[id], ...position, glow: 0.32 },
      }));

      if (Math.hypot(nextVelocity.x, nextVelocity.y) > 0.65) {
        animationRef.current = requestAnimationFrame(tick);
      } else {
        settleCard(id, position);
      }
    };
    animationRef.current = requestAnimationFrame(tick);
  };

  const onPointerMove = (event, id) => {
    if (!dragRef.current || dragRef.current.id !== id) return;
    const rect = stageRef.current.getBoundingClientRect();
    const now = event.timeStamp;
    const x = clamp(event.clientX - rect.left - dragRef.current.offsetX, STAGE_INSET, rect.width - CARD_WIDTH - STAGE_INSET);
    const y = clamp(event.clientY - rect.top - dragRef.current.offsetY, STAGE_INSET, rect.height - CARD_HEIGHT - STAGE_INSET);
    const elapsed = Math.max(8, now - dragRef.current.time);
    dragRef.current.velocity = {
      x: ((x - dragRef.current.x) / elapsed) * 16,
      y: ((y - dragRef.current.y) / elapsed) * 16,
    };
    dragRef.current.x = x;
    dragRef.current.y = y;
    dragRef.current.time = now;
    setSnappedId(isNearCore({ x, y }) ? id : null);
    setPositions((current) => ({
      ...current,
      [id]: { ...current[id], x, y, glow: 0.4 },
    }));
  };

  const releaseCard = (id) => {
    if (!dragRef.current || dragRef.current.id !== id) return;
    const { x, y, velocity } = dragRef.current;
    dragRef.current = null;
    setDraggingId(null);
    if (isNearCore({ x, y })) {
      settleCard(id, { x, y });
      return;
    }
    startInertia(id, { x, y }, velocity);
  };

  const core = getCore();

  return (
    <section className="profile-viz-shell">
      <div className="profile-viz-hero">
        <div>
          <div className="profile-viz-eyebrow"><Layers3 size={14} /> 中文画像可视化面板</div>
          <h2>抽象画像层 + 三分解耦 + 3D 拖动展示</h2>
          <p>拖动卡片可观察画像层之间的连接关系。卡片带有惯性，靠近核心时会自动吸附到稳定轨道。</p>
        </div>
        <div className="profile-viz-hero-stat">
          <div><Sparkles size={16} /> {runtimeStatus?.runtime_mode || '运行中'}</div>
          <div><ShieldCheck size={16} /> {abstractProfile?.encoding_model || 'microsoft/deberta-v3-large'}</div>
        </div>
      </div>

      <div className="profile-viz-stage">
        <div
          className="profile-viz-orbital"
          ref={stageRef}
          onPointerMove={(event) => {
            if (dragRef.current) onPointerMove(event, dragRef.current.id);
          }}
          onPointerUp={() => {
            if (dragRef.current) releaseCard(dragRef.current.id);
          }}
          onPointerCancel={() => {
            if (dragRef.current) releaseCard(dragRef.current.id);
          }}
          onPointerLeave={() => {
            if (dragRef.current) releaseCard(dragRef.current.id);
          }}
        >
          <div className="profile-viz-grid" />
          <div className="profile-viz-particles" aria-hidden="true">
            {Array.from({ length: 22 }, (_, index) => (
              <i key={index} style={{ '--particle-index': index }} />
            ))}
          </div>
          <div className="profile-viz-rings"><span /><span /><span /></div>
          <svg
            className="profile-viz-links"
            viewBox={`0 0 ${stageSize.width} ${stageSize.height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <filter id="profile-link-glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>
            {cards.map((card) => {
              const position = positions[card.id];
              return (
                <g key={card.id}>
                  <line
                    x1={position.x + CARD_WIDTH / 2}
                    y1={position.y + CARD_HEIGHT / 2}
                    x2={core.x}
                    y2={core.y}
                    stroke={card.color}
                    strokeWidth={snappedId === card.id ? 2.6 : 1.4}
                    strokeDasharray={snappedId === card.id ? '0' : '7 8'}
                    opacity={snappedId === card.id ? 0.8 : 0.34}
                    filter="url(#profile-link-glow)"
                  />
                  <circle r="3.5" fill={card.color} opacity="0.9">
                    <animateMotion
                      dur={`${2.4 + cards.indexOf(card) * 0.35}s`}
                      repeatCount="indefinite"
                      path={`M ${position.x + CARD_WIDTH / 2} ${position.y + CARD_HEIGHT / 2} L ${core.x} ${core.y}`}
                    />
                  </circle>
                </g>
              );
            })}
          </svg>
          <div className={`profile-viz-core ${snappedId ? 'is-attracting' : ''}`}>
            <div className="profile-viz-core-inner">
              <Orbit size={22} />
              <Atom size={28} />
              <strong>画像核心</strong>
              <span>{snappedId ? '正在吸附' : '抽象表示'}</span>
            </div>
          </div>
          {cards.map((card) => {
            const pos = positions[card.id];
            const isDragging = draggingId === card.id;
            const isSnapped = snappedId === card.id;
            return (
              <button
                key={card.id}
                type="button"
                className={`profile-viz-card ${isDragging ? 'dragging' : ''} ${isSnapped ? 'snapped' : ''}`}
                onPointerDown={(event) => {
                  cancelAnimationFrame(animationRef.current);
                  const cardRect = event.currentTarget.getBoundingClientRect();
                  dragRef.current = {
                    id: card.id,
                    offsetX: event.clientX - cardRect.left,
                    offsetY: event.clientY - cardRect.top,
                    x: pos.x,
                    y: pos.y,
                    time: event.timeStamp,
                    velocity: { x: 0, y: 0 },
                  };
                  setDraggingId(card.id);
                }}
                style={{
                  transform: `translate3d(${pos.x}px, ${pos.y}px, ${pos.depth}px) rotateX(${pos.tilt}deg) rotateY(-${pos.tilt - 4}deg) rotate(${pos.rotate}deg) scale(${isDragging ? 1.04 : 1})`,
                  borderColor: card.color,
                  boxShadow: `0 18px 44px rgba(0,0,0,${isDragging ? 0.44 : 0.34}), 0 0 0 1px ${card.color}33 inset, 0 0 42px ${card.color}${isDragging || isSnapped ? '88' : '55'}`,
                  zIndex: isDragging ? 10 : 3,
                }}
              >
                <div className="profile-viz-card-top">
                  <span style={{ color: card.color }}>{card.subtitle}</span>
                  <Move3d size={15} />
                </div>
                <strong>{card.title}</strong>
                <p>{card.text}</p>
                <div className="profile-viz-card-footer">
                  <span style={{ background: `${card.color}22`, color: card.color }}>
                    {isSnapped ? '已接入核心' : '可拖动'}
                  </span>
                  <Maximize2 size={13} />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="profile-viz-metrics">
        <div><span>抽象画像 ID</span><strong>{abstractProfile?.profile_id || '待生成'}</strong></div>
        <div><span>编码维度</span><strong>{abstractProfile?.embedding_dim || 0}</strong></div>
        <div><span>学习标签</span><strong>{labels.mastery_level || studentProfile?.student_level || '未知'}</strong></div>
        <div><span>隐私标签</span><strong>{labels.sensitivity_level || '未知'}</strong></div>
      </div>
    </section>
  );
}
