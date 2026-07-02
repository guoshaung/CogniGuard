import { useMemo, useState } from 'react';
import { CheckCircle2, Copy, ImageUp, SearchCheck, ShieldAlert, WandSparkles } from 'lucide-react';
import './WatermarkDetectorPanel.css';

const attackOptions = [
  { id: 'inpainting', label: '局部重绘', description: '模拟 AIGC 对局部内容重新生成' },
  { id: 'object_removal', label: '目标移除', description: '模拟删除画面中的一块对象' },
  { id: 'local_replacement', label: '局部替换', description: '模拟替换为新的 AIGC 元素' },
  { id: 'local_style_edit', label: '风格改写', description: '模拟局部色彩与质感变化' },
];

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

const copyImageSource = async (source) => {
  const resolved = source.startsWith('data:') ? source : new URL(source, window.location.origin).href;
  const response = await fetch(resolved);
  const blob = await response.blob();
  if (navigator.clipboard?.write && window.ClipboardItem) {
    await navigator.clipboard.write([
      new ClipboardItem({ [blob.type || 'image/png']: blob }),
    ]);
    return 'image';
  }
  await navigator.clipboard.writeText(resolved);
  return 'url';
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
  const [imageData, setImageData] = useState('');
  const [imageName, setImageName] = useState('');
  const [imageId, setImageId] = useState('');
  const [imageResourceId, setImageResourceId] = useState('');
  const [imageBusy, setImageBusy] = useState(false);
  const [imageResult, setImageResult] = useState(null);
  const [imageError, setImageError] = useState('');
  const [attackImageData, setAttackImageData] = useState('');
  const [attackImageName, setAttackImageName] = useState('');
  const [attackType, setAttackType] = useState('inpainting');
  const [attackPrompt, setAttackPrompt] = useState('');
  const [attackBusy, setAttackBusy] = useState(false);
  const [attackResult, setAttackResult] = useState(null);
  const [attackError, setAttackError] = useState('');
  const [copyMessage, setCopyMessage] = useState('');

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

  const loadImage = (file) => {
    if (!file) return;
    setImageName(file.name);
    setImageResult(null);
    setImageError('');
    const reader = new FileReader();
    reader.onload = () => setImageData(String(reader.result || ''));
    reader.onerror = () => setImageError('图片读取失败，请换一张图片重试。');
    reader.readAsDataURL(file);
  };

  const loadAttackImage = (file) => {
    if (!file) return;
    setAttackImageName(file.name);
    setAttackResult(null);
    setAttackError('');
    const reader = new FileReader();
    reader.onload = () => setAttackImageData(String(reader.result || ''));
    reader.onerror = () => setAttackError('图片读取失败，请换一张图片重试。');
    reader.readAsDataURL(file);
  };

  const loadPastedImage = (event, target) => {
    const items = Array.from(event.clipboardData?.items || []);
    const imageItem = items.find((item) => item.type.startsWith('image/'));
    if (!imageItem) return;
    event.preventDefault();
    const file = imageItem.getAsFile();
    if (target === 'attack') {
      loadAttackImage(file);
    } else {
      loadImage(file);
    }
  };

  const runImageAttack = async () => {
    if (!attackImageData) {
      setAttackError('请先粘贴或上传一张图片。');
      return;
    }
    setAttackBusy(true);
    setAttackError('');
    setCopyMessage('');
    try {
      const response = await fetch('/api/watermark/image-attack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: attackImageData,
          attack_type: attackType,
          prompt: attackPrompt || undefined,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setAttackResult(payload);
    } catch (caughtError) {
      setAttackError(caughtError.message);
    } finally {
      setAttackBusy(false);
    }
  };

  const copyImage = async (source, label) => {
    setCopyMessage('');
    try {
      const copied = await copyImageSource(source);
      setCopyMessage(copied === 'image' ? `已复制${label}` : `已复制${label}链接`);
    } catch (caughtError) {
      setCopyMessage(`复制失败：${caughtError.message}`);
    }
  };

  const useAttackedForDetection = () => {
    if (!attackResult?.attacked_image_data) return;
    setImageData(attackResult.attacked_image_data);
    setImageName(`attacked-${attackType}.png`);
    setImageResult(null);
    setImageError('');
  };

  const runImageDetection = async () => {
    if (!imageData) {
      setImageError('请先上传一张图片。');
      return;
    }
    setImageBusy(true);
    setImageError('');
    try {
      const response = await fetch('/api/watermark/image-detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: imageData,
          image_id: imageId || undefined,
          resource_id: imageResourceId || undefined,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setImageResult(payload);
    } catch (caughtError) {
      setImageError(caughtError.message);
    } finally {
      setImageBusy(false);
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

      <div className="image-attack-card">
        <div className="image-detector-title">
          <div>
            <span>AIGC Image Attack</span>
            <h3>AIGC 图片修改</h3>
            <p>粘贴或上传一张已加水印图片，选择攻击方式后生成受攻击图片；右侧可复制或送入下方检测。</p>
          </div>
          <WandSparkles size={28} />
        </div>
        <div className="image-attack-grid">
          <label className="image-upload-box attack-upload-box" onPaste={(event) => loadPastedImage(event, 'attack')}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => loadAttackImage(event.target.files?.[0])}
            />
            {attackImageData ? (
              <img src={attackImageData} alt={attackImageName || 'source for AIGC attack'} />
            ) : (
              <span>粘贴图片或点击上传</span>
            )}
          </label>
          <aside className="image-attack-controls">
            <label>
              <span>攻击方式</span>
              <select value={attackType} onChange={(event) => setAttackType(event.target.value)}>
                {attackOptions.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>
            <p>{attackOptions.find((option) => option.id === attackType)?.description}</p>
            <label>
              <span>编辑提示词 optional</span>
              <input value={attackPrompt} onChange={(event) => setAttackPrompt(event.target.value)} placeholder="例如：替换图中高亮区域" />
            </label>
            <button type="button" onClick={runImageAttack} disabled={attackBusy || !attackImageData}>
              {attackBusy ? '生成攻击图中...' : '执行 AIGC 攻击'}
            </button>
          </aside>
          <div className="attacked-preview-panel">
            {attackResult?.attacked_image_data ? (
              <>
                <img src={attackResult.attacked_image_data} alt="AIGC attacked result" />
                <div className="attacked-preview-actions">
                  <button type="button" onClick={() => copyImage(attackResult.attacked_image_data, '受攻击图片')}>
                    <Copy size={14} /> 复制图片
                  </button>
                  <button type="button" onClick={useAttackedForDetection}>
                    用这张图检测
                  </button>
                </div>
                <small>{attackResult.message}</small>
              </>
            ) : (
              <span>受攻击图片会显示在这里</span>
            )}
          </div>
        </div>
        {attackError && <div className="watermark-detector-error"><ShieldAlert size={15} /> {attackError}</div>}
        {copyMessage && <div className="watermark-copy-message">{copyMessage}</div>}
      </div>

      <div className="image-detector-card">
        <div className="image-detector-title">
          <div>
            <span>Image Resource Detection</span>
            <h3>教学图片水印检测</h3>
            <p>上传图片后检测是否属于本系统生成资源；即使可见 logo 被删除，也会继续扫描隐式频域水印。</p>
          </div>
          <ImageUp size={28} />
        </div>
        <div className="image-detector-grid">
          <label className="image-upload-box" onPaste={(event) => loadPastedImage(event, 'detect')}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => loadImage(event.target.files?.[0])}
            />
            {imageData ? (
              <img src={imageData} alt={imageName || 'uploaded teaching resource'} />
            ) : (
              <span>选择图片 / Drop-in upload</span>
            )}
          </label>
          <aside>
            <details className="image-advanced-fields">
              <summary>高级：手动指定 ID</summary>
              <label>
                <span>image_id optional</span>
                <input value={imageId} onChange={(event) => setImageId(event.target.value)} placeholder="cg_img_..." />
              </label>
              <label>
                <span>resource_id optional</span>
                <input value={imageResourceId} onChange={(event) => setImageResourceId(event.target.value)} placeholder="teacher_resource_..." />
              </label>
            </details>
            <button type="button" onClick={runImageDetection} disabled={imageBusy || !imageData}>
              {imageBusy ? '检测图片中...' : '检测图片水印 / Verify Image'}
            </button>
          </aside>
        </div>
        {imageError && <div className="watermark-detector-error"><ShieldAlert size={15} /> {imageError}</div>}
        {imageResult && (
          <div className={`watermark-detection-result ${imageResult.tamper_suspicion ? 'warn' : 'ok'}`}>
            <div className="result-headline">
              {imageResult.watermark_detected ? <CheckCircle2 size={20} /> : <ShieldAlert size={20} />}
              <strong>{imageResult.system_resource ? 'System image resource detected' : 'System image not confirmed'}</strong>
              <span>{Math.round((imageResult.detection_confidence || 0) * 100)}%</span>
            </div>
            <div className="result-metrics">
              <div><span>hidden_watermark</span><strong>{String(imageResult.hidden_watermark_detected)}</strong></div>
              <div><span>visible_logo</span><strong>{String(imageResult.visible_logo_detected)}</strong></div>
              <div><span>tamper_suspicion</span><strong>{String(imageResult.tamper_suspicion)}</strong></div>
              <div><span>auth_status</span><strong>{shortValue(imageResult.auth_status)}</strong></div>
              <div><span>attack_regime</span><strong>{shortValue(imageResult.attack_regime)}</strong></div>
              <div><span>detection_method</span><strong>{imageResult.detection_method}</strong></div>
            </div>
            <div className="tamper-localization-panel">
              <div>
                <strong>篡改定位</strong>
                <span>
                  {imageResult.overlay_url || imageResult.predicted_mask_url
                    ? '已返回疑似修改区域'
                    : '当前结果未返回可视化区域'}
                </span>
              </div>
              <div className="tamper-localization-images">
                {imageResult.overlay_url && (
                  <figure>
                    <img src={imageResult.overlay_url} alt="tamper localization overlay" />
                    <figcaption>修改区域叠加图</figcaption>
                  </figure>
                )}
                {imageResult.predicted_mask_url && (
                  <figure>
                    <img src={imageResult.predicted_mask_url} alt="predicted tamper mask" />
                    <figcaption>预测 mask</figcaption>
                  </figure>
                )}
              </div>
              {imageResult.reports?.length > 0 && (
                <div className="tamper-region-list">
                  {imageResult.reports.slice(0, 6).map((region) => (
                    <div key={region.region_id ?? JSON.stringify(region.bbox)}>
                      <span>区域 {region.region_id ?? '-'}</span>
                      <strong>{region.change_type || 'unknown'} / {region.severity || 'unknown'}</strong>
                      <em>bbox [{(region.bbox || []).join(', ')}]</em>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <details className="image-result-advanced">
              <summary>高级检测字段</summary>
              <div className="result-metrics">
                <div><span>matched_image_id</span><strong>{shortValue(imageResult.matched_image_id)}</strong></div>
                <div><span>matched_resource_id</span><strong>{shortValue(imageResult.matched_resource_id)}</strong></div>
                <div><span>bit_accuracy</span><strong>{shortValue(imageResult.bit_accuracy)}</strong></div>
                <div><span>report_json_path</span><strong>{shortValue(imageResult.report_json_path)}</strong></div>
              </div>
            </details>
            <p>{imageResult.explanation}</p>
          </div>
        )}
      </div>
    </section>
  );
}
