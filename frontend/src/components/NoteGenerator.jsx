import { useState, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamNotes } from '../utils/api'
import { useAuth } from '../context/AuthContext'
import ChatPanel from './ChatPanel'
import AuthModal from './AuthModal'

import { API_BASE } from '../config'
const API = API_BASE


// ─── Status enum ─────────────────────────────────────────────────────────────
const STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  STREAMING: 'streaming',
  DONE: 'done',
  ERROR: 'error',
}

// ─── Styles (inline — no extra CSS file needed for Phase 1) ──────────────────
const styles = {
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '2rem 1.5rem',
  },
  header: {
    marginBottom: '2rem',
    textAlign: 'center',
  },
  title: {
    fontSize: '1.8rem',
    fontWeight: 700,
    color: '#ff4444',
    marginBottom: '0.4rem',
  },
  subtitle: {
    color: '#888',
    fontSize: '0.95rem',
  },
  form: {
    display: 'flex',
    gap: '0.75rem',
    marginBottom: '1.5rem',
  },
  input: {
    flex: 1,
    padding: '0.75rem 1rem',
    borderRadius: '8px',
    border: '1px solid #1e293b',
    background: '#0f172a',
    color: '#e8e8e8',
    fontSize: '0.95rem',
    outline: 'none',
  },
  langSelect: {
    padding: '0.75rem 0.75rem',
    borderRadius: '8px',
    border: '1px solid #1e293b',
    background: '#0f172a',
    color: '#94a3b8',
    fontSize: '0.85rem',
    cursor: 'pointer',
    outline: 'none',
    flexShrink: 0,
  },
  button: {
    padding: '0.75rem 1.5rem',
    borderRadius: '8px',
    border: 'none',
    background: '#ff4444',
    color: '#fff',
    fontWeight: 600,
    cursor: 'pointer',
    fontSize: '0.95rem',
    transition: 'opacity 0.2s',
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.75rem',
  },
  statusBadge: {
    fontSize: '0.8rem',
    padding: '0.2rem 0.6rem',
    borderRadius: '999px',
    background: '#1a1a1a',
    border: '1px solid #333',
    color: '#aaa',
  },
  downloadBtn: {
    padding: '0.4rem 1rem',
    borderRadius: '8px',
    border: '1px solid #333',
    background: '#1a1a1a',
    color: '#e8e8e8',
    cursor: 'pointer',
    fontSize: '0.85rem',
    textDecoration: 'none',
  },
  saveBtn: {
    padding: '0.4rem 1rem',
    borderRadius: '8px',
    border: 'none',
    background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '0.85rem',
    fontWeight: 600,
  },
  previewPanel: {
    background: '#141414',
    border: '1px solid #262626',
    borderRadius: '10px',
    padding: '1.5rem 2rem',
    minHeight: '300px',
    lineHeight: '1.7',
    overflowY: 'auto',
  },
  placeholder: {
    color: '#555',
    textAlign: 'center',
    marginTop: '4rem',
    fontSize: '0.95rem',
  },
  errorBox: {
    background: '#2a0a0a',
    border: '1px solid #6b1212',
    borderRadius: '8px',
    padding: '1rem 1.25rem',
    color: '#ff6b6b',
    marginBottom: '1rem',
    fontSize: '0.9rem',
  },
  cursor: {
    display: 'inline-block',
    width: '2px',
    height: '1em',
    background: '#ff4444',
    verticalAlign: 'text-bottom',
    animation: 'blink 0.8s step-end infinite',
  },
}

// Inject blink keyframe once
const blinkStyle = document.createElement('style')
blinkStyle.textContent = `@keyframes blink { 50% { opacity: 0 } }`
document.head.appendChild(blinkStyle)

