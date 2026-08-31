// src/context/ThemeContext.jsx — Light/Dark theme with CSS variables
import { createContext, useContext, useState, useEffect } from 'react'

const ThemeContext = createContext(null)

// CSS variables — dark is default, light overrides
const darkVars = `
  :root {
    --bg: #07070f;
    --bg-surface: #09090f;
    --bg-card: #0d0d1a;
    --bg-input: #0f172a;
    --border: #1e293b;
    --border-subtle: #0f172a;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #475569;
    --text-faint: #334155;
    --accent: #6366f1;
    --accent-light: #a5b4fc;
    --user-bubble: #3730a3;
    --ai-bubble: #0f172a;
    --nav-bg: #0a0a14;
  }
`

const lightVars = `
  [data-theme="light"] {
    --bg: #f8fafc;
    --bg-surface: #f1f5f9;
    --bg-card: #ffffff;
    --bg-input: #f8fafc;
    --border: #e2e8f0;
    --border-subtle: #e2e8f0;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #64748b;
    --text-faint: #94a3b8;
    --accent: #4f46e5;
    --accent-light: #6366f1;
    --user-bubble: #4f46e5;
    --ai-bubble: #f1f5f9;
    --nav-bg: #ffffff;
  }
  [data-theme="light"] body { background: #f8fafc !important; color: #0f172a !important; }
  [data-theme="light"] nav { background: #ffffff !important; border-color: #e2e8f0 !important; }
  [data-theme="light"] aside { background: #f1f5f9 !important; border-color: #e2e8f0 !important; }
  [data-theme="light"] .notes-md p, [data-theme="light"] .notes-md li { color: #374151 !important; }
  [data-theme="light"] .notes-md h1, [data-theme="light"] .notes-md h2, [data-theme="light"] .notes-md h3 { color: #111827 !important; border-color: #e2e8f0 !important; }
  [data-theme="light"] .notes-md strong { color: #111827 !important; }
  [data-theme="light"] .notes-md code { background: #f1f5f9 !important; color: #4f46e5 !important; }
  [data-theme="light"] .notes-md blockquote { color: #6b7280 !important; border-color: #6366f1 !important; }
  [data-theme="light"] .md-preview { background: #fff !important; color: #0f172a !important; }
  [data-theme="light"] .chat-md p, [data-theme="light"] .chat-md li { color: #374151 !important; }
  [data-theme="light"] ::-webkit-scrollbar-track { background: #f1f5f9 !important; }
  [data-theme="light"] ::-webkit-scrollbar-thumb { background: #cbd5e1 !important; }
`

// Inject style tag once
let styleEl = null
function injectStyles() {
  if (!styleEl) {
    styleEl = document.createElement('style')
    styleEl.id = 'theme-vars'
    document.head.appendChild(styleEl)
  }
  styleEl.textContent = darkVars + lightVars
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')

  useEffect(() => {
    injectStyles()
  }, [])

  useEffect(() => {
    localStorage.setItem('theme', theme)
    document.documentElement.setAttribute('data-theme', theme)
    document.body.style.background = theme === 'light' ? '#f8fafc' : '#07070f'
    document.body.style.color = theme === 'light' ? '#0f172a' : '#e2e8f0'
  }, [theme])

  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return (
    <ThemeContext.Provider value={{ theme, toggle, isDark: theme === 'dark' }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) return { theme: 'dark', toggle: () => {}, isDark: true }
  return ctx
}
