import { useState } from 'react';

type Props = { apiBaseUrl: string };

export default function ForgotPassword({ apiBaseUrl }: Props) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'sent' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus('idle');
    setMessage('');
    try {
      const res = await fetch(`${apiBaseUrl}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      if (!res.ok) throw new Error('Failed to send reset email');
      setStatus('sent');
      setMessage('If an account exists, a reset link has been sent.');
    } catch (err: any) {
      setStatus('error');
      setMessage(err.message || 'Failed to send reset email');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Forgot password</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <input className="w-full border rounded px-3 py-2" placeholder="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
        {message && <div className={status === 'error' ? 'text-red-600 text-sm' : 'text-green-700 text-sm'}>{message}</div>}
        <button disabled={loading} className="w-full bg-black text-white rounded px-4 py-2">{loading ? 'Sending...' : 'Send reset link'}</button>
      </form>
      <div className="mt-3 text-sm">
        <a href="/login" onClick={(e) => { e.preventDefault(); window.history.pushState({}, '', '/login'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="text-blue-600">Back to login</a>
      </div>
    </div>
  );
}


