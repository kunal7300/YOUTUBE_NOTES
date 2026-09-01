"""
transcript.py – Fetch captions from YouTube with cloud-deployment resilience.

Strategy:
  1. youtube-transcript-api with SOCS consent cookie (bypasses EU/bot consent wall)
  2. Direct Innertube API POST (works from datacenter IPs)
  3. Web page HTML scraping + TimedText XML parse (final fallback)
"""

from dataclasses import dataclass
from typing import List, Optional
import re
import os
import json
import html
import tempfile
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import base64
import struct


class TranscriptError(Exception):
    """Raised when transcript cannot be fetched; carries a user-friendly message."""

    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = message


@dataclass
class TranscriptResult:
    video_id: str
    transcript_text: str
    segments: List[dict]
    language: str


# ── Shared helpers ────────────────────────────────────────────────────────────

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# SOCS cookie that pre-accepts YouTube consent (bypasses the GDPR wall
# that blocks headless / datacenter requests).
_CONSENT_COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSOCS\tCAISNQgDEitib3FfaWRlbnRpd"
    "HlfZnJvbnRlbmRfdWlzZXJ2ZXJfMjAyMzExMDguMDdfcDEaAmVuIAEaBgiA_LyaBg\n"
    ".youtube.com\tTRUE\t/\tFALSE\t2147483647\tCONSENT\tPENDING+987\n"
)

def _get_cookies_path() -> str:
    """Return path to a Netscape cookies.txt with consent cookies."""
    path = os.path.join(tempfile.gettempdir(), "yt_consent_cookies.txt")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(_CONSENT_COOKIES)
    return path


def _extract_video_id(url: str) -> str:
    url = url.strip()
    if re.match(r"^[A-Za-z0-9_-]{11}$", url):
        return url
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{11})",
        r"[?&]v=([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise TranscriptError(
        "Could not find a valid YouTube video ID in the URL. "
        "Please paste a valid YouTube link."
    )


def _build_segments(raw) -> List[dict]:
    """Normalise transcript snippets (v1.x objects or dicts) to list of dicts."""
    segments = []
    for s in raw:
        if hasattr(s, "text"):
            segments.append({
                "text": s.text or "",
                "start": float(s.start or 0.0),
                "duration": float(s.duration or 0.0),
            })
        elif isinstance(s, dict):
            segments.append({
                "text": s.get("text", ""),
                "start": float(s.get("start", 0.0)),
                "duration": float(s.get("duration", 0.0)),
            })
    return segments


def _segments_to_result(video_id: str, segments: List[dict], lang: str = "en") -> TranscriptResult:
    full_text = " ".join(s["text"] for s in segments if s["text"])
    return TranscriptResult(video_id=video_id, transcript_text=full_text,
                            segments=segments, language=lang)


# ── Layer 1: youtube-transcript-api with consent cookies ──────────────────────

def _fetch_via_library(video_id: str) -> Optional[TranscriptResult]:
    """Use youtube-transcript-api with SOCS consent cookie."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        cookies_path = _get_cookies_path()
        ytt = YouTubeTranscriptApi(cookies=cookies_path)

        transcript_list = ytt.list(video_id)

        # Search priority: manual EN/HI → generated EN/HI → any track
        transcript = None
        for lang_codes in [["en", "en-US", "en-GB", "en-IN"], ["hi", "hi-IN"]]:
            try:
                transcript = transcript_list.find_manually_created_transcript(lang_codes)
                break
            except Exception:
                pass
        if not transcript:
            for lang_codes in [["en", "en-US", "en-GB", "en-IN"], ["hi", "hi-IN"]]:
                try:
                    transcript = transcript_list.find_generated_transcript(lang_codes)
                    break
                except Exception:
                    pass
        if not transcript:
            try:
                transcript = next(iter(transcript_list))
            except StopIteration:
                return None

        fetched = transcript.fetch()
        segments = _build_segments(fetched)
        if segments:
            return _segments_to_result(video_id, segments, transcript.language_code)
    except Exception:
        pass
    return None


# ── Layer 2: Direct Innertube API ────────────────────────────────────────────

def _build_innertube_params(video_id: str) -> str:
    """Build the base64-encoded protobuf 'params' for get_transcript."""
    # Minimal protobuf: field 1 (string) = "\n" + video_id
    inner = b"\x0a" + bytes([len(video_id)]) + video_id.encode("utf-8")
    # Wrap: field 2 (string) = inner
    outer = b"\x12" + bytes([len(inner)]) + inner
    return base64.b64encode(outer).decode("ascii")


def _fetch_via_innertube(video_id: str) -> Optional[TranscriptResult]:
    """Call YouTube's internal Innertube get_transcript endpoint."""
    try:
        api_url = "https://www.youtube.com/youtubei/v1/get_transcript"
        payload = json.dumps({
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240313.05.00",
                    "hl": "en",
                    "gl": "US",
                }
            },
            "params": _build_innertube_params(video_id),
        }).encode("utf-8")

        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": _BROWSER_HEADERS["User-Agent"],
                "Origin": "https://www.youtube.com",
                "Referer": f"https://www.youtube.com/watch?v={video_id}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Navigate the Innertube response structure
        actions = data.get("actions", [])
        if not actions:
            return None

        body = None
        for action in actions:
            panel = action.get("updateEngagementPanelAction", {}).get("content", {})
            renderer = panel.get("transcriptRenderer", {})
            body_r = renderer.get("body", {}).get("transcriptBodyRenderer", {})
            if body_r:
                body = body_r
                break

        # Alternative path
        if not body:
            for action in actions:
                seg_list = action.get("updateEngagementPanelAction", {}) \
                    .get("content", {}) \
                    .get("transcriptRenderer", {}) \
                    .get("content", {}) \
                    .get("transcriptSearchPanelRenderer", {}) \
                    .get("body", {}) \
                    .get("transcriptSegmentListRenderer", {})
                if seg_list:
                    body = seg_list
                    break

        if not body:
            return None

        initial_segments = body.get("initialSegments", [])
        segments = []
        for seg in initial_segments:
            renderer = seg.get("transcriptSegmentRenderer", {})
            snippet = renderer.get("snippet", {}).get("runs", [])
            text = "".join(r.get("text", "") for r in snippet).strip()
            start_ms = int(renderer.get("startMs", "0"))
            end_ms = int(renderer.get("endMs", "0"))
            if text:
                segments.append({
                    "text": text,
                    "start": start_ms / 1000.0,
                    "duration": (end_ms - start_ms) / 1000.0,
                })

        if segments:
            return _segments_to_result(video_id, segments, "en")
    except Exception:
        pass
    return None


