import { useState } from 'react';

const fieldName = { preference: '学习偏好', mastery: '掌握程度' };

export default function ProfileConsentDemo() {
  const [message, setMessage] = useState('一元一次方程怎么理解？');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  async function post(path, body) {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '请求失败');
    return data;
  }

  async function runTurn() {
    setBusy(true);
    setStatus('');
    try {
      setResult(await post('/api/consent-demo/turn', { message }));
    } catch (error) {
      setStatus(`演示未运行：${error.message}。请确认本机演示开关已开启并重启服务。`);
    } finally {
      setBusy(false);
    }
  }

  async function decide(action, requestId) {
    setBusy(true);
    setStatus('');
    try {
      await post('/api/consent-demo/decision', {
        action, ...(requestId ? { request_id: requestId } : {}),
      });
      setStatus(action === 'approve' ? '已同意。再次提问可查看变化。' :
        action === 'deny' ? '已拒绝，仍可继续提问。' : '已撤销，后续提问不再使用该字段。');
      setResult(null);
    } catch (error) {
      setStatus(`操作未完成：${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="consent-demo" aria-label="模拟画像字段授权演示">
      <h2>学习偏好授权演示</h2>
      <p>本机合成学生数据，未接入真实账号；此处的选择不是对真实学生资料的授权。</p>
      <p>系统可自动使用模拟掌握程度；教师使用模拟学习偏好需要你的确认。</p>
      <label htmlFor="consent-demo-question">学生问题</label>
      <div className="consent-demo-actions">
        <input id="consent-demo-question" value={message} maxLength={500}
          onChange={(event) => setMessage(event.target.value)} />
        <button type="button" disabled={busy || !message.trim()} onClick={runTurn}>发送问题</button>
      </div>
      {result && <div>
        <p><strong>教学回答：</strong>{result.answer}</p>
        <details><summary>本轮教学上下文</summary><pre>{result.context_card}</pre></details>
        {(result.profile_consent_requests || []).map((item) => (
          <div className="consent-demo-request" key={item.request_id}>
            <strong>教师请求使用：{fieldName[item.field] || item.field}</strong>
            <p>用途：个性化教学；不同意也可以继续提问。</p>
            <button type="button" disabled={busy} onClick={() => decide('approve', item.request_id)}>同意</button>{' '}
            <button type="button" disabled={busy} onClick={() => decide('deny', item.request_id)}>拒绝</button>
          </div>
        ))}
      </div>}
      {result && <button type="button" disabled={busy} onClick={() => decide('revoke')}>撤销学习偏好授权</button>}
      {status && <p role="status">{status}</p>}
    </section>
  );
}