// ─── Markdown prose styles ────────────────────────────────────────────────────
const proseStyle = document.createElement('style')
proseStyle.textContent = `
  .md-preview h1, .md-preview h2 { color: #fff; border-bottom: 1px solid #333; padding-bottom: 0.3em; margin: 1.4em 0 0.6em; }
  .md-preview h3 { color: #ddd; margin: 1.1em 0 0.4em; }
  .md-preview h4 { color: #bbb; margin: 0.8em 0 0.3em; }
  .md-preview p { margin: 0.5em 0; }
  .md-preview ul, .md-preview ol { padding-left: 1.5em; margin: 0.4em 0; }
  .md-preview li { margin: 0.25em 0; }
  .md-preview blockquote { border-left: 3px solid #ff4444; padding-left: 1em; color: #aaa; margin: 0.75em 0; }
  .md-preview code { background: #1e1e1e; padding: 0.15em 0.4em; border-radius: 4px; font-size: 0.88em; color: #e06c75; }
  .md-preview pre { background: #1e1e1e; padding: 1em; border-radius: 8px; overflow-x: auto; margin: 0.75em 0; }
  .md-preview pre code { background: transparent; padding: 0; color: #abb2bf; }
  .md-preview strong { color: #fff; }
  .md-preview hr { border: none; border-top: 1px solid #333; margin: 1.5em 0; }
  .md-preview table { border-collapse: collapse; width: 100%; margin: 0.75em 0; }
  .md-preview th, .md-preview td { border: 1px solid #333; padding: 0.4em 0.75em; }
  .md-preview th { background: #1e1e1e; }
`
document.head.appendChild(proseStyle)