# ── Layer 3: Web page HTML + TimedText XML ───────────────────────────────────

def _fetch_via_web_scrape(video_id: str) -> Optional[TranscriptResult]:
    """Scrape captionTracks from YouTube HTML and fetch the TimedText XML."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        cookie_handler = urllib.request.HTTPCookieProcessor()
        opener = urllib.request.build_opener(cookie_handler)
        
        headers = dict(_BROWSER_HEADERS)
        headers["Cookie"] = "SOCS=CAISNQgDEitib3FfaWRlbnRpdHlfZnJvbnRlbmRfdWlzZXJ2ZXJfMjAyMzExMDguMDdfcDEaAmVuIAEaBgiA_LyaBg; CONSENT=PENDING+987"
        
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=15) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        m = re.search(r'"captionTracks":(\[.*?\])', html_text)
        if not m:
            return None

        tracks = json.loads(m.group(1))
        if not tracks:
            return None

        # Prefer English or Hindi
        track = tracks[0]
        for t in tracks:
            code = t.get("languageCode", "").lower()
            if code.startswith("en"):
                track = t
                break
        for t in tracks:
            code = t.get("languageCode", "").lower()
            if code.startswith("hi"):
                track = t
                break

        base_url = track.get("baseUrl")
        if not base_url:
            return None

        req2 = urllib.request.Request(base_url, headers=headers)
        with opener.open(req2, timeout=15) as resp2:
            xml_data = resp2.read().decode("utf-8", errors="ignore")

        if not xml_data.strip():
            return None

        root = ET.fromstring(xml_data)
        segments = []
        for elem in root.findall("text"):
            text = html.unescape(elem.text or "").strip()
            if text:
                start = float(elem.attrib.get("start", 0))
                dur = float(elem.attrib.get("dur", 0))
                segments.append({"text": text, "start": start, "duration": dur})

        if segments:
            lang = track.get("languageCode", "en")
            return _segments_to_result(video_id, segments, lang)
    except Exception:
        pass
    return None


# ── Public entry point ───────────────────────────────────────────────────────

def fetch_transcript(url: str) -> TranscriptResult:
    """
    Fetch the transcript for a YouTube video using a 3-layer fallback strategy:
      1. youtube-transcript-api + consent cookies
      2. Direct Innertube API POST
      3. Web HTML scraping + TimedText XML

    Raises TranscriptError if all layers fail.
    """
    video_id = _extract_video_id(url)

    # Layer 1: youtube-transcript-api with consent cookie
    result = _fetch_via_library(video_id)
    if result and result.segments:
        return result

    # Layer 2: Innertube API
    result = _fetch_via_innertube(video_id)
    if result and result.segments:
        return result

    # Layer 3: Web scrape fallback
    result = _fetch_via_web_scrape(video_id)
    if result and result.segments:
        return result

    raise TranscriptError(
        "Could not retrieve the transcript for this video. "
        "This may happen if the video has no subtitles or YouTube is "
        "temporarily blocking requests. Please try a different video."
    )
