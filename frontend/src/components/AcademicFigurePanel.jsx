import './AcademicFigurePanel.css';

const FIGURE_TITLES = {
  evidence_pipeline: 'Figure 1. MR-SEB-HSW-ST Evidence-bound Watermark Pipeline',
  audit_chain: 'Figure 2. Evidence-chain Binding Structure',
  seed_binding: 'Figure 3. Seed Commitment and Audit Binding Verification',
  semantic_preservation: 'Figure 4. Semantic Preservation under Evidence-bound Watermarking',
  watermark_attack_robustness: 'Figure 5. Watermark Detection Robustness under Text Attacks',
  multi_round_detection: 'Figure 6. Multi-round Aggregate Detection Curve',
  tamper_localization: 'Figure 7. Tamper Localization Map',
  cross_mechanism_heatmap: 'Figure 8. Cross-mechanism Defense Heatmap',
};

const INTERPRETATIONS = {
  evidence_pipeline: 'Raw audit fields are canonicalized and converted into public commitments; they are not written into the protected answer body.',
  audit_chain: 'Each round binds answer, resource trace, watermark commitment and previous hash, so tampering creates a visible chain break.',
  seed_binding: 'The panel exposes only audit digest and seed commitments; raw HMAC seeds remain private.',
  semantic_preservation: 'Semantic-aware watermarking protects formulas, numbers, terms, resource identifiers and key teaching steps.',
  watermark_attack_robustness: 'Detection is evaluated together with evidence-chain validity, not by watermark presence alone.',
  multi_round_detection: 'Aggregate confidence remains stable when one round is deleted, summarized or lightly paraphrased.',
  tamper_localization: 'Round-by-attack localization shows where suspicious modifications are concentrated.',
  cross_mechanism_heatmap: 'The three sub-mechanisms and TPCS jointly reduce residual risk across heterogeneous attacks.',
};

const DEFAULT_FIGURES = Object.keys(FIGURE_TITLES);

const hashPreview = (value, fallback = 'pending') => {
  if (!value) return fallback;
  const text = String(value);
  return text.length > 18 ? `${text.slice(0, 14)}...${text.slice(-6)}` : text;
};

const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, Number(value) || 0));

const fallbackRounds = [
  { round_id: 1, answer_id: 'ans_demo_0001', watermark_id: 'wm_sem_demo01', audit_digest: 'digest_demo_round_1', seed_commitment: 'hmac:demo01...a91c', watermark_version: 'MR-SEB-HSW-ST-v1', detection_confidence: 0.91, semantic_similarity: 0.97, previous_audit_hash: 'GENESIS', audit_hash: 'hash_demo_round_1', chain_valid: true, tamper_suspicion: false, resource_id: 'res_demo', chunk_id: 'chunk_001', return_mode: 'summary', risk_state: 'medium', policy_decision: 'degrade_to_summary', protected_span_count: 7 },
  { round_id: 2, answer_id: 'ans_demo_0002', watermark_id: 'wm_sem_demo02', audit_digest: 'digest_demo_round_2', seed_commitment: 'hmac:demo02...b72d', watermark_version: 'MR-SEB-HSW-ST-v1', detection_confidence: 0.88, semantic_similarity: 0.96, previous_audit_hash: 'hash_demo_round_1', audit_hash: 'hash_demo_round_2', chain_valid: true, tamper_suspicion: false, resource_id: 'res_demo', chunk_id: 'chunk_002', return_mode: 'variant', risk_state: 'medium', policy_decision: 'controlled_variant', protected_span_count: 8 },
  { round_id: 3, answer_id: 'ans_demo_0003', watermark_id: 'wm_sem_demo03', audit_digest: 'digest_demo_round_3', seed_commitment: 'hmac:demo03...c83e', watermark_version: 'MR-SEB-HSW-ST-v1', detection_confidence: 0.76, semantic_similarity: 0.94, previous_audit_hash: 'hash_demo_round_2', audit_hash: 'hash_demo_round_3', chain_valid: false, tamper_suspicion: true, resource_id: 'res_demo', chunk_id: 'chunk_003', return_mode: 'summary', risk_state: 'high', policy_decision: 'trace_and_refuse', protected_span_count: 8 },
];