// ─── Component ────────────────────────────────────────────────────────────────
export default function NoteGenerator() {
  const { user, getToken } = useAuth()
  const [url, setUrl] = useState('')
  const [language, setLanguage] = useState('hinglish')
  const [model, setModel] = useState('qwen/qwen3.6-27b')
  const [markdown, setMarkdown] = useState('')
  const [status, setStatus] = useState(STATUS.IDLE)
  const [errorMsg, setErrorMsg] = useState('')
  const [saving, setSaving] = useState(false)
  const [savedNoteId, setSavedNoteId] = useState(null)
  const [savedTitle, setSavedTitle] = useState('')
  const [showChat, setShowChat] = useState(false)
  const [showAuth, setShowAuth] = useState(false)
  const [videoTitle, setVideoTitle] = useState('')
  const abortRef = useRef(null)

  const isRunning = status === STATUS.LOADING || status === STATUS.STREAMING

  // Fetch real YouTube video title via oEmbed (no API key needed)
  const fetchVideoTitle = async (videoUrl) => {
    try {
      const res = await fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(videoUrl)}&format=json`)
      const data = await res.json()
      return data.title || ''
    } catch {
      return ''
    }
  }

  const handleGenerate = useCallback(() => {
    if (!url.trim()) return
    if (abortRef.current) abortRef.current()
    setMarkdown('')
    setErrorMsg('')
    setSavedNoteId(null)
    setSavedTitle('')
    setShowChat(false)
    setVideoTitle('')
    setStatus(STATUS.LOADING)

    // Fetch title in background
    fetchVideoTitle(url.trim()).then(t => setVideoTitle(t))

    const { abort } = streamNotes(url.trim(), {
      onToken: (token) => {
        setStatus(STATUS.STREAMING)
        setMarkdown((prev) => prev + token)
      },
      onError: (msg) => {
        setErrorMsg(msg)
        setStatus(STATUS.ERROR)
      },
      onDone: () => setStatus(STATUS.DONE),
    }, language, model)
    abortRef.current = abort
  }, [url, language, model])

  const handleStop = () => {
    if (abortRef.current) abortRef.current()
    setStatus(STATUS.DONE)
  }

  const handleSaveAndChat = async () => {
    if (!user) { setShowAuth(true); return }
    setSaving(true)
    try {
      // Use real title, fallback to fetched title, fallback to video ID
      const title = videoTitle || await fetchVideoTitle(url.trim()) || url.replace(/.*v=/, '').slice(0, 50) || 'Untitled'
      const res = await fetch(`${API}/store-notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ youtube_url: url, title, notes_text: markdown, language }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Server error')
      }
      const data = await res.json()
      setSavedNoteId(data.note_id)
      setSavedTitle(title)
      setShowChat(true)
    } catch (e) {
      alert('Failed to save notes: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDownload = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'lecture-notes.md'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const statusLabel = {
    [STATUS.IDLE]: 'Ready',
    [STATUS.LOADING]: 'Fetching transcript…',
    [STATUS.STREAMING]: 'Generating notes…',
    [STATUS.DONE]: 'Done',
    [STATUS.ERROR]: 'Error',
  }[status]

  return (
    <div style={styles.container}>
      {/* Header with small illustration */}
      <div style={styles.header}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '0.75rem' }}>
          <div style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
              <path d="M6 6h10" />
              <path d="M6 10h10" />
              <path d="M6 14h6" />
              <polygon points="18 13 18 19 22 16" fill="#ffffff" stroke="none" />
            </svg>
          </div>
        </div>
        <div style={styles.title}>Lecture Notes</div>
        <div style={styles.subtitle}>Paste a YouTube URL and get structured notes instantly.</div>
      </div>

      {/* URL Input + Model + Language + Button */}
      <div style={styles.form}>
        <input
          style={styles.input}
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !isRunning && handleGenerate()}
          disabled={isRunning}
        />
        <select
          style={styles.langSelect}
          value={model}
          onChange={e => setModel(e.target.value)}
          disabled={isRunning}
          title="Select Groq Model"
        >
          <option value="qwen/qwen3.6-27b">Qwen 3.6 27B</option>
          <option value="openai/gpt-oss-20b">GPT-OSS 20B</option>
          <option value="qwen/qwen3.8-27b">Qwen 3.8 27B</option>
          <option value="openai/gpt-oss-120b">GPT-OSS 120B</option>
        </select>
        <select
          style={styles.langSelect}
          value={language}
          onChange={e => setLanguage(e.target.value)}
          disabled={isRunning}
          title="Select Language"
        >
          <option value="hinglish">Hinglish</option>
          <option value="english">English</option>
          <option value="hindi">Hindi</option>
        </select>
        {isRunning ? (
          <button style={{ ...styles.button, background: '#374151' }} onClick={handleStop}>Stop</button>
        ) : (
          <button style={{ ...styles.button, ...(!url.trim() ? styles.buttonDisabled : {}) }}
            onClick={handleGenerate} disabled={!url.trim()}>
            Generate
          </button>
        )}
      </div>

      {/* Error box */}
      {status === STATUS.ERROR && (
        <div style={styles.errorBox}>{errorMsg}</div>
      )}

      {/* Toolbar */}
      {(markdown || isRunning) && (
        <div style={styles.toolbar}>
          <span style={styles.statusBadge}>{statusLabel}</span>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {/* Show Save & Chat whenever there's content and we're not streaming */}
            {markdown && !isRunning && !savedNoteId && (
              <button style={styles.saveBtn} onClick={handleSaveAndChat} disabled={saving}>
                {saving ? 'Saving...' : 'Save & Chat'}
              </button>
            )}
            {savedNoteId && (
              <span style={{ color: '#22c55e', fontSize: '0.85rem', fontWeight: 600 }}>
                Saved
              </span>
            )}
            {markdown && !isRunning && (
              <button style={styles.downloadBtn} onClick={handleDownload}>
                Download .md
              </button>
            )}
            {isRunning && (
              <button style={{ ...styles.downloadBtn, color: '#ef4444', borderColor: '#7f1d1d' }} onClick={handleStop}>
                Stop
              </button>
            )}
          </div>
        </div>
      )}

      {/* Preview panel */}
      <div style={styles.previewPanel}>
        {!markdown && !isRunning && status === STATUS.IDLE && (
          <div style={styles.placeholder}>
            Your lecture notes will appear here…
          </div>
        )}
        {!markdown && status === STATUS.LOADING && (
          <div style={styles.placeholder}>Fetching transcript, please wait…</div>
        )}
        {markdown && (
          <div className="md-preview">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {markdown}
            </ReactMarkdown>
            {status === STATUS.STREAMING && <span style={styles.cursor} />}
          </div>
        )}
      </div>

      {/* RAG Chat Panel (shown after saving) */}
      {savedNoteId && showChat && (
        <ChatPanel noteId={savedNoteId} noteTitle={savedTitle || videoTitle || 'Notes'} />
      )}

      {/* Auth Modal */}
      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </div>
  )
}
