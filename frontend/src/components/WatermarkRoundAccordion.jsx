import { useEffect, useState } from 'react';
import { CheckCircle2, Copy, FlaskConical, ShieldAlert } from 'lucide-react';
import './WatermarkRoundAccordion.css';

const shortHash = (value) => {
  if (!value) return '-';
  const text = String(value);
  return text.length > 34 ? `${text.slice(0, 18)}...${text.slice(-8)}` : text;
};

export default function WatermarkRoundAccordion({ sessionId = '' }) {
  const [payload, setPayload] = useState(null);
  const [openRound, setOpenRound] = useState(null);
  const [busyRound, setBusyRound] = useState(null);
  const [error, setError] = useState('');

  const loadRounds = async () => {
    setError('');
    try {
      const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
      const response = await fetch(`/api/watermark/rounds${query}`, { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      setPayload(data);
      setOpenRound(data.rounds?.[0]?.round_id ?? null);
    } catch (caughtError) {
      setError(caughtError.message);
    }
  };

  useEffect(() => {
    loadRounds();
  }, [sessionId]);

  const updateRoundDetection = (roundId, detection) => {
    setPayload((current) => ({
      ...current,
      rounds: (current?.rounds || []).map((round) => (
        round.round_id === roundId
          ? { ...round, detection_result: detection }
          : round
      )),
    }));
  };

  const detectRound = async (round) => {
    setBusyRound(round.round_id);
    setError('');
    try {
      const response = await fetch('/api/watermark/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: round.post_watermark_text,
          mode: 'evidence_bound',
          session_id: payload?.session_id,
          answer_id: round.answer_id,
          round_id: round.round_id,
          candidate_scope: 'selected_answer',
          audit_fields: {
            answer_id: round.answer_id,
            session_id: payload?.session_id,
            round_id: round.round_id,
            ...round.audit_fields_public,
            previous_audit_hash: round.previous_audit_hash,
          },
        }),
      });
      const result = await response.json();
      if (!response.ok || result.success === false) throw new Error(result.error || `HTTP ${response.status}`);
      updateRoundDetection(round.round_id, {
        watermark_detected: result.watermark_detected,
        detection_confidence: result.detection_confidence,
        tamper_suspicion: result.tamper_suspicion,
        detection_method: result.detection_method,
      });
    } catch (caughtError) {
      setError(caughtError.message);
    } finally {
      setBusyRound(null);
    }
  };

  const copyText = async (text) => {
    await navigator.clipboard?.writeText(text);
  };

  const rounds = payload?.rounds || [];

  return (
    <section className="watermark-round-accordion">
      <div className="round-accordion-header">
        <div>
          <span>Section 2</span>
          <h2>Multi-round Pre/Post Watermark Comparison</h2>
          <p>逐轮展示水印前教学草稿、水印后下发回答，以及公开可验证审计字段。</p>
        </div>
        <em>{payload?.data_source || 'loading'}</em>
      </div>

      {error && <div className="round-error"><ShieldAlert size={15} /> {error}</div>}
      {!rounds.length && !error && <div className="round-empty">正在加载多轮水印记录...</div>}

      <div className="round-list">
        {rounds.map((round) => {
          const expanded = openRound === round.round_id;
          const detection = round.detection_result || {};
          return (
            <article className={`round-item ${expanded ? 'expanded' : ''}`} key={`${round.round_id}-${round.answer_id}`}>
              <button type="button" className="round-summary" onClick={() => setOpenRound(expanded ? null : round.round_id)}>
                <span>Round {round.round_id}</span>
                <strong>{round.answer_id}</strong>
                <em>{round.watermark_id}</em>
                <b>{round.audit_fields_public?.return_mode || '-'}</b>
                <i>{Math.round((detection.detection_confidence || 0) * 100)}%</i>
                {round.chain_valid ? <CheckCircle2 size={16} /> : <ShieldAlert size={16} />}
              </button>

              {expanded && (
                <div className="round-detail">
                  <div className="pre-post-grid">
                    <section>
                      <h3>Pre-watermark Draft</h3>
                      <pre>{round.pre_watermark_text || 'No pre-watermark draft stored.'}</pre>
                    </section>
                    <section>
                      <h3>Post-watermark Protected Answer</h3>
                      <pre>{round.post_watermark_text || 'No protected answer stored.'}</pre>
                    </section>
                  </div>

                  <div className="round-field-grid">
                    <div><span>Changed sentences</span><strong>{round.diff_summary?.changed_sentence_count ?? 0}</strong></div>
                    <div><span>Protected spans</span><strong>{round.diff_summary?.protected_span_count ?? 0}</strong></div>
                    <div><span>Formula preserved</span><strong>{String(round.diff_summary?.formula_preserved ?? true)}</strong></div>
                    <div><span>Numbers preserved</span><strong>{String(round.diff_summary?.numbers_preserved ?? true)}</strong></div>
                    <div><span>Semantic similarity</span><strong>{round.diff_summary?.semantic_similarity ?? '-'}</strong></div>
                    <div><span>audit_digest</span><strong>{shortHash(round.audit_digest)}</strong></div>
                    <div><span>seed_commitment</span><strong>{shortHash(round.seed_commitment)}</strong></div>
                    <div><span>previous_audit_hash</span><strong>{shortHash(round.previous_audit_hash)}</strong></div>
                    <div><span>audit_hash</span><strong>{shortHash(round.audit_hash)}</strong></div>
                    <div><span>chain_valid</span><strong>{String(round.chain_valid)}</strong></div>
                  </div>

                  <div className="round-actions">
                    <button type="button" onClick={() => detectRound(round)} disabled={busyRound === round.round_id}>
                      <FlaskConical size={14} /> {busyRound === round.round_id ? '检测中...' : '检测本轮水印'}
                    </button>
                    <button type="button" onClick={() => copyText(round.post_watermark_text || '')}>
                      <Copy size={14} /> 复制水印后文本
                    </button>
                    <button type="button" onClick={() => copyText(JSON.stringify(round.audit_fields_public || {}, null, 2))}>
                      <Copy size={14} /> 复制公开审计字段
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
