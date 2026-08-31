// PublicNote.jsx — View publicly shared note without requiring login
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { API_BASE } from '../config'
const API = API_BASE

export default function PublicNote() {
  const { shareId } = useParams()
  const [note, setNote] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchShared = async () => {
      try {
        const res = await fetch(`${API}/shared/${shareId}`)
        if (!res.ok) throw new Error('Shared note not found or link has expired.')
        const data = await res.json()
        setNote(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchShared()
  }, [shareId])

  if (loading) return <div style={s.center}>Loading shared note...</div>
  if (error || !note) return (
    <div style={s.center}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ color: '#ef4444', marginBottom: '1rem', fontSize: '1.1rem' }}>{error || 'Note not found'}</div>
        <Link to="/" style={s.homeLink}>Go to Home &rarr;</Link>
      </div>
    </div>
  )

  const fmtDate = (iso) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <div style={s.page}>
      <header style={s.header}>
        <div style={s.headerContent}>
          <Link to="/" style={s.logo}>YT Notes</Link>
          <Link to="/" style={s.ctaBtn}>Create Your Own Notes</Link>
        </div>
      </header>

      <main style={s.container}>
        <div style={s.meta}>
          <h1 style={s.title}>{note.title}</h1>
          <div style={s.subRow}>
            <span>Created on {fmtDate(note.created_at)}</span>
            {note.youtube_url && (
              <a href={note.youtube_url} target="_blank" rel="noreferrer" style={s.ytLink}>
                Watch Video &rarr;
              </a>
            )}
          </div>
          {note.tags?.length > 0 && (
            <div style={s.tagRow}>
              {note.tags.map(t => <span key={t} style={s.tag}>{t}</span>)}
            </div>
          )}
        </div>

        <div className="notes-md" style={s.content}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.content}</ReactMarkdown>
        </div>
      </main>
    </div>
  )
}

const s = {
  page: { minHeight: '100vh', background: '#07070f', color: '#e2e8f0' },
  center: { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', color: '#64748b' },
  homeLink: { color: '#6366f1', textDecoration: 'underline' },
  header: { height: 60, borderBottom: '1px solid #1e293b', background: '#09090f', display: 'flex', alignItems: 'center' },
  headerContent: { width: '100%', maxWidth: 900, margin: '0 auto', padding: '0 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  logo: { fontWeight: 700, color: '#a5b4fc', fontSize: '1.1rem' },
  ctaBtn: { padding: '0.45rem 1rem', background: '#4f46e5', color: '#fff', borderRadius: 6, fontSize: '0.85rem', fontWeight: 500 },
  container: { maxWidth: 900, margin: '0 auto', padding: '2.5rem 1.5rem' },
  meta: { marginBottom: '2rem', paddingBottom: '1.5rem', borderBottom: '1px solid #1e293b' },
  title: { fontSize: '1.8rem', fontWeight: 700, color: '#f1f5f9', marginBottom: '0.75rem' },
  subRow: { display: 'flex', gap: '1.5rem', color: '#64748b', fontSize: '0.85rem' },
  ytLink: { color: '#6366f1', fontWeight: 500 },
  tagRow: { display: 'flex', gap: '0.4rem', marginTop: '0.75rem' },
  tag: { background: '#1e1b4b', color: '#a5b4fc', fontSize: '0.75rem', padding: '0.2rem 0.6rem', borderRadius: 999 },
  content: { lineHeight: 1.8, fontSize: '0.95rem' },
}
