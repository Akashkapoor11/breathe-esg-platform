import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Leaf, AlertCircle, Loader2 } from 'lucide-react'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.data?.detail || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: 'rgba(63,185,80,0.15)' }}>
            <Leaf size={22} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <div className="text-xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              Breathe ESG
            </div>
            <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Emissions Ingestion Platform
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-base font-semibold mb-5">Sign in to your account</h2>

          {error && (
            <div className="flex items-center gap-2 text-sm px-3 py-2 rounded-md mb-4"
              style={{ background: 'rgba(248,81,73,0.1)', color: 'var(--danger)' }}>
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Username
              </label>
              <input
                className="input"
                type="text"
                autoComplete="username"
                placeholder="admin"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Password
              </label>
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                required
              />
            </div>
            <button type="submit" disabled={loading}
              className="btn-primary w-full justify-center py-2.5 mt-1">
              {loading ? <Loader2 size={14} className="animate-spin" /> : null}
              Sign in
            </button>
          </form>
        </div>

        <div className="mt-4 text-xs text-center" style={{ color: 'var(--text-muted)' }}>
          Demo credentials:&nbsp;
          <code className="mono">admin / admin123</code>&nbsp; or &nbsp;
          <code className="mono">analyst / analyst123</code>
        </div>
      </div>
    </div>
  )
}