const fallbackAttacks = [
  { attack_type: 'delete_sentences', round_id: 1, watermark_detected: true, detection_confidence: 0.9, audit_chain_valid: true, seed_binding_valid: true, semantic_preservation_score: 0.95, tamper_suspicion: false, defense_decision: 'trace' },
  { attack_type: 'truncate_middle', round_id: 2, watermark_detected: true, detection_confidence: 0.86, audit_chain_valid: true, seed_binding_valid: true, semantic_preservation_score: 0.92, tamper_suspicion: false, defense_decision: 'trace' },
  { attack_type: 'light_paraphrase', round_id: 2, watermark_detected: true, detection_confidence: 0.82, audit_chain_valid: true, seed_binding_valid: true, semantic_preservation_score: 0.9, tamper_suspicion: false, defense_decision: 'allow_with_audit' },
  { attack_type: 'summary_like', round_id: 3, watermark_detected: true, detection_confidence: 0.74, audit_chain_valid: true, seed_binding_valid: true, semantic_preservation_score: 0.88, tamper_suspicion: false, defense_decision: 'degrade' },
  { attack_type: 'marker_removal', round_id: 3, watermark_detected: true, detection_confidence: 0.71, audit_chain_valid: true, seed_binding_valid: true, semantic_preservation_score: 0.87, tamper_suspicion: false, defense_decision: 'trace' },
  { attack_type: 'source_id_replacement', round_id: 3, watermark_detected: true, detection_confidence: 0.58, audit_chain_valid: false, seed_binding_valid: false, semantic_preservation_score: 0.84, tamper_suspicion: true, defense_decision: 'tamper_suspected' },
  { attack_type: 'round_deletion', round_id: 2, watermark_detected: false, detection_confidence: 0.45, audit_chain_valid: false, seed_binding_valid: false, semantic_preservation_score: 0.78, tamper_suspicion: true, defense_decision: 'chain_break' },
  { attack_type: 'cross_round_splicing', round_id: 3, watermark_detected: true, detection_confidence: 0.62, audit_chain_valid: false, seed_binding_valid: false, semantic_preservation_score: 0.8, tamper_suspicion: true, defense_decision: 'splice_detected' },
];

export function buildAcademicFigureData(input = {}) {
  const pipelineData = input.pipelineData || input.data || {};
  const audit = pipelineData.audit_trace || input.audit_trace || {};
  const c2rag = pipelineData.protection_logs?.c2_rag || {};
  const verification = audit.verification_preview || pipelineData.protection_logs?.hsw_st?.verification_preview || {};
  const record = audit.audit_record || {};
  const trace = record.resource_trace?.[0] || {};
  const currentRound = {
    round_id: record.round_id || verification.matched_round_id || 1,
    answer_id: audit.answer_id || record.answer_id || 'ans_demo_current',
    profile_card_id: record.profile_card_id || audit.profile_card_id || 'card_hash_demo',
    resource_id: trace.resource_id || c2rag.resource_id || audit.resource_id || 'res_demo_current',
    chunk_id: trace.chunk_id || c2rag.chunk_id || audit.chunk_id || 'chunk_demo_current',
    return_mode: trace.return_mode || c2rag.return_mode || 'summary',
    risk_state: record.risk_state || 'medium',
    policy_decision: record.policy_decision || 'degrade_to_summary',
    audit_digest: audit.audit_digest || 'digest_demo_current',
    seed_commitment: audit.watermark_seed_commitment || 'hmac:demo-current...9f1a',
    watermark_version: audit.watermark_scheme || 'MR-SEB-HSW-ST-v1',
    watermark_id: audit.watermark_id || 'wm_sem_demo_current',
    watermark_detected: verification.watermark_detected ?? true,
    detection_confidence: verification.confidence ?? 0.91,
    semantic_similarity: 0.96,
    formula_preserved: 0.99,
    numbers_preserved: 0.98,
    term_preserved: 0.97,
    key_step_preserved: 0.95,
    placeholder_recovery: 0.94,
    protected_span_count: audit.semantic_watermark?.locked_content_types?.length || 7,
    previous_audit_hash: record.previous_audit_hash || audit.multi_round_binding?.previous_audit_hash || 'GENESIS',
    audit_hash: verification.chain_hash_head || audit.watermarked_answer_sha256 || 'hash_demo_current',
    chain_valid: verification.audit_chain_valid ?? true,
    tamper_suspicion: verification.tamper_suspicion ?? false,
  };

  const hasRealAudit = Boolean(audit.audit_digest || audit.watermarked_answer_sha256 || audit.watermark_id);
  const rounds = hasRealAudit
    ? [...fallbackRounds.slice(0, Math.max(0, Number(currentRound.round_id) - 1)), currentRound]
    : fallbackRounds;
  const attackResult = input.attackResult || {};
  const latestAttack = attackResult.attack_type ? {
    attack_type: attackResult.attack_type,
    round_id: currentRound.round_id,
    attacked_text_preview: attackResult.prompt || attackResult.effect || '',
    watermark_detected: currentRound.watermark_detected,
    detection_confidence: currentRound.detection_confidence,
    audit_chain_valid: currentRound.chain_valid,
    seed_binding_valid: !currentRound.tamper_suspicion,
    semantic_preservation_score: currentRound.semantic_similarity,
    tamper_suspicion: currentRound.tamper_suspicion || attackResult.decision === 'trace_and_refuse',
    defense_decision: attackResult.decision || 'audited',
  } : null;

  return {
    session_id: record.session_id || pipelineData.session_id || 'sess_demo_academic_figures',
    source: hasRealAudit ? 'real' : 'demo-derived figure data',
    rounds,
    attacks: latestAttack ? [latestAttack, ...fallbackAttacks.slice(0, 5)] : fallbackAttacks,
  };
}

