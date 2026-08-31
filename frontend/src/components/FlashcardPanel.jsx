// FlashcardPanel.jsx — Flip-card study mode with clean typography
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'

import { API_BASE } from '../config'
const API = API_BASE

export default function FlashcardPanel({ noteId }) {
  const { getToken } = useAuth()
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [idx, setIdx] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [known, setKnown] = useState(new Set())

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/flashcards/${noteId}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.detail || 'Failed to load flashcards')
        }
        const d = await res.json()
        setCards(d.flashcards || [])
      } catch (e) { setError(e.message) }
      finally { setLoading(false) }
    }
    load()
  }, [noteId])

  const go = (dir) => {
    setFlipped(false)
    setTimeout(() => setIdx(i => Math.max(0, Math.min(cards.length - 1, i + dir))), 150)
  }

  const markKnown = () => {
    setKnown(prev => new Set([...prev, idx]))
    if (idx < cards.length - 1) go(1)
  }

  if (loading) return <div style={s.center}>Generating flashcards...</div>
  if (error) return <div style={s.center}>{error}</div>
  if (!cards.length) return <div style={s.center}>No flashcards available.</div>

  const card = cards[idx]
  const isKnown = known.has(idx)
  const remaining = cards.length - known.size

  return (
    <div style={s.wrap}>
      {/* Progress */}
      <div style={s.progress}>
        <span style={s.counter}>{idx + 1} / {cards.length}</span>
        <div style={s.progressBar}>
          <div style={{ ...s.progressFill, width: `${((idx + 1) / cards.length) * 100}%` }} />
        </div>
        <span style={s.remaining}>Known: {known.size}</span>
      </div>

      {/* Card */}
      <div style={s.cardWrap} onClick={() => setFlipped(f => !f)}>
        <div style={{ ...s.card, ...(flipped ? s.cardFlipped : {}) }}>
          <div style={s.cardFront}>
            <div style={s.cardLabel}>Question</div>
            <div style={s.cardText}>{card?.front}</div>
            <div style={s.tapHint}>Click to flip</div>
          </div>
          <div style={s.cardBack}>
            <div style={{ ...s.cardLabel, color: '#4ade80' }}>Answer</div>
            <div style={s.cardText}>{card?.back}</div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div style={s.controls}>
        <button style={{ ...s.btn, ...s.btnOutline }} onClick={() => go(-1)} disabled={idx === 0}>Previous</button>
        {flipped && !isKnown && (
          <button style={{ ...s.btn, ...s.btnGreen }} onClick={markKnown}>Mark Known</button>
        )}
        {flipped && isKnown && (
          <span style={s.knownBadge}>Known</span>
        )}
        {!flipped && (
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={() => setFlipped(true)}>Flip</button>
        )}
        <button style={{ ...s.btn, ...s.btnOutline }} onClick={() => go(1)} disabled={idx === cards.length - 1}>Next</button>
      </div>

      {remaining === 0 && (
        <div style={s.done}>
          <div>You have reviewed all {cards.length} cards.</div>
          <button style={s.resetBtn} onClick={() => { setKnown(new Set()); setIdx(0); setFlipped(false) }}>Start Over</button>
        </div>
      )}
    </div>
  )
}

const flipStyle = document.createElement('style')
flipStyle.textContent = `
  .card-inner { transition: transform 0.4s cubic-bezier(0.4,0,0.2,1); transform-style: preserve-3d; }
  .card-flipped .card-inner { transform: rotateY(180deg); }
`
document.head.appendChild(flipStyle)

const s = {
  wrap: { padding: '1.5rem', overflowY: 'auto', maxWidth: 600, margin: '0 auto' },
  center: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: '#64748b', fontSize: '0.9rem' },
  progress: { display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' },
  counter: { color: '#64748b', fontSize: '0.85rem', minWidth: 50 },
  progressBar: { flex: 1, height: 4, background: '#1e293b', borderRadius: 99 },
  progressFill: { height: '100%', background: 'linear-gradient(90deg,#7c3aed,#4f46e5)', borderRadius: 99, transition: 'width 0.3s' },
  remaining: { color: '#22c55e', fontSize: '0.8rem', minWidth: 70, textAlign: 'right' },
  cardWrap: { perspective: 1000, cursor: 'pointer', marginBottom: '1.5rem' },
  card: { position: 'relative', minHeight: 220, transformStyle: 'preserve-3d', transition: 'transform 0.4s cubic-bezier(0.4,0,0.2,1)' },
  cardFlipped: { transform: 'rotateY(180deg)' },
  cardFront: { position: 'absolute', inset: 0, background: '#0d0d1a', border: '1px solid #1e293b', borderRadius: 12, padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden' },
  cardBack: { position: 'absolute', inset: 0, background: '#0a1628', border: '1px solid #1e3a5f', borderRadius: 12, padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', transform: 'rotateY(180deg)', backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden' },
  cardLabel: { fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', color: '#a5b4fc', marginBottom: '1rem', textTransform: 'uppercase' },
  cardText: { color: '#e2e8f0', fontSize: '0.95rem', lineHeight: 1.7, textAlign: 'center' },
  tapHint: { position: 'absolute', bottom: '1rem', color: '#475569', fontSize: '0.75rem' },
  controls: { display: 'flex', gap: '0.75rem', justifyContent: 'center', alignItems: 'center' },
  btn: { padding: '0.55rem 1.25rem', borderRadius: 8, fontSize: '0.85rem', fontWeight: 500, cursor: 'pointer' },
  btnOutline: { border: '1px solid #1e293b', background: 'transparent', color: '#64748b' },
  btnPrimary: { border: 'none', background: '#1e1b4b', color: '#a5b4fc' },
  btnGreen: { border: 'none', background: '#14532d', color: '#4ade80' },
  knownBadge: { color: '#22c55e', fontSize: '0.85rem' },
  done: { textAlign: 'center', marginTop: '2rem', color: '#a5b4fc', fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' },
  resetBtn: { padding: '0.45rem 1.2rem', borderRadius: 6, border: 'none', background: '#1e1b4b', color: '#a5b4fc', cursor: 'pointer', fontSize: '0.85rem' },
}
