// MyNotes.jsx — Full-featured notes library with clean typography (no emojis)
import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import ChatPanel from './ChatPanel'
import QuizPanel from './QuizPanel'
import FlashcardPanel from './FlashcardPanel'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { API_BASE } from '../config'
const API = API_BASE

const mdStyle = document.createElement('style')
mdStyle.textContent = `
  .notes-md h1,.notes-md h2{color:#f1f5f9;border-bottom:1px solid #1e293b;padding-bottom:.3em;margin:1.4em 0 .6em}
  .notes-md h3{color:#e2e8f0;margin:1em 0 .4em}.notes-md h4{color:#cbd5e1;margin:.8em 0 .3em}
  .notes-md p{margin:.5em 0;color:#94a3b8;line-height:1.8}
  .notes-md ul,.notes-md ol{padding-left:1.6em;margin:.4em 0}
  .notes-md li{margin:.3em 0;color:#94a3b8}
  .notes-md strong{color:#e2e8f0}
  .notes-md blockquote{border-left:3px solid #4f46e5;padding-left:1em;color:#64748b;margin:.75em 0}
  .notes-md code{background:#0f172a;padding:.15em .4em;border-radius:4px;font-size:.85em;color:#a5b4fc}
  .notes-md pre{background:#0f172a;padding:1em;border-radius:8px;overflow-x:auto;margin:.75em 0;border:1px solid #1e293b}
  .notes-md pre code{background:transparent;padding:0;color:#94a3b8}
  .notes-md hr{border:none;border-top:1px solid #1e293b;margin:1.5em 0}
  .notes-md table{border-collapse:collapse;width:100%;margin:.75em 0}
  .notes-md th,.notes-md td{border:1px solid #1e293b;padding:.4em .75em;color:#94a3b8;font-size:.85em}
  .notes-md th{background:#0f172a;color:#e2e8f0}
`
document.head.appendChild(mdStyle)

const TABS = [
  { id: 'notes', label: 'Notes' },
  { id: 'summary', label: 'Summary' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'flashcards', label: 'Flashcards' },
  { id: 'chat', label: 'Chat' },
]

