import { useEffect, useState } from 'react';

export default function DemoStudentLogin() {
  const [account, setAccount] = useState('student-demo');
  const [password, setPassword] = useState('');
  const [identity, setIdentity] = useState(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    fetch('/api/demo-identity/status', { credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => { if (active) setIdentity(data?.identity || null); })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const response = await fetch('/api/demo-identity/login', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account, password }),
      });
      if (!response.ok) throw new Error('登录失败，请检查演示账号、密码和本机开关。');
      setIdentity(await response.json());
      setPassword('');
      setMessage('模拟登录成功，仅用于本机合成数据。');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    try {
      const response = await fetch('/api/demo-identity/logout', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      if (!response.ok) throw new Error('退出失败。');
      setIdentity(null);
      setMessage('模拟账号已退出。');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="consent-demo demo-login" aria-label="模拟学生登录">
      <h2>模拟学生登录</h2>
      <p>仅用于本机合成数据，不能登录学校账号，也不验证真实学生身份。</p>
      <p>演示账号：<code>student-demo</code>；演示密码：<code>demo-only-2026</code>。请勿输入真实密码。</p>
      {identity ? <div className="demo-login-row">
        <strong>当前登录：{identity.display_name}</strong>
        <button type="button" onClick={signOut} disabled={busy}>退出模拟登录</button>
      </div> : <form onSubmit={submit} className="demo-login-form">
        <label>账号<input value={account} onChange={(event) => setAccount(event.target.value)} autoComplete="off" /></label>
        <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="off" /></label>
        <button type="submit" disabled={busy || !account || !password}>模拟登录</button>
      </form>}
      <p>此阶段只验证登录与会话，尚未将登录身份接到下方授权或课堂。</p>
      {message && <p role="status">{message}</p>}
    </section>
  );
}
