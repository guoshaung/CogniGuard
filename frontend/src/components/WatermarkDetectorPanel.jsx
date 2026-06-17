import { useMemo, useState } from 'react';
import { CheckCircle2, SearchCheck, ShieldAlert } from 'lucide-react';
import './WatermarkDetectorPanel.css';

const publicAuditKeys = [
  'answer_id',
  'session_id',
  'round_id',
  'profile_card_id',
  'resource_id',
  'chunk_id',
  'return_mode',
  'risk_state',
  'policy_decision',
  'previous_audit_hash',
  'timestamp_bucket',
];

const shortValue = (value) => {
  if (value === null || value === undefined || value === '') return '-';
  const text = String(value);
  return text.length > 42 ? `${text.slice(0, 24)}...${text.slice(-10)}` : text;
};

export default function WatermarkDetectorPanel({ defaultText = '', auditTrace = {}, sessionId = '' }) {
  const [text, setText] = useState(defaultText || '');
  const [mode, setMode] = useState('blind_scan');
  const [candidateScope, setCandidateScope] = useState('current_session');
  const [answerId, setAnswerId] = useState(auditTrace.answer_id || '');
  const [roundId, setRoundId] = useState(auditTrace.audit_record?.round_id || '');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const auditFields = useMemo(() => {
    const record = auditTrace.audit_record || {};
    const trace = record.resource_trace?.[0] || {};
    return {
      answer_id: answerId || record.answer_id || auditTrace.answer_id || '',
      session_id: sessionId || record.session_id || '',
      round_id: roundId || record.round_id || '',
      profile_card_id: record.profile_card_id || auditTrace.profile_card_id || '',
      resource_id: trace.resource_id || auditTrace.resource_id || '',
      chunk_id: trace.chunk_id || auditTrace.chunk_id || '',
      return_mode: trace.return_mode || '',
      risk_state: record.risk_state || '',
      policy_decision: record.policy_decision || '',
      previous_audit_hash: record.previous_audit_hash || auditTrace.multi_round_binding?.previous_audit_hash || '',
      timestamp_bucket: record.timestamp_bucket || '',
    };
  }, [answerId, auditTrace, roundId, sessionId]);

  const runDetection = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/watermark/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          mode,
          session_id: sessionId || auditFields.session_id,
          answer_id: answerId || undefined,
          round_id: roundId || undefined,
          candidate_scope: candidateScope,
          audit_fields: mode === 'evidence_bound' ? auditFields : {},
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setResult(payload);
    } catch (caughtError) {
      setError(caughtError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="watermark-detector-panel">
      <div className="watermark-detector-header">
        <div>
          <span>Section 1</span>
          <h2>MR-SEB-HSW-ST Detection Console</h2>
          <p>粘贴最终回答、攻击后文本或转发文本，验证语义水印、seed commitment 与 evidence-chain。</p>
        </div>
        <SearchCheck size={30} />
      </div>

      <div className="watermark-detector-grid">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="粘贴需要检测的回答文本..."
          rows={7}
        />
        <aside>
          <label>
            <span>检测模式</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="evidence_bound">Evidence-bound verification</option>
              <option value="blind_scan">Blind scan in current session</option>
            </select>
          </label>
          <label>
            <span>candidate_scope</span>
            <select value={candidateScope} onChange={(event) => setCandidateScope(event.target.value)}>
              <option value="current_session">current_session</option>
              <option value="all_recent">all_recent</option>
              <option value="selected_answer">selected_answer</option>
            </select>
          </label>
          <label>
            <span>answer_id optional</span>
            <input value={answerId} onChange={(event) => setAnswerId(event.target.value)} />
          </label>
          <label>
            <span>round_id optional</span>
            <input value={roundId} onChange={(event) => setRoundId(event.target.value)} />
          </label>
          <button type="button" onClick={runDetection} disabled={busy}>
            {busy ? '检测中...' : '检测水印 / Verify Watermark'}
          </button>
        </aside>
      </div>

      {error && <div className="watermark-detector-error"><ShieldAlert size={15} /> {error}</div>}

      {result && (
        <div className={`watermark-detection-result ${result.tamper_suspicion ? 'warn' : 'ok'}`}>
          <div className="result-headline">
            {result.tamper_suspicion ? <ShieldAlert size={20} /> : <CheckCircle2 size={20} />}
            <strong>{result.watermark_detected ? 'Watermark detected' : 'Watermark not confirmed'}</strong>
            <span>{Math.round((result.detection_confidence || 0) * 100)}%</span>
          </div>
          <div className="result-metrics">
            <div><span>matched_round_id</span><strong>{shortValue(result.matched_round_id)}</strong></div>
            <div><span>seed_binding_valid</span><strong>{String(result.seed_binding_valid)}</strong></div>
            <div><span>audit_chain_valid</span><strong>{String(result.audit_chain_valid)}</strong></div>
            <div><span>tamper_suspicion</span><strong>{String(result.tamper_suspicion)}</strong></div>
            <div><span>semantic_similarity</span><strong>{result.semantic_preservation?.semantic_similarity ?? '-'}</strong></div>
            <div><span>detection_method</span><strong>{result.detection_method}</strong></div>
          </div>
          <details>
            <summary>公开验证字段 public verification fields</summary>
            <div className="public-field-grid">
              <div><span>audit_digest</span><strong>{shortValue(result.audit_digest)}</strong></div>
              <div><span>seed_commitment</span><strong>{shortValue(result.seed_commitment)}</strong></div>
              <div><span>audit_hash</span><strong>{shortValue(result.audit_hash)}</strong></div>
              <div><span>previous_audit_hash</span><strong>{shortValue(result.previous_audit_hash)}</strong></div>
              {publicAuditKeys.map((key) => (
                <div key={key}><span>{key}</span><strong>{shortValue(result.matched_evidence?.[key] || auditFields[key])}</strong></div>
              ))}
            </div>
          </details>
          <p>{result.explanation}</p>
        </div>
      )}
    </section>
  );
}