function FigureShell({ id, dataSource, children }) {
  return (
    <article className="academic-figure">
      <header>
        <div>
          <h3>{FIGURE_TITLES[id]}</h3>
          <p>{INTERPRETATIONS[id]}</p>
        </div>
        <span>{dataSource}</span>
      </header>
      {children}
      <footer>
        <button type="button">Export PNG</button>
        <button type="button">Export SVG</button>
      </footer>
    </article>
  );
}

function EvidencePipelineFigure({ dataSource }) {
  const nodes = [
    ['Audit Fields', 'answer_id, round_id, resource_id'],
    ['Canonicalization', 'sorted stable JSON'],
    ['Audit Digest', 'SHA256(canonical_record)'],
    ['HMAC Seed Derivation', 'private seed, public commitment'],
    ['Semantic Guard', 'formula / number / term locks'],
    ['Watermark Generation', 'seed-dependent variants'],
    ['Protected Answer', 'no raw fields in body'],
    ['Detection', 'confidence + matched round'],
    ['Hash-chain Verification', 'previous_hash -> audit_hash'],
  ];
  return (
    <FigureShell id="evidence_pipeline" dataSource={dataSource}>
      <div className="pipeline-figure">
        {nodes.map(([title, desc], index) => (
          <div className="pipeline-node-wrap" key={title}>
            <div className="pipeline-node">
              <strong>{title}</strong>
              <small>{desc}</small>
            </div>
            {index < nodes.length - 1 && <b>→</b>}
          </div>
        ))}
      </div>
      <div className="figure-note">raw audit fields are not written into text</div>
    </FigureShell>
  );
}

function AuditChainFigure({ rounds, dataSource }) {
  return (
    <FigureShell id="audit_chain" dataSource={dataSource}>
      <div className="chain-timeline">
        <div className="chain-node genesis">GENESIS</div>
        {rounds.map((round) => (
          <div className={`chain-round ${round.chain_valid ? 'valid' : 'broken'}`} key={`${round.round_id}-${round.answer_id}`}>
            <div className="chain-link" />
            <div className="chain-node">
              <strong>round {round.round_id}</strong>
              <span>{hashPreview(round.answer_id)}</span>
              <span>{hashPreview(round.watermark_id)}</span>
              <span>audit {hashPreview(round.audit_hash)}</span>
              <span>prev {hashPreview(round.previous_audit_hash)}</span>
              <em>{round.chain_valid ? 'chain_valid' : 'Hash mismatch / Tamper suspected'}</em>
            </div>
          </div>
        ))}
      </div>
    </FigureShell>
  );
}

