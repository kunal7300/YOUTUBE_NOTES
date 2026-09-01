/**
 * api.js – Wrapper for the /generate-notes SSE endpoint.
 *
 * Usage:
 *   const { eventSource, abort } = streamNotes(url, {
 *     onToken: (token) => ...,
 *     onError: (message) => ...,
 *     onDone: () => ...,
 *   });
 *
 * Note: We use a POST request with fetch + ReadableStream instead of
 * the native EventSource API because EventSource only supports GET.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

/**
 * Stream notes for a YouTube URL via SSE.
 *
 * @param {string} youtubeUrl
 * @param {{ onToken: Function, onError: Function, onDone: Function }} callbacks
 * @returns {{ abort: Function }} – Call abort() to cancel the stream.
 */
export function streamNotes(youtubeUrl, { onToken, onError, onDone }, language = 'hinglish', model = 'qwen/qwen3.6-27b', transcriptText = null) {
  const controller = new AbortController()

  ;(async () => {
    let response
    try {
      const body = { url: youtubeUrl, language, model }
      if (transcriptText) body.transcript_text = transcriptText

      response = await fetch(`${API_BASE}/generate-notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    } catch (err) {
      if (err.name === 'AbortError') return
      onError('Could not connect to the server. Is the backend running?')
      return
    }

    if (!response.ok) {
      onError(`Server error: ${response.status} ${response.statusText}`)
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      let done, value
      try {
        ;({ done, value } = await reader.read())
      } catch {
        break
      }
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE events are separated by double newlines
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? '' // Last incomplete chunk stays in buffer

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data:')) continue

        const raw = line.slice(5).trim()

        if (raw === '[DONE]') {
          onDone()
          return
        }

        try {
          const parsed = JSON.parse(raw)
          if (parsed.error) {
            onError(parsed.error)
            return
          }
          if (parsed.token !== undefined) {
            onToken(parsed.token)
          }
        } catch {
          // Ignore malformed SSE lines
        }
      }
    }

    onDone()
  })()

  return { abort: () => controller.abort() }
}
