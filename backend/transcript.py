"""
transcript.py – Fetch captions from YouTube, with multi-layer fallback & explicit error handling.
Compatible with youtube-transcript-api >= 1.0.0 (instance-based API).
"""

from dataclasses import dataclass
from typing import List, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
import re
import urllib.request
import json
import html
import xml.etree.ElementTree as ET


class TranscriptError(Exception):
    """Raised when transcript cannot be fetched; carries a user-friendly message."""

    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = message


@dataclass
class TranscriptResult:
    video_id: str
    transcript_text: str      # Full concatenated text
    segments: List[dict]      # Raw [{text, start, duration}] list
    language: str


def _extract_video_id(url: str) -> str:
    """
    Extract the YouTube video ID from any format:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/live/VIDEO_ID
    - Direct 11-character video ID
    """
    url = url.strip()
    # Check if raw 11-char ID was passed directly
    if re.match(r"^[A-Za-z0-9_-]{11}$", url):
        return url

    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/|\/live\/)([A-Za-z0-9_-]{11})",
        r"[?&]v=([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
    raise TranscriptError(
        "Could not find a valid YouTube video ID in the URL. "
        "Please paste a valid YouTube watch, short, or youtu.be link."
    )


def _fetch_web_timedtext_fallback(video_id: str) -> Optional[TranscriptResult]:
    """
    Fallback method: Extract captionTracks directly from YouTube HTML
    if the API endpoint is throttled or blocked on cloud hosts.
    """
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        match = re.search(r'"captionTracks":(\[.*?\])', html_text)
        if not match:
            return None

        tracks = json.loads(match.group(1))
        if not tracks:
            return None

        # Prioritize English or Hindi
        track = tracks[0]
        for t in tracks:
            code = t.get("languageCode", "").lower()
            if code.startswith("en") or code.startswith("hi"):
                track = t
                break

        base_url = track.get("baseUrl")
        if not base_url:
            return None

        req2 = urllib.request.Request(base_url, headers=headers)
        with urllib.request.urlopen(req2, timeout=12) as resp2:
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
            full_text = " ".join(s["text"] for s in segments)
            return TranscriptResult(
                video_id=video_id,
                transcript_text=full_text,
                segments=segments,
                language=track.get("languageCode", "en"),
            )
    except Exception:
        pass
    return None


def fetch_transcript(url: str) -> TranscriptResult:
    """
    Fetch the transcript for a YouTube video.
    Uses instance-based YouTubeTranscriptApi with multi-language search
    and automatic Web TimedText fallback.
    """
    video_id = _extract_video_id(url)
    ytt = YouTubeTranscriptApi()

    # ── Attempt 1: Standard YouTubeTranscriptApi.list() ──────────────────────
    try:
        transcript_list = ytt.list(video_id)

        transcript = None
        # 1. Manually created English / Hindi
        for lang_codes in [["en", "en-US", "en-GB", "en-IN"], ["hi", "hi-IN"]]:
            try:
                transcript = transcript_list.find_manually_created_transcript(lang_codes)
                break
            except Exception:
                pass

        # 2. Auto-generated English / Hindi
        if not transcript:
            for lang_codes in [["en", "en-US", "en-GB", "en-IN"], ["hi", "hi-IN"]]:
                try:
                    transcript = transcript_list.find_generated_transcript(lang_codes)
                    break
                except Exception:
                    pass

        # 3. Any available transcript track
        if not transcript:
            try:
                transcript = next(iter(transcript_list))
            except StopIteration:
                pass

        if transcript:
            fetched = transcript.fetch()
            segments = []
            for s in fetched:
                if hasattr(s, "text"):
                    segments.append({
                        "text": s.text or "",
                        "start": float(s.start or 0.0),
                        "duration": float(s.duration or 0.0),
                    })
                else:
                    segments.append({
                        "text": s.get("text", ""),
                        "start": float(s.get("start", 0.0)),
                        "duration": float(s.get("duration", 0.0)),
                    })

            if segments:
                full_text = " ".join(s["text"] for s in segments)
                return TranscriptResult(
                    video_id=video_id,
                    transcript_text=full_text,
                    segments=segments,
                    language=transcript.language_code,
                )

    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        # Fall through to web fallback or raise
        pass
    except Exception:
        # Fall through to web fallback
        pass

    # ── Attempt 2: Direct web timedtext fallback ────────────────────────────
    fallback_res = _fetch_web_timedtext_fallback(video_id)
    if fallback_res and fallback_res.segments:
        return fallback_res

    # ── Attempt 3: Direct get_transcript() helper ────────────────────────────
    try:
        fetched_direct = ytt.get_transcript(video_id)
        if fetched_direct:
            segments = [
                {
                    "text": s.get("text", "") if isinstance(s, dict) else getattr(s, "text", ""),
                    "start": float(s.get("start", 0.0)) if isinstance(s, dict) else getattr(s, "start", 0.0),
                    "duration": float(s.get("duration", 0.0)) if isinstance(s, dict) else getattr(s, "duration", 0.0),
                }
                for s in fetched_direct
            ]
            full_text = " ".join(s["text"] for s in segments)
            return TranscriptResult(
                video_id=video_id,
                transcript_text=full_text,
                segments=segments,
                language="en",
            )
    except Exception:
        pass

    # If all attempts fail, provide clear diagnostic message
    raise TranscriptError(
        "Could not retrieve the transcript for this video. "
        "Please ensure the video has subtitles/captions enabled (not a music video or live stream), or test with a standard lecture."
    )
