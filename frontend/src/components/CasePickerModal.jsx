import React, { useEffect, useRef } from 'react';
import { BookOpen, Brain, Hash, AlertCircle, TrendingUp, X, CheckCircle } from 'lucide-react';

/**
 * CasePickerModal — Full-screen overlay showing diagnostic case cards.
 *
 * Props:
 *   isOpen: boolean
 *   cases: Array<object>
 *   selectedIdx: number
 *   onSelect: (index: number) => void
 *   onClose: () => void
 */

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

function truncateHash(hash) {
  if (!hash) return '—';
  return `${hash.substring(0, 8)}…${hash.substring(hash.length - 4)}`;
}

export default function CasePickerModal({ isOpen, cases, selectedIdx, onSelect, onClose }) {
  const overlayRef = useRef(null);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCardClick = (idx) => {
    onSelect(idx);
    // Short delay to show selection animation before closing
    setTimeout(() => onClose(), 350);
  };

  return (
    <div className="case-modal-overlay" ref={overlayRef} onClick={(e) => {
      if (e.target === overlayRef.current) onClose();
    }}>
      <div className="case-modal-container">
        {/* Header */}
        <div className="case-modal-header">
          <div className="case-modal-header-left">
            <BookOpen size={22} style={{ color: 'var(--color-blue)' }} />
            <div>
              <h2 className="case-modal-title">选择诊断案例 / Select Diagnostic Case</h2>
              <p className="case-modal-subtitle">
                共 {cases.length} 个案例 — 点击卡片选择案例并启动防护流水线
              </p>
            </div>
          </div>
          <button className="case-modal-close" onClick={onClose} title="Close">
            <X size={20} />
          </button>
        </div>

        {/* Card Grid */}
        <div className="case-modal-grid">
          {cases.map((item, index) => {
            const isSelected = index === selectedIdx;
            return (
              <div
                key={index}
                className={`case-card ${isSelected ? 'selected' : ''}`}
                onClick={() => handleCardClick(index)}
                style={{ animationDelay: `${index * 40}ms` }}
              >
                {/* Selection indicator */}
                {isSelected && (
                  <div className="case-card-check">
                    <CheckCircle size={18} />
                  </div>
                )}

                {/* Card number */}
                <div className="case-card-number">#{index + 1}</div>

                {/* Knowledge point */}
                <div className="case-card-kp">
                  <span className="case-card-icon">{getKnowledgeIcon(item.knowledge_point)}</span>
                  <span className="case-card-kp-text">{item.knowledge_point || 'Unknown'}</span>
                </div>

                {/* Details grid */}
                <div className="case-card-details">
                  <div className="case-card-detail-row">
                    <Hash size={12} />
                    <span className="case-card-detail-label">学生 Hash</span>
                    <span className="case-card-detail-value">{truncateHash(item.student_hash)}</span>
                  </div>

                  {item.common_error_type && (
                    <div className="case-card-detail-row">
                      <AlertCircle size={12} />
                      <span className="case-card-detail-label">错误类型</span>
                      <span className="case-card-detail-value error-type">{item.common_error_type}</span>
                    </div>
                  )}

                  {item.learner_state_summary && (
                    <div className="case-card-detail-row">
                      <TrendingUp size={12} />
                      <span className="case-card-detail-label">学习状态</span>
                      <span className="case-card-detail-value">{item.learner_state_summary}</span>
                    </div>
                  )}

                  {item.task_id && (
                    <div className="case-card-detail-row">
                      <Brain size={12} />
                      <span className="case-card-detail-label">任务 ID</span>
                      <span className="case-card-detail-value mono">{item.task_id}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
