import React from 'react';
import { Terminal, X } from 'lucide-react';

export default function JsonDrawer({ isOpen, onClose, data, title }) {
  if (!isOpen) return null;

  return (
    <div className="json-drawer-backdrop" onClick={onClose}>
      <div className="json-drawer-content" onClick={(e) => e.stopPropagation()}>
        <div className="json-drawer-header">
          <div className="json-drawer-title">
            <Terminal size={18} style={{ color: 'var(--color-blue)' }} />
            <span>{title || 'Raw Response Details'}</span>
          </div>
          <button className="json-drawer-close" onClick={onClose} aria-label="Close raw JSON response drawer">
            <X size={20} />
          </button>
        </div>
        <div className="json-drawer-body">
          <pre className="json-block output" style={{ maxHeight: '100%', overflowY: 'auto', margin: 0 }}>
            {JSON.stringify(data ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