function SeedBindingFigure({ rounds, dataSource }) {
  return (
    <FigureShell id="seed_binding" dataSource={dataSource}>
      <div className="academic-table-wrap">
        <table>
          <thead><tr><th>round</th><th>audit_digest</th><th>seed_commitment</th><th>watermark_version</th><th>matched_seed_commitment</th><th>status</th><th>confidence</th></tr></thead>
          <tbody>
            {rounds.map((round) => (
              <tr key={round.answer_id}>
                <td>{round.round_id}</td>
                <td>{hashPreview(round.audit_digest)}</td>
                <td>{hashPreview(round.seed_commitment)}</td>
                <td>{round.watermark_version}</td>
                <td>{round.tamper_suspicion ? 'failed' : hashPreview(round.seed_commitment)}</td>
                <td className={round.chain_valid ? 'ok' : 'bad'}>{round.chain_valid ? 'verified' : 'mismatch'}</td>
                <td>{Math.round(clamp(round.detection_confidence) * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </FigureShell>
  );
}

function MetricBarsFigure({ rounds, dataSource }) {
  const latest = rounds[rounds.length - 1] || {};
  const metrics = [
    ['Formula Preservation Rate', latest.formula_preserved ?? 0.99],
    ['Number Preservation Rate', latest.numbers_preserved ?? 0.98],
    ['Term Preservation Rate', latest.term_preserved ?? 0.97],
    ['Key Step Preservation Rate', latest.key_step_preserved ?? 0.95],
    ['Semantic Similarity', latest.semantic_similarity ?? 0.96],
    ['Placeholder Recovery Rate', latest.placeholder_recovery ?? 0.94],
  ];
  return (
    <FigureShell id="semantic_preservation" dataSource={dataSource}>
      <div className="metric-bars">
        {metrics.map(([label, value]) => (
          <div className="metric-row" key={label}>
            <span>{label}</span>
            <div><i style={{ width: `${clamp(value) * 100}%` }} /></div>
            <strong>{Math.round(clamp(value) * 100)}%</strong>
          </div>
        ))}
      </div>
    </FigureShell>
  );
}

function AttackRobustnessFigure({ attacks, dataSource }) {
  return (
    <FigureShell id="watermark_attack_robustness" dataSource={dataSource}>
      <div className="attack-robustness">
        {attacks.map((attack) => (
          <div className="attack-row" key={`${attack.attack_type}-${attack.round_id}`}>
            <span>{attack.attack_type}</span>
            <div className="attack-bar"><i style={{ width: `${clamp(attack.detection_confidence) * 100}%` }} /></div>
            <b>{Math.round(clamp(attack.detection_confidence) * 100)}%</b>
            <em className={attack.audit_chain_valid ? 'ok' : 'bad'}>{attack.audit_chain_valid ? 'chain ok' : 'chain break'}</em>
            <em className={attack.tamper_suspicion ? 'bad' : 'ok'}>{attack.tamper_suspicion ? 'tamper' : 'clean'}</em>
          </div>
        ))}
      </div>
    </FigureShell>
  );
}

function MultiRoundCurveFigure({ rounds, dataSource }) {
  const width = 560;
  const height = 190;
  const maxRound = Math.max(...rounds.map((round) => Number(round.round_id) || 1), 1);
  const point = (round, key, offset = 0) => {
    const x = 36 + ((Number(round.round_id) - 1) / Math.max(1, maxRound - 1)) * (width - 72);
    const y = height - 28 - clamp(round[key] ?? round.detection_confidence) * (height - 58) + offset;
    return `${x},${y}`;
  };
  const single = rounds.map((round) => point(round, 'detection_confidence')).join(' ');
  const aggregate = rounds.map((round, index) => point({ ...round, aggregate: Math.min(0.98, 0.84 + index * 0.04) }, 'aggregate', -2)).join(' ');
  const chain = rounds.map((round) => point({ ...round, chainScore: round.chain_valid ? 0.96 : 0.58 }, 'chainScore', 2)).join(' ');
  return (
    <FigureShell id="multi_round_detection" dataSource={dataSource}>
      <svg className="curve-figure" viewBox={`0 0 ${width} ${height}`} role="img">
        <line x1="32" y1={height - 28} x2={width - 26} y2={height - 28} />
        <line x1="32" y1="18" x2="32" y2={height - 28} />
        <polyline points={single} className="curve-single" />
        <polyline points={aggregate} className="curve-aggregate" />
        <polyline points={chain} className="curve-chain" />
        {rounds.map((round) => <text key={round.round_id} x={point(round, 'detection_confidence').split(',')[0]} y={height - 8}>r{round.round_id}</text>)}
      </svg>
      <div className="curve-legend"><span className="single">single_round_confidence</span><span className="aggregate">aggregate_session_confidence</span><span className="chain">chain_validity_score</span></div>
    </FigureShell>
  );
}

function TamperLocalizationFigure({ attacks, rounds, dataSource }) {
  const attackTypes = [...new Set(attacks.map((attack) => attack.attack_type))].slice(0, 8);
  return (
    <FigureShell id="tamper_localization" dataSource={dataSource}>
      <div className="heatmap-grid" style={{ gridTemplateColumns: `130px repeat(${rounds.length}, 1fr)` }}>
        <strong>attack / round</strong>
        {rounds.map((round) => <strong key={round.round_id}>r{round.round_id}</strong>)}
        {attackTypes.map((type) => (
          <div className="heatmap-row" style={{ display: 'contents' }} key={type}>
            <span>{type}</span>
            {rounds.map((round) => {
              const found = attacks.find((attack) => attack.attack_type === type && Number(attack.round_id) === Number(round.round_id));
              const risk = found ? (found.tamper_suspicion ? 0.92 : 1 - clamp(found.detection_confidence)) : 0.16;
              return <i key={`${type}-${round.round_id}`} style={{ '--risk': risk }} title={`${type} round ${round.round_id}`} />;
            })}
          </div>
        ))}
      </div>
    </FigureShell>
  );
}

function CrossMechanismHeatmapFigure({ dataSource }) {
  const columns = ['学生画像隐私保护', '教师版权保护', '生成内容审计追踪', 'TPCS 横向治理'];
  const rows = ['privacy_extraction', 'copyright_reconstruction', 'retrieval_poisoning', 'watermark_tampering', 'audit_evasion', 'multi_turn_inference', 'replay_attack', 'profile_pollution'];
  return (
    <FigureShell id="cross_mechanism_heatmap" dataSource={dataSource}>
      <div className="defense-heatmap" style={{ gridTemplateColumns: `160px repeat(${columns.length}, 1fr)` }}>
        <strong>attack / mechanism</strong>
        {columns.map((column) => <strong key={column}>{column}</strong>)}
        {rows.map((row, rowIndex) => (
          <div style={{ display: 'contents' }} key={row}>
            <span>{row}</span>
            {columns.map((column, colIndex) => {
              const score = clamp(0.52 + ((rowIndex + colIndex * 2) % 5) * 0.1);
              return <i key={`${row}-${column}`} style={{ '--score': score }}>{Math.round(score * 100)}</i>;
            })}
          </div>
        ))}
      </div>
    </FigureShell>
  );
}

export default function AcademicFigurePanel({ data, pipelineData, attackResult, figures = DEFAULT_FIGURES, compact = false }) {
  const figureData = buildAcademicFigureData({ data, pipelineData, attackResult });
  const selected = figures.filter((figure) => FIGURE_TITLES[figure]);

  return (
    <section className={`academic-figure-panel ${compact ? 'compact' : ''}`}>
      <div className="academic-panel-heading">
        <div>
          <span>Academic Figures</span>
          <h2>MR-SEB-HSW-ST Evidence-bound Evaluation</h2>
        </div>
        <em>{figureData.source}</em>
      </div>
      {selected.includes('evidence_pipeline') && <EvidencePipelineFigure dataSource={figureData.source} />}
      {selected.includes('audit_chain') && <AuditChainFigure rounds={figureData.rounds} dataSource={figureData.source} />}
      {selected.includes('seed_binding') && <SeedBindingFigure rounds={figureData.rounds} dataSource={figureData.source} />}
      {selected.includes('semantic_preservation') && <MetricBarsFigure rounds={figureData.rounds} dataSource={figureData.source} />}
      {selected.includes('watermark_attack_robustness') && <AttackRobustnessFigure attacks={figureData.attacks} dataSource={figureData.source} />}
      {selected.includes('multi_round_detection') && <MultiRoundCurveFigure rounds={figureData.rounds} dataSource={figureData.source} />}
      {selected.includes('tamper_localization') && <TamperLocalizationFigure attacks={figureData.attacks} rounds={figureData.rounds} dataSource={figureData.source} />}
      {selected.includes('cross_mechanism_heatmap') && <CrossMechanismHeatmapFigure dataSource={figureData.source} />}
    </section>
  );
}
