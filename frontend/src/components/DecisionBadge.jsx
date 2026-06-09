import React from 'react';

export default function DecisionBadge({ decision }) {
  const norm = String(decision || 'not_enabled').toLowerCase().trim();
  
  let label = '未启用 / Not Ingested';
  let className = 'badge-gray';

  if (norm.includes('allow') || norm.includes('approve') || norm.includes('passed') || norm.includes('accept') || norm.includes('success')) {
    label = '允许 / Allow';
    className = 'badge-green';
  } else if (norm.includes('sanitize') || norm.includes('obfuscate') || norm.includes('rewrite') || norm.includes('clean')) {
    label = '净化 / Sanitize';
    className = 'badge-blue';
  } else if (norm.includes('degrade')) {
    label = '降级 / Degrade';
    className = 'badge-orange';
  } else if (norm.includes('block') || norm.includes('refuse') || norm.includes('deny') || norm.includes('denied') || norm.includes('high') || norm.includes('intercept')) {
    label = '阻断 / Refuse';
    className = 'badge-red';
  } else if (norm.includes('not_enabled') || norm.includes('not-enabled') || norm.includes('disabled') || norm.includes('not_triggered')) {
    label = '未启用 / Not Enabled';
    className = 'badge-gray';
  } else {
    // default/fallback matching
    label = decision;
    className = 'badge-gray';
  }

  return (
    <span className={`cg-decision-badge ${className}`}>
      {label}
    </span>
  );
}
