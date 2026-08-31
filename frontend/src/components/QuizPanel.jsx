// QuizPanel.jsx — Per-topic MCQ quiz with reveal + score
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'

import { API_BASE } from '../config'
const API = API_BASE

export default function QuizPanel({ noteId }) {
  const { getToken } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revealed, setRevealed] = useState({}) // { "topicIdx-qIdx": true }
  const [selected, setSelected] = useState({}) // { "topicIdx-qIdx": "A" }
  const [score, setScore] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/quiz/${noteId}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.detail || 'Failed to load quiz')
        }
        const d = await res.json()
        setData(d)
      } catch (e) { setError(e.message) }
      finally { setLoading(false) }
    }
    load()
  }, [noteId])

  const totalQ = data?.topics?.reduce((s, t) => s + (t.questions ? t.questions.length : 0), 0) || 0
  const answeredAll = totalQ > 0 && Object.keys(selected).length === totalQ

  const calcScore = () => {
    let correct = 0
    data.topics.forEach((topic, ti) => {
      (topic.questions || []).forEach((q, qi) => {
        const key = `${ti}-${qi}`
        if (selected[key] === q.correct) correct++
      })
    })
    const allRevealed = {}
    data.topics.forEach((t, ti) => (t.questions || []).forEach((_, qi) => { allRevealed[`${ti}-${qi}`] = true }))
    setRevealed(allRevealed)
    setScore({ correct, total: totalQ })
  }

  const reset = () => { setSelected({}); setRevealed({}); setScore(null) }

  if (loading) return <div style={s.center}>Generating quiz...</div>
  if (error) return <div style={s.center}>{error}</div>
  if (!data?.topics?.length) return <div style={s.center}>No quiz data available.</div>

  return (
    <div style={s.wrap}>
      {score && (
        <div style={{ ...s.scoreBanner, background: score.correct / score.total >= 0.7 ? '#064e3b' : '#450a0a' }}>
          <span>Score: <strong>{score.correct}/{score.total}</strong> ({Math.round(score.correct / score.total * 100)}%)</span>
          <button style={s.resetBtn} onClick={reset}>Try Again</button>
        </div>
      )}

      {data.topics.map((topic, ti) => (
        <div key={ti} style={s.topicBlock}>
          <div style={s.topicTitle}>{topic.topic}</div>
          {(topic.questions || []).map((q, qi) => {
            const key = `${ti}-${qi}`
            const isRevealed = revealed[key]
            const userAns = selected[key]
            return (
              <div key={qi} style={s.qCard}>
                <div style={s.qText}>{qi + 1}. {q.question}</div>
                <div style={s.options}>
                  {(q.options || []).map(opt => {
                    const letter = opt.charAt(0)
                    const isCorrect = letter === q.correct
                    const isSelected = userAns === letter
                    let bg = '#0f172a'
                    if (isRevealed) bg = isCorrect ? '#14532d' : (isSelected ? '#450a0a' : '#0f172a')
                    else if (isSelected) bg = '#1e1b4b'
                    return (
                      <button
                        key={letter}
                        style={{ ...s.option, background: bg, border: isSelected ? '1px solid #6366f1' : '1px solid #1e293b' }}
                        onClick={() => !isRevealed && setSelected(p => ({ ...p, [key]: letter }))}
                        disabled={isRevealed}
                      >
                        {opt}
                        {isRevealed && isCorrect && ' (Correct)'}
                      </button>
                    )
                  })}
                </div>
                {!isRevealed && userAns && (
                  <button style={s.revealBtn} onClick={() => setRevealed(p => ({ ...p, [key]: true }))}>
                    Check Answer
                  </button>
                )}
                {isRevealed && (
                  <div style={s.explanation}>Explanation: {q.explanation}</div>
                )}
              </div>
            )
          })}
        </div>
      ))}

      {!score && answeredAll && (
        <button style={s.submitBtn} onClick={calcScore}>Calculate Score</button>
      )}
    </div>
  )
}

const s = {
  wrap: { padding: '1.5rem', overflowY: 'auto' },
  center: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: '#64748b', fontSize: '0.9rem' },
  scoreBanner: { display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.9rem 1.25rem', borderRadius: 8, marginBottom: '1.5rem', color: '#e2e8f0', fontSize: '0.95rem' },
  resetBtn: { marginLeft: 'auto', padding: '0.35rem 0.9rem', borderRadius: 6, border: 'none', background: '#1e293b', color: '#94a3b8', cursor: 'pointer', fontSize: '0.8rem' },
  topicBlock: { marginBottom: '2rem' },
  topicTitle: { fontWeight: 700, color: '#a5b4fc', fontSize: '0.95rem', marginBottom: '1rem', paddingBottom: '0.5rem', borderBottom: '1px solid #1e293b' },
  qCard: { background: '#0d0d1a', border: '1px solid #1e293b', borderRadius: 10, padding: '1rem', marginBottom: '0.75rem' },
  qText: { color: '#e2e8f0', fontSize: '0.9rem', fontWeight: 500, marginBottom: '0.75rem', lineHeight: 1.5 },
  options: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
  option: { padding: '0.55rem 0.9rem', borderRadius: 8, color: '#cbd5e1', cursor: 'pointer', fontSize: '0.875rem', textAlign: 'left', transition: 'all 0.15s' },
  revealBtn: { marginTop: '0.75rem', padding: '0.35rem 0.9rem', borderRadius: 6, border: 'none', background: '#1e1b4b', color: '#a5b4fc', cursor: 'pointer', fontSize: '0.8rem' },
  explanation: { marginTop: '0.75rem', padding: '0.6rem 0.9rem', background: '#0f172a', borderRadius: 8, color: '#94a3b8', fontSize: '0.82rem', lineHeight: 1.6, borderLeft: '3px solid #4f46e5' },
  submitBtn: { width: '100%', padding: '0.75rem', borderRadius: 8, border: 'none', background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer', marginTop: '1rem' },
}
