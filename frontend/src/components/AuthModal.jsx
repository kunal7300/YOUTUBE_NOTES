// src/components/AuthModal.jsx — Login / Register modal
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function AuthModal({ onClose, defaultMode = 'login' }) {
  const { signIn, signUp, signInWithGoogle } = useAuth()
  const [mode, setMode] = useState(defaultMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setSuccess(''); setLoading(true)
    try {
      if (mode === 'login') {
        await signIn(email, password)
        onClose()
      } else {
        await signUp(email, password)
        setSuccess('Account created! Check your email to confirm, then log in.')
        setMode('login')
      }
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.modal} onClick={e => e.stopPropagation()}>
        <button style={s.closeBtn} onClick={onClose}>✕</button>

        <div style={s.logoRow}>📚</div>
        <h2 style={s.title}>{mode === 'login' ? 'Welcome back' : 'Create account'}</h2>
        <p style={s.subtitle}>{mode === 'login' ? 'Sign in to your account' : 'Start generating notes for free'}</p>

        {error && <div style={s.error}>{error}</div>}
        {success && <div style={s.success}>{success}</div>}

        <button style={s.googleBtn} onClick={signInWithGoogle} disabled={loading}>
          <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width={18} />
          Continue with Google
        </button>

        <div style={s.divider}><span>or continue with email</span></div>

        <form onSubmit={handleSubmit} style={s.form}>
          <div style={s.field}>
            <label style={s.label}>Email</label>
            <input style={s.input} type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div style={s.field}>
            <label style={s.label}>Password</label>
            <input style={s.input} type="password" placeholder="Min. 6 characters" value={password} onChange={e => setPassword(e.target.value)} required minLength={6} />
          </div>
          <button style={{ ...s.primaryBtn, opacity: loading ? 0.7 : 1 }} type="submit" disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <p style={s.switchText}>
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <span style={s.switchLink} onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
            {mode === 'login' ? 'Sign up' : 'Sign in'}
          </span>
        </p>
      </div>
    </div>
  )
}

const s = {
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' },
  modal: { background: '#0d0d1a', border: '1px solid #1e1e3a', borderRadius: 16, padding: '2.5rem', width: 400, position: 'relative', color: '#e2e8f0' },
  closeBtn: { position: 'absolute', top: 14, right: 16, background: 'none', border: 'none', color: '#475569', fontSize: 16, cursor: 'pointer' },
  logoRow: { fontSize: '2rem', textAlign: 'center', marginBottom: '0.5rem' },
  title: { textAlign: 'center', fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.3rem', color: '#f1f5f9' },
  subtitle: { textAlign: 'center', color: '#64748b', fontSize: '0.875rem', marginBottom: '1.5rem' },
  googleBtn: { width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', padding: '0.7rem', borderRadius: 10, border: '1px solid #1e293b', background: '#111827', color: '#e2e8f0', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500, marginBottom: '1.25rem' },
  divider: { textAlign: 'center', color: '#334155', fontSize: '0.8rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem', '&::before,&::after': { content: '""', flex: 1, borderTop: '1px solid #1e293b' } },
  form: { display: 'flex', flexDirection: 'column', gap: '1rem' },
  field: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
  label: { fontSize: '0.8rem', fontWeight: 500, color: '#94a3b8' },
  input: { padding: '0.65rem 0.9rem', borderRadius: 9, border: '1px solid #1e293b', background: '#111827', color: '#f1f5f9', fontSize: '0.9rem', outline: 'none', transition: 'border 0.15s' },
  primaryBtn: { padding: '0.75rem', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', fontSize: '0.95rem', cursor: 'pointer', fontWeight: 600, marginTop: '0.25rem' },
  switchText: { textAlign: 'center', marginTop: '1.25rem', color: '#475569', fontSize: '0.875rem' },
  switchLink: { color: '#818cf8', cursor: 'pointer', fontWeight: 600 },
  error: { background: '#1a0a0a', border: '1px solid #7f1d1d', borderRadius: 8, padding: '0.6rem 0.9rem', color: '#fca5a5', fontSize: '0.85rem', marginBottom: '0.75rem' },
  success: { background: '#0a1a0e', border: '1px solid #166534', borderRadius: 8, padding: '0.6rem 0.9rem', color: '#86efac', fontSize: '0.85rem', marginBottom: '0.75rem' },
}
