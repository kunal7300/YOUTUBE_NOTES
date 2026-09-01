"""
transcript.py – Fetch captions from YouTube with multi-strategy cloud resilience.

Strategy:
  1. yt-dlp Python API (Primary: extracts clean subtitle tracks without binary dependency)
  2. YouTubeTranscriptApi.list_transcripts() / get_transcript()
  3. Direct Web HTML Scraping + TimedText XML parse
"""

from dataclasses import dataclass
from typing import List, Optional
import re
import json
import urllib.request
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
    transcript_text: str
    segments: List[dict]
    language: str


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
        "Please paste a valid YouTube watch or youtu.be link."
    )


def _segments_to_result(video_id: str, segments: List[dict], lang: str = "en") -> TranscriptResult:
    full_text = " ".join(s["text"] for s in segments if s["text"])
    return TranscriptResult(
        video_id=video_id,
        transcript_text=full_text,
        segments=segments,
        language=lang,
    )


# ── Layer 1: yt-dlp Python API (Most Reliable) ────────────────────────────────

def _fetch_via_ytdlp(video_id: str) -> Optional[TranscriptResult]:
    """Use yt_dlp library directly in-memory to extract subtitles."""
    try:
        import yt_dlp

        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB", "en-orig", "hi", "all"],
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "mweb", "web"],
                    "player_skip": ["js", "configs", "webpage"],
                }
            },
        }

        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            subs = info.get("subtitles") or {}
            auto_subs = info.get("automatic_captions") or {}

            # Prioritize English, Hindi, or any available track
            target_formats = None
            detected_lang = "en"

            for lang in ["en", "en-US", "en-GB", "en-orig", "hi", "hi-IN"]:
                if lang in subs:
                    target_formats = subs[lang]
                    detected_lang = lang
                    break
                elif lang in auto_subs:
                    target_formats = auto_subs[lang]
                    detected_lang = lang
                    break

            if not target_formats:
                # Take first available language
                if subs:
                    first_lang = next(iter(subs))
                    target_formats = subs[first_lang]
                    detected_lang = first_lang
                elif auto_subs:
                    first_lang = next(iter(auto_subs))
                    target_formats = auto_subs[first_lang]
                    detected_lang = first_lang

            if not target_formats:
                return None

            fmt_map = {f.get("ext"): f.get("url") for f in target_formats if f.get("url")}

            # Try json3 format
            if "json3" in fmt_map:
                req = urllib.request.Request(
                    fmt_map["json3"],
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                segments = []
                for event in data.get("events", []):
                    if "segs" in event:
                        text = "".join(s.get("utf8", "") for s in event["segs"]).strip()
                        if text and text != "\n":
                            start = float(event.get("tStartMs", 0)) / 1000.0
                            dur = float(event.get("dDurationMs", 0)) / 1000.0
                            segments.append({"text": text, "start": start, "duration": dur})

                if segments:
                    return _segments_to_result(video_id, segments, detected_lang)

            # Try srv1 / srv2 / srv3 / ttml XML format
            for ext in ["srv3", "srv2", "srv1", "ttml"]:
                if ext in fmt_map:
                    req = urllib.request.Request(
                        fmt_map[ext],
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    )
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        xml_text = resp.read().decode("utf-8", errors="ignore")

                    root = ET.fromstring(xml_text)
                    segments = []
                    for elem in root.findall(".//text"):
                        text = html.unescape(elem.text or "").strip()
                        if text:
                            start = float(elem.attrib.get("start", 0))
                            dur = float(elem.attrib.get("dur", 0))
                            segments.append({"text": text, "start": start, "duration": dur})

                    if segments:
                        return _segments_to_result(video_id, segments, detected_lang)

    except Exception:
        pass
    return None


# ── Layer 2: YouTubeTranscriptApi ────────────────────────────────────────────

def _fetch_via_library(video_id: str) -> Optional[TranscriptResult]:
    """Standard youtube_transcript_api call."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)

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
        segments = []
        for s in fetched:
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

        if segments:
            return _segments_to_result(video_id, segments, transcript.language_code)
    except Exception:
        pass
    return None


# ── Layer 3: Web HTML Scraping + TimedText XML ────────────────────────────────

def _fetch_via_web_scrape(video_id: str) -> Optional[TranscriptResult]:
    """Scrape captionTracks from YouTube HTML."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        m = re.search(r'"captionTracks":(\[.*?\])', html_text)
        if not m:
            return None

        tracks = json.loads(m.group(1))
        if not tracks:
            return None

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
            return _segments_to_result(video_id, segments, track.get("languageCode", "en"))
    except Exception:
        pass
    return None


# ── Public Entry Point ────────────────────────────────────────────────────────

def fetch_transcript(url: str) -> TranscriptResult:
    """
    Fetch the transcript for a YouTube video.
    Executes multi-layer strategy:
      1. yt-dlp Python API (Primary)
      2. YouTubeTranscriptApi (Secondary)
      3. Web TimedText Scraping (Fallback)
    """
    video_id = _extract_video_id(url)

    # 1. yt-dlp Python API
    res = _fetch_via_ytdlp(video_id)
    if res and res.segments:
        return res

    # 2. YouTubeTranscriptApi
    res = _fetch_via_library(video_id)
    if res and res.segments:
        return res

    # 3. Web Scrape
    res = _fetch_via_web_scrape(video_id)
    if res and res.segments:
        return res

    raise TranscriptError(
        "Could not retrieve the transcript for this video. "
        "Please ensure the video has subtitles/captions enabled or try another lecture."
    )


def fetch_transcript_debug(url: str) -> dict:
    """Diagnostic version that reports each layer's execution result and exact errors."""
    import traceback
    video_id = _extract_video_id(url)
    report = {"video_id": video_id, "layers": {}}

    # Test Layer 1: yt-dlp
    try:
        import yt_dlp
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB", "en-orig", "hi", "all"],
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            subs = list((info.get("subtitles") or {}).keys())
            auto = list((info.get("automatic_captions") or {}).keys())
            report["layers"]["1_ytdlp"] = {
                "status": "INFO_EXTRACTED",
                "manual_subs": subs[:5],
                "auto_subs": auto[:5],
            }
            res = _fetch_via_ytdlp(video_id)
            if res and res.segments:
                report["layers"]["1_ytdlp"]["status"] = "SUCCESS"
                report["layers"]["1_ytdlp"]["segments"] = len(res.segments)
                report["layers"]["1_ytdlp"]["sample"] = res.segments[0]["text"][:60]
    except Exception as e:
        report["layers"]["1_ytdlp"] = {"status": "ERROR", "error": str(e), "trace": traceback.format_exc()}

    # Test Layer 2: YouTubeTranscriptApi
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        tl = ytt.list(video_id)
        transcripts = [f"{t.language} ({t.language_code})" for t in tl]
        report["layers"]["2_library"] = {"status": "LIST_SUCCESS", "available": transcripts[:5]}
    except Exception as e:
        report["layers"]["2_library"] = {"status": "ERROR", "error": str(e), "trace": traceback.format_exc()}

    return report
