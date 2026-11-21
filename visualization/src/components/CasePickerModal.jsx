import { useEffect, useRef, useState } from 'react';
import { AlertCircle, BookOpen, CheckCircle, MousePointer2, ShieldAlert, User, X } from 'lucide-react';

function formatKnowledge(item) {
  if (item?.knowledge_points?.length) return item.knowledge_points.join(' · ');
  return item?.knowledge_point || item?.episode_id || '未命名案例';
}

export default function CasePickerModal({ isOpen, cases, selectedIdx, onSelect, onClose }) {
  const overlayRef = useRef(null);
  const [previewIdx, setPreviewIdx] = useState(selectedIdx);

  useEffect(() => {
    if (isOpen) setPreviewIdx(selectedIdx);
  }, [isOpen, selectedIdx]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;
  const previewCase = cases[previewIdx] || cases[0];

  return (
    <div
      className="case-modal-overlay"
      ref={overlayRef}
      onClick={(event) => {
        if (event.target === overlayRef.current) onClose();
      }}
    >
      <div className="case-modal-container">
        <div className="case-modal-header">
          <div className="case-modal-header-left">
            <BookOpen size={22} />
            <div>
              <h2 className="case-modal-title">选择课堂案例</h2>
              <p className="case-modal-subtitle">已加载 {cases.length} 个案例，课堂与攻击演示都会绑定当前选择。</p>
            </div>
          </div>
          <button className="case-modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="case-picker-layout">
          <div className="case-modal-grid">
            {cases.map((item, index) => {
              const selected = index === selectedIdx;
              const previewing = index === previewIdx;
              return (
                <button
                  key={item.episode_id || index}
                  className={`case-card ${selected ? 'selected' : ''} ${previewing ? 'previewing' : ''}`}
                  onClick={() => setPreviewIdx(index)}
                  onDoubleClick={() => {
                    onSelect(index);
                    onClose();
                  }}
                >
                  {selected && (
                    <div className="case-card-check">
                      <CheckCircle size={16} />
                    </div>
                  )}
                  <div className="case-card-topline">
                    <span>#{index + 1}</span>
                    <span>{item.episode_id}</span>
                  </div>
                  <div className="case-card-kp">{formatKnowledge(item)}</div>
                  <div className="case-card-details">
                    <div className="case-card-detail-row">
                      <User size={12} />
                      <span>{item.student_level || '学段未设置'}</span>
                    </div>
                    <div className="case-card-detail-row">
                      <ShieldAlert size={12} />
                      <span>{item.attack_type || '未配置攻击类型'}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <aside className="case-preview-panel">
            <span className="case-preview-kicker"><MousePointer2 size={14} /> 单击预览 · 双击注入</span>
            <h3>{formatKnowledge(previewCase)}</h3>
            <div className="case-preview-id">{previewCase?.episode_id || '未选择案例'}</div>
            <dl>
              <div><dt>学生阶段</dt><dd>{previewCase?.student_level || '未设置'}</dd></div>
              <div><dt>攻击类型</dt><dd>{previewCase?.attack_type || '未配置'}</dd></div>
              <div><dt>课堂场景</dt><dd>{previewCase?.scenario_type || '未设置'}</dd></div>
              <div><dt>风险等级</dt><dd>{previewCase?.risk_level || '待评估'}</dd></div>
            </dl>
            <button
              className="case-preview-inject"
              onClick={() => {
                onSelect(previewIdx);
                onClose();
              }}
            >
              注入当前案例
            </button>
          </aside>
        </div>
      </div>
    </div>
  );
}
