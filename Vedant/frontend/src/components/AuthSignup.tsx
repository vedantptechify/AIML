import { useState } from 'react';

type Props = { apiBaseUrl: string };

export default function AuthSignup({ apiBaseUrl }: Props) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password })
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d?.detail || 'Signup failed');
      }
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));
      window.history.pushState({}, '', '/');
      window.dispatchEvent(new PopStateEvent('popstate'));
    } catch (err: any) {
      setError(err.message || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Create account</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <input className="w-full border rounded px-3 py-2" placeholder="First name" value={firstName} onChange={e => setFirstName(e.target.value)} required />
        <input className="w-full border rounded px-3 py-2" placeholder="Last name" value={lastName} onChange={e => setLastName(e.target.value)} required />
        <input className="w-full border rounded px-3 py-2" placeholder="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
        <input className="w-full border rounded px-3 py-2" placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <div className="text-red-600 text-sm">{error}</div>}
        <button disabled={loading} className="w-full bg-black text-white rounded px-4 py-2">{loading ? 'Creating...' : 'Sign up'}</button>
      </form>
      <div className="mt-3 text-sm">
        Already have an account?{' '}
        <a href="/login" onClick={(e) => { e.preventDefault(); window.history.pushState({}, '', '/login'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="text-blue-600">Log in</a>
      </div>
    </div>
  );
}


