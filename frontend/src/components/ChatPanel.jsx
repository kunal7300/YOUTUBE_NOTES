// ChatPanel.jsx — Clean RAG chat, no bot icons, professional bubbles
import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { API_BASE } from '../config'
const API = API_BASE

export default function ChatPanel({ noteId, noteTitle }) {
  const { getToken } = useAuth()
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/chat-history/${noteId}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        const data = await res.json()
        if (data.messages) setMessages(data.messages.map(m => ({ role: m.role, content: m.content })))
      } catch (e) { console.error(e) }
      finally { setLoadingHistory(false) }
    }
    load()
  }, [noteId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!question.trim() || loading) return
    const q = question.trim()
    setQuestion('')
    setMessages(prev => [...prev, { role: 'user', content: q }, { role: 'assistant', content: '' }])
    setLoading(true)

    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ note_id: noteId, question: q }),
      })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6)
          if (raw === '[DONE]') break
          try {
            const { token: tok, error } = JSON.parse(raw)
            if (error) {
              setMessages(prev => { const m = [...prev]; m[m.length - 1].content = `Error: ${error}`; return m })
            } else if (tok) {
              setMessages(prev => { const m = [...prev]; m[m.length - 1] = { ...m[m.length - 1], content: m[m.length - 1].content + tok }; return m })
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      setMessages(prev => { const m = [...prev]; m[m.length - 1].content = `Error: ${err.message}`; return m })
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div style={s.container}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <div style={s.headerTitle}>Chat with Notes</div>
          <div style={s.headerSub}>{noteTitle}</div>
        </div>
        <div style={s.headerBadge}>AI-powered</div>
      </div>

      {/* Messages */}
      <div style={s.messages}>
        {loadingHistory ? (
          <div style={s.centered}>Loading history…</div>
        ) : messages.length === 0 ? (
          <div style={s.empty}>
            <div style={s.emptyIcon}>💬</div>
            <div style={s.emptyTitle}>Ask anything about these notes</div>
            <div style={s.emptyHint}>Try: "What are the key concepts?" or "Explain RAG in Hinglish"</div>
            <div style={s.suggestions}>
              {['Main topics kya hain?', 'Explain with real-world example', 'Interview ke liye key points'].map(q => (
                <button key={q} style={s.suggBtn} onClick={() => { setQuestion(q) }}>{q}</button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} style={msg.role === 'user' ? s.userRow : s.aiRow}>
              <div style={msg.role === 'user' ? s.userBubble : s.aiBubble}>
                {msg.role === 'user' ? (
                  <span style={s.userText}>{msg.content}</span>
                ) : (
                  <div style={s.aiText} className="chat-md">
                    {msg.content
                      ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                      : <span style={{ opacity: 0.4 }}>▌</span>
                    }
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={s.inputBar}>
        <textarea
          ref={inputRef}
          style={s.textarea}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          rows={1}
          disabled={loading}
        />
        <button
          style={{ ...s.sendBtn, opacity: loading || !question.trim() ? 0.4 : 1 }}
          onClick={sendMessage}
          disabled={loading || !question.trim()}
        >
          {loading ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /></svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
          )}
        </button>
      </div>
    </div>
  )
}

// Inject chat markdown styles
const chatStyle = document.createElement('style')
chatStyle.textContent = `
  .chat-md p { margin: 0.35em 0; }
  .chat-md ul, .chat-md ol { padding-left: 1.4em; margin: 0.4em 0; }
  .chat-md li { margin: 0.2em 0; }
  .chat-md strong { color: #e2e8f0; }
  .chat-md code { background: #1e293b; padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.85em; color: #a5b4fc; }
  .chat-md blockquote { border-left: 2px solid #4f46e5; padding-left: 0.75em; color: #94a3b8; margin: 0.5em 0; }
`
document.head.appendChild(chatStyle)

const s = {
  container: { display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a14' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.5rem', borderBottom: '1px solid #0f172a', flexShrink: 0 },
  headerTitle: { fontWeight: 600, color: '#e2e8f0', fontSize: '0.9rem' },
  headerSub: { color: '#475569', fontSize: '0.75rem', marginTop: 2, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  headerBadge: { fontSize: '0.7rem', padding: '0.25rem 0.6rem', borderRadius: 999, background: '#1e1b4b', color: '#818cf8', border: '1px solid #312e81' },
  messages: { flex: 1, overflowY: 'auto', padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' },
  centered: { textAlign: 'center', color: '#334155', paddingTop: '3rem' },
  empty: { display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: '2.5rem', gap: '0.5rem' },
  emptyIcon: { fontSize: '2.5rem', marginBottom: '0.5rem' },
  emptyTitle: { color: '#94a3b8', fontWeight: 600, fontSize: '1rem' },
  emptyHint: { color: '#475569', fontSize: '0.8rem', marginBottom: '1rem' },
  suggestions: { display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' },
  suggBtn: { padding: '0.4rem 0.9rem', borderRadius: 999, border: '1px solid #1e293b', background: '#0f172a', color: '#64748b', cursor: 'pointer', fontSize: '0.8rem' },
  userRow: { display: 'flex', justifyContent: 'flex-end' },
  aiRow: { display: 'flex', justifyContent: 'flex-start' },
  userBubble: { maxWidth: '72%', background: '#3730a3', borderRadius: '14px 14px 2px 14px', padding: '0.65rem 1rem' },
  aiBubble: { maxWidth: '80%', background: '#0f172a', border: '1px solid #1e293b', borderRadius: '14px 14px 14px 2px', padding: '0.75rem 1rem' },
  userText: { color: '#e0e7ff', fontSize: '0.9rem', lineHeight: 1.6 },
  aiText: { color: '#cbd5e1', fontSize: '0.9rem', lineHeight: 1.7 },
  inputBar: { display: 'flex', gap: '0.75rem', padding: '1rem 1.5rem', borderTop: '1px solid #0f172a', background: '#07070f', flexShrink: 0 },
  textarea: { flex: 1, padding: '0.65rem 1rem', borderRadius: 10, border: '1px solid #1e293b', background: '#0f172a', color: '#e2e8f0', fontSize: '0.9rem', resize: 'none', outline: 'none', fontFamily: 'inherit', lineHeight: 1.5 },
  sendBtn: { width: 40, height: 40, borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, alignSelf: 'flex-end' },
}
