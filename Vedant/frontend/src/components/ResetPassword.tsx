import { useEffect, useState } from 'react';

type Props = { apiBaseUrl: string };

export default function ResetPassword({ apiBaseUrl }: Props) {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('token') || '';
    setToken(t);
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setStatus('error');
      setMessage('Passwords do not match');
      return;
    }
    setLoading(true);
    setStatus('idle');
    setMessage('');
    try {
      const res = await fetch(`${apiBaseUrl}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password })
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d?.detail || 'Failed to reset password');
      }
      setStatus('ok');
      setMessage('Password reset successful. You can now log in.');
      setTimeout(() => {
        window.history.pushState({}, '', '/login');
        window.dispatchEvent(new PopStateEvent('popstate'));
      }, 800);
    } catch (err: any) {
      setStatus('error');
      setMessage(err.message || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Reset password</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <input className="w-full border rounded px-3 py-2" placeholder="New password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        <input className="w-full border rounded px-3 py-2" placeholder="Confirm password" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required />
        {message && <div className={status === 'error' ? 'text-red-600 text-sm' : 'text-green-700 text-sm'}>{message}</div>}
        <button disabled={loading} className="w-full bg-black text-white rounded px-4 py-2">{loading ? 'Saving...' : 'Reset password'}</button>
      </form>
    </div>
  );
}