export default function MyNotes() {
  const { user, getToken, loading } = useAuth()
  const navigate = useNavigate()
  const [notes, setNotes] = useState([])
  const [searchQ, setSearchQ] = useState('')
  const [fetching, setFetching] = useState(true)
  const [selectedNote, setSelectedNote] = useState(null)
  const [activeTab, setActiveTab] = useState('notes')
  const [deleting, setDeleting] = useState(null)
  const [summary, setSummary] = useState('')
  const [loadingSummary, setLoadingSummary] = useState(false)
  const [shareUrl, setShareUrl] = useState('')
  const [sharing, setSharing] = useState(false)
  const [editingTags, setEditingTags] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const tagRef = useRef(null)

  useEffect(() => { if (!loading && !user) navigate('/') }, [user, loading])

  useEffect(() => {
    if (!user) return
    fetchNotes()
  }, [user])

  const fetchNotes = async () => {
    try {
      const res = await fetch(`${API}/my-notes`, { headers: { Authorization: `Bearer ${getToken()}` } })
      const data = await res.json()
      setNotes(data.notes || [])
    } catch { }
    finally { setFetching(false) }
  }

  const searchNotes = async (q) => {
    if (!q.trim()) { fetchNotes(); return }
    try {
      const res = await fetch(`${API}/search-notes?q=${encodeURIComponent(q)}`, {
        headers: { Authorization: `Bearer ${getToken()}` }
      })
      const data = await res.json()
      setNotes(data.results || [])
    } catch { }
  }

  const openNote = async (noteId) => {
    try {
      const res = await fetch(`${API}/my-notes/${noteId}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      const note = await res.json()
      setSelectedNote(note)
      setActiveTab('notes')
      setSummary('')
      setShareUrl('')
    } catch { }
  }

  const deleteNote = async (noteId, e) => {
    e.stopPropagation()
    if (!window.confirm('Delete this note permanently?')) return
    setDeleting(noteId)
    try {
      await fetch(`${API}/my-notes/${noteId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${getToken()}` } })
      setNotes(p => p.filter(n => n.id !== noteId))
      if (selectedNote?.id === noteId) setSelectedNote(null)
    } catch { alert('Failed to delete') }
    finally { setDeleting(null) }
  }

  const loadSummary = async () => {
    if (summary) return
    setLoadingSummary(true)
    try {
      const res = await fetch(`${API}/summary/${selectedNote.id}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      const d = await res.json()
      setSummary(d.summary || '')
    } catch { setSummary('Failed to generate summary.') }
    finally { setLoadingSummary(false) }
  }

  const shareNote = async () => {
    setSharing(true)
    try {
      const res = await fetch(`${API}/share/${selectedNote.id}`, {
        method: 'POST', headers: { Authorization: `Bearer ${getToken()}` }
      })
      const d = await res.json()
      const url = `${window.location.origin}/shared/${d.share_id}`
      setShareUrl(url)
      await navigator.clipboard.writeText(url)
    } catch { alert('Failed to share') }
    finally { setSharing(false) }
  }

  const saveTag = async () => {
    const tag = tagInput.trim()
    if (!tag) return
    const newTags = [...(selectedNote.tags || []), tag]
    try {
      await fetch(`${API}/tags/${selectedNote.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ tags: newTags }),
      })
      setSelectedNote(p => ({ ...p, tags: newTags }))
      setNotes(ns => ns.map(n => n.id === selectedNote.id ? { ...n, tags: newTags } : n))
      setTagInput('')
    } catch { }
  }

  const removeTag = async (tag) => {
    const newTags = (selectedNote.tags || []).filter(t => t !== tag)
    try {
      await fetch(`${API}/tags/${selectedNote.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ tags: newTags }),
      })
      setSelectedNote(p => ({ ...p, tags: newTags }))
      setNotes(ns => ns.map(n => n.id === selectedNote.id ? { ...n, tags: newTags } : n))
    } catch { }
  }

  const fmtDate = (iso) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  const langLabel = { english: 'EN', hindi: 'HI', hinglish: 'Hinglish' }

  if (loading || fetching) return <div style={s.splash}>Loading...</div>
  if (!user) return null

  return (
    <div style={s.layout}>
      {/* ── Sidebar ── */}
      <aside style={s.sidebar}>
        <div style={s.sidebarHead}>
          <span style={s.sidebarTitle}>My Notes</span>
          <span style={s.noteCount}>{notes.length}</span>
        </div>

        {/* Search */}
        <div style={s.searchWrap}>
          <input
            style={s.searchInput}
            placeholder="Search notes..."
            value={searchQ}
            onChange={e => { setSearchQ(e.target.value); searchNotes(e.target.value) }}
          />
        </div>

        <div style={s.noteList}>
          {notes.length === 0 ? (
            <div style={s.emptyList}>
              <div style={{ marginBottom: '.5rem', color: '#64748b' }}>{searchQ ? 'No results found' : 'No saved notes yet'}</div>
              {!searchQ && <span style={s.goLink} onClick={() => navigate('/')}>Generate notes &rarr;</span>}
            </div>
          ) : notes.map(note => (
            <div
              key={note.id}
              style={{ ...s.noteItem, ...(selectedNote?.id === note.id ? s.noteItemActive : {}) }}
              onClick={() => openNote(note.id)}
            >
              <div style={s.noteItemRow}>
                {note.language && <span style={s.langBadge}>{langLabel[note.language] || note.language}</span>}
                <div style={s.noteItemTitle}>{note.title || 'Untitled'}</div>
                <button style={s.delBtn} onClick={e => deleteNote(note.id, e)} disabled={deleting === note.id} title="Delete">
                  {deleting === note.id ? '...' : '\u00d7'}
                </button>
              </div>
              <div style={s.noteItemDate}>{fmtDate(note.created_at)}</div>
              {note.tags?.length > 0 && (
                <div style={s.tagRow}>
                  {note.tags.slice(0, 3).map(t => <span key={t} style={s.tagChip}>{t}</span>)}
                </div>
              )}
            </div>
          ))}
        </div>
      </aside>

      {/* ── Main ── */}
      <main style={s.main}>
        {!selectedNote ? (
          <div style={s.selectPrompt}>
            <div style={{ color: '#64748b', fontSize: '1rem' }}>Select a note from the sidebar</div>
          </div>
        ) : (
          <div style={s.noteView}>
            {/* Header */}
            <div style={s.noteHeader}>
              <div style={s.noteMeta}>
                <h1 style={s.noteTitle}>{selectedNote.title}</h1>
                <div style={s.noteSubRow}>
                  <span style={s.noteDate}>{fmtDate(selectedNote.created_at)}</span>
                  <a href={selectedNote.youtube_url} target="_blank" rel="noreferrer" style={s.ytLink}>Watch on YouTube &rarr;</a>
                  {/* Tags */}
                  <div style={s.tagArea}>
                    {(selectedNote.tags || []).map(t => (
                      <span key={t} style={s.tagPill}>
                        {t}
                        <span style={s.tagX} onClick={() => removeTag(t)}>&times;</span>
                      </span>
                    ))}
                    {editingTags ? (
                      <input
                        ref={tagRef}
                        style={s.tagInp}
                        value={tagInput}
                        placeholder="Add tag..."
                        onChange={e => setTagInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') saveTag(); if (e.key === 'Escape') setEditingTags(false) }}
                        onBlur={() => { saveTag(); setEditingTags(false) }}
                        autoFocus
                      />
                    ) : (
                      <button style={s.addTagBtn} onClick={() => setEditingTags(true)}>+ Tag</button>
                    )}
                  </div>
                  {/* Share */}
                  <button style={s.shareBtn} onClick={shareNote} disabled={sharing}>
                    {sharing ? 'Sharing...' : shareUrl ? 'Link Copied' : 'Share'}
                  </button>
                </div>
              </div>
              {/* Tabs */}
              <div style={s.tabRow}>
                {TABS.map(tab => (
                  <button
                    key={tab.id}
                    style={{ ...s.tab, ...(activeTab === tab.id ? s.tabActive : {}) }}
                    onClick={() => { setActiveTab(tab.id); if (tab.id === 'summary') loadSummary() }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Content */}
            <div style={s.contentArea}>
              {activeTab === 'notes' && (
                <div className="notes-md" style={s.scrollPad}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedNote.content}</ReactMarkdown>
                </div>
              )}
              {activeTab === 'summary' && (
                <div style={s.scrollPad}>
                  {loadingSummary ? (
                    <div style={s.loadingMsg}>Generating summary...</div>
                  ) : summary ? (
                    <div className="notes-md">
                      <h2 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>SUMMARY</h2>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
                    </div>
                  ) : (
                    <button style={s.genBtn} onClick={loadSummary}>Generate Summary</button>
                  )}
                </div>
              )}
              {activeTab === 'quiz' && <QuizPanel noteId={selectedNote.id} />}
              {activeTab === 'flashcards' && <FlashcardPanel noteId={selectedNote.id} />}
              {activeTab === 'chat' && (
                <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                  <ChatPanel noteId={selectedNote.id} noteTitle={selectedNote.title} />
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

const s = {
  layout: { display: 'flex', height: 'calc(100vh - 54px)', overflow: 'hidden', background: '#07070f' },
  sidebar: { width: 265, background: '#09090f', borderRight: '1px solid #0f172a', display: 'flex', flexDirection: 'column', flexShrink: 0 },
  sidebarHead: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.9rem 1.25rem', borderBottom: '1px solid #0f172a' },
  sidebarTitle: { fontWeight: 700, color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em' },
  noteCount: { background: '#1e293b', color: '#64748b', fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: 999 },
  searchWrap: { padding: '0.75rem 1rem', borderBottom: '1px solid #0f172a' },
  searchInput: { width: '100%', padding: '0.5rem 0.75rem', borderRadius: 8, border: '1px solid #1e293b', background: '#0f172a', color: '#e2e8f0', fontSize: '0.85rem', outline: 'none' },
  noteList: { flex: 1, overflowY: 'auto' },
  emptyList: { padding: '2.5rem 1.25rem', textAlign: 'center', fontSize: '0.875rem' },
  goLink: { color: '#6366f1', cursor: 'pointer', fontSize: '0.85rem' },
  noteItem: { padding: '0.75rem 1.25rem', borderBottom: '1px solid #0a0a14', cursor: 'pointer' },
  noteItemActive: { background: '#0f172a', borderLeft: '2px solid #6366f1' },
  noteItemRow: { display: 'flex', alignItems: 'center', gap: '0.5rem' },
  langBadge: { fontSize: '0.7rem', color: '#a5b4fc', background: '#1e1b4b', padding: '0.1rem 0.4rem', borderRadius: 4, flexShrink: 0 },
  noteItemTitle: { flex: 1, color: '#cbd5e1', fontSize: '0.85rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  delBtn: { background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '1rem', padding: '0 0.25rem', flexShrink: 0, lineHeight: 1 },
  noteItemDate: { color: '#475569', fontSize: '0.72rem', marginTop: 2 },
  tagRow: { display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginTop: '0.4rem' },
  tagChip: { background: '#1e293b', color: '#64748b', fontSize: '0.68rem', padding: '0.15rem 0.45rem', borderRadius: 999 },
  main: { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' },
  selectPrompt: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' },
  noteView: { display: 'flex', flexDirection: 'column', height: '100%' },
  noteHeader: { padding: '1.25rem 2rem 0', borderBottom: '1px solid #0f172a', background: '#09090f', flexShrink: 0 },
  noteMeta: { marginBottom: '1rem' },
  noteTitle: { color: '#f1f5f9', fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' },
  noteSubRow: { display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' },
  noteDate: { color: '#64748b', fontSize: '0.78rem' },
  ytLink: { color: '#6366f1', fontSize: '0.78rem', fontWeight: 500 },
  tagArea: { display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' },
  tagPill: { background: '#1e1b4b', color: '#a5b4fc', fontSize: '0.73rem', padding: '0.2rem 0.6rem', borderRadius: 999, display: 'flex', alignItems: 'center', gap: '0.3rem' },
  tagX: { cursor: 'pointer', color: '#6366f1', fontWeight: 700, fontSize: '0.9em' },
  tagInp: { padding: '0.25rem 0.6rem', borderRadius: 999, border: '1px solid #4f46e5', background: '#0f172a', color: '#e2e8f0', fontSize: '0.78rem', outline: 'none', width: 80 },
  addTagBtn: { padding: '0.2rem 0.6rem', borderRadius: 999, border: '1px dashed #334155', background: 'transparent', color: '#475569', cursor: 'pointer', fontSize: '0.73rem' },
  shareBtn: { marginLeft: 'auto', padding: '0.3rem 0.9rem', borderRadius: 7, border: '1px solid #1e293b', background: 'transparent', color: '#94a3b8', cursor: 'pointer', fontSize: '0.8rem' },
  tabRow: { display: 'flex', gap: '0.15rem', overflowX: 'auto' },
  tab: { padding: '0.6rem 1rem', border: 'none', background: 'transparent', color: '#64748b', cursor: 'pointer', fontSize: '0.83rem', fontWeight: 500, borderBottom: '2px solid transparent', borderRadius: '6px 6px 0 0', whiteSpace: 'nowrap', transition: 'all 0.15s' },
  tabActive: { color: '#a5b4fc', borderBottomColor: '#6366f1' },
  contentArea: { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' },
  scrollPad: { padding: '1.75rem 2rem', overflowY: 'auto', flex: 1 },
  loadingMsg: { textAlign: 'center', color: '#64748b', marginTop: '3rem' },
  genBtn: { padding: '0.75rem 2rem', borderRadius: 10, border: 'none', background: '#1e1b4b', color: '#a5b4fc', cursor: 'pointer', display: 'block', margin: '3rem auto' },
  splash: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '80vh', color: '#64748b' },
}
