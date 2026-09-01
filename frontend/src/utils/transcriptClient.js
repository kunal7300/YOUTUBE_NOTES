/**
 * transcriptClient.js – Extract YouTube captions client-side via Vercel Edge proxy.
 *
 * Flow:
 *   1. Fetch the YouTube watch page HTML through /api/proxy
 *   2. Extract captionTracks JSON from the HTML
 *   3. Fetch the TimedText XML for the best caption track via /api/proxy
 *   4. Parse the XML and return plain transcript text
 */

/**
 * Extract video ID from a YouTube URL.
 */
function extractVideoId(url) {
  const m = url.match(/(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})/)
  return m ? m[1] : null
}

/**
 * Fetch transcript text for a YouTube video using the Vercel Edge proxy.
 *
 * @param {string} youtubeUrl – Full YouTube watch URL
 * @returns {Promise<string|null>} – Transcript text, or null if extraction failed
 */
export async function fetchTranscriptClientSide(youtubeUrl) {
  const videoId = extractVideoId(youtubeUrl)
  if (!videoId) return null

  try {
    // Step 1: Fetch YouTube page HTML via our Edge proxy
    const pageUrl = `https://www.youtube.com/watch?v=${videoId}`
    const proxyBase = '/api/proxy'
    const htmlResp = await fetch(`${proxyBase}?url=${encodeURIComponent(pageUrl)}`)
    if (!htmlResp.ok) return null
    const html = await htmlResp.text()

    // Step 2: Extract captionTracks from the HTML
    const match = html.match(/"captionTracks":(\[.*?\])/)
    if (!match) return null

    let tracks
    try {
      tracks = JSON.parse(match[1])
    } catch {
      return null
    }
    if (!tracks || tracks.length === 0) return null

    // Step 3: Pick best track (prefer English, then Hindi, then first)
    let bestTrack = tracks[0]
    for (const t of tracks) {
      const code = (t.languageCode || '').toLowerCase()
      if (code.startsWith('en')) { bestTrack = t; break }
    }
    // Also check Hindi if no English found
    if (!bestTrack.languageCode?.startsWith('en')) {
      for (const t of tracks) {
        const code = (t.languageCode || '').toLowerCase()
        if (code.startsWith('hi')) { bestTrack = t; break }
      }
    }

    const baseUrl = bestTrack.baseUrl
    if (!baseUrl) return null

    // Step 4: Fetch the TimedText XML via proxy
    const xmlResp = await fetch(`${proxyBase}?url=${encodeURIComponent(baseUrl)}`)
    if (!xmlResp.ok) return null
    const xmlText = await xmlResp.text()
    if (!xmlText.trim()) return null

    // Step 5: Parse XML and extract text segments
    const parser = new DOMParser()
    const doc = parser.parseFromString(xmlText, 'text/xml')
    const textElements = doc.querySelectorAll('text')

    if (textElements.length === 0) return null

    const segments = []
    textElements.forEach(el => {
      const text = (el.textContent || '').trim()
      if (text) {
        // Decode HTML entities
        const decoded = text
          .replace(/&amp;/g, '&')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&quot;/g, '"')
          .replace(/&#39;/g, "'")
        segments.push(decoded)
      }
    })

    if (segments.length === 0) return null

    return segments.join(' ')
  } catch (err) {
    console.warn('Client-side transcript extraction failed:', err)
    return null
  }
}
