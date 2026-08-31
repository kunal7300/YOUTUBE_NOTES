import { useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider, useTheme } from './context/ThemeContext'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import NoteGenerator from './components/NoteGenerator'
import MyNotes from './components/MyNotes'
import AuthModal from './components/AuthModal'
import PublicNote from './components/PublicNote'

// ── Login / Landing page (shown when not logged in) ───────────────────────────
function LandingPage() {
  const [showAuth, setShowAuth] = useState(false)
  const [mode, setMode] = useState('login')

  const open = (m) => { setMode(m); setShowAuth(true) }

  return (
    <div style={land.page}>
      <div style={land.card}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
          <div style={{
            width: 72,
            height: 72,
            borderRadius: 20,
            background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 10px 25px -5px rgba(99, 102, 241, 0.4), 0 8px 10px -6px rgba(168, 85, 247, 0.4)',
          }}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
              <path d="M6 6h10" />
              <path d="M6 10h10" />
              <path d="M6 14h6" />
              <polygon points="18 13 18 19 22 16" fill="#ffffff" stroke="none" />
            </svg>
          </div>
        </div>
        <h1 style={land.title}>YT Lecture Notes</h1>
        <p style={land.sub}>Generate structured notes from any YouTube lecture.<br />Save them, search them, quiz yourself, and chat with them.</p>

        <div style={land.features}>
          {['Paste any YouTube URL', 'Structured notes instantly', 'Quiz and flashcards per topic', 'Saved library with full search'].map(f => (
            <div key={f} style={land.feature}>{f}</div>
          ))}
        </div>

        <div style={land.btnRow}>
          <button style={land.primary} onClick={() => open('register')}>Get Started</button>
          <button style={land.outline} onClick={() => open('login')}>Sign In</button>
        </div>
      </div>
      {showAuth && <AuthModal onClose={() => setShowAuth(false)} defaultMode={mode} />}
    </div>
  )
}

const land = {
  page: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(ellipse at 50% 0%, #1e1b4b 0%, #07070f 60%)' },
  card: { textAlign: 'center', maxWidth: 520, padding: '3rem 2rem' },
  title: { fontSize: '2.4rem', fontWeight: 800, background: 'linear-gradient(135deg, #a5b4fc, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '1rem' },
  sub: { color: '#94a3b8', lineHeight: 1.8, fontSize: '1.05rem', marginBottom: '2rem' },
  features: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '2rem', textAlign: 'left' },
  feature: { background: '#0f0f1e', border: '1px solid #1e1e3a', borderRadius: 10, padding: '0.75rem 1rem', color: '#cbd5e1', fontSize: '0.9rem' },
  btnRow: { display: 'flex', gap: '1rem', justifyContent: 'center' },
  primary: { padding: '0.8rem 2rem', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', fontWeight: 700, fontSize: '1rem', cursor: 'pointer' },
  outline: { padding: '0.8rem 2rem', borderRadius: 10, border: '1px solid #334155', background: 'transparent', color: '#94a3b8', fontWeight: 600, fontSize: '1rem', cursor: 'pointer' },
}

// ── Navbar ─────────────────────────────────────────────────────────────────────
function NavBar() {
  const { user, signOut } = useAuth()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()

  const handleSignOut = async () => { await signOut(); navigate('/') }

  return (
    <nav style={nav.bar}>
      <Link to="/" style={nav.logo}>YT Notes</Link>
      <div style={nav.right}>
        <Link to="/" style={nav.link}>Generate</Link>
        <Link to="/my-notes" style={nav.link}>My Notes</Link>
        <button style={nav.themeBtn} onClick={toggle} title="Toggle theme">
          {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
        </button>
        <span style={nav.email}>{user.email}</span>
        <button style={nav.logoutBtn} onClick={handleSignOut}>Logout</button>
      </div>
    </nav>
  )
}

const nav = {
  bar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 2rem', height: 54, background: '#0a0a14', borderBottom: '1px solid #1a1a2e', position: 'sticky', top: 0, zIndex: 100 },
  logo: { fontWeight: 800, fontSize: '1.05rem', color: '#a5b4fc', letterSpacing: 0.3 },
  right: { display: 'flex', alignItems: 'center', gap: '1.25rem' },
  link: { color: '#94a3b8', fontSize: '0.875rem', fontWeight: 500 },
  themeBtn: { background: '#1e293b', border: '1px solid #334155', color: '#cbd5e1', cursor: 'pointer', fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 6 },
  email: { color: '#64748b', fontSize: '0.8rem' },
  logoutBtn: { padding: '0.35rem 0.9rem', borderRadius: 7, border: '1px solid #1e293b', background: 'transparent', color: '#94a3b8', cursor: 'pointer', fontSize: '0.8rem' },
}

// ── App with auth gate ─────────────────────────────────────────────────────────
function AppRoutes() {
  const { user, loading } = useAuth()

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: '#64748b' }}>
      Loading...
    </div>
  )

  return (
    <Routes>
      <Route path="/shared/:shareId" element={<PublicNote />} />
      <Route path="/public/note/:shareId" element={<PublicNote />} />
      <Route path="*" element={
        !user ? <LandingPage /> : (
          <>
            <NavBar />
            <Routes>
              <Route path="/" element={<NoteGenerator />} />
              <Route path="/my-notes" element={<MyNotes />} />
              <Route path="*" element={<NoteGenerator />} />
            </Routes>
          </>
        )
      } />
    </Routes>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
