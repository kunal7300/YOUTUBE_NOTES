"""
transcript.py – Fetch captions from YouTube, with explicit error handling.
Compatible with youtube-transcript-api >= 1.0.0 (instance-based API).
"""

from dataclasses import dataclass
from typing import List
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
import re


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
    Extract the YouTube video ID from various URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    patterns = [r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise TranscriptError(
        "Could not find a valid YouTube video ID in the URL you provided. "
        "Please check the URL and try again."
    )


def fetch_transcript(url: str) -> TranscriptResult:
    """
    Fetch the transcript for a YouTube video.
    Uses the instance-based API introduced in youtube-transcript-api v1.0.0.

    Raises TranscriptError with a user-friendly message for all known failure modes.
    """
    video_id = _extract_video_id(url)
    ytt = YouTubeTranscriptApi()

    try:
        transcript_list = ytt.list(video_id)

        # Prefer manually created English, fallback to generated, then any language
        try:
            transcript = transcript_list.find_manually_created_transcript(
                ["en", "en-US", "en-GB"]
            )
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(
                    ["en", "en-US", "en-GB"]
                )
            except Exception:
                # Take whatever is available and translate if needed
                transcript = next(iter(transcript_list))
                if transcript.language_code not in ("en", "en-US", "en-GB"):
                    transcript = transcript.translate("en")

        fetched = transcript.fetch()
        # v1.x returns FetchedTranscriptSnippet objects with .text/.start/.duration attributes
        segments = []
        for s in fetched:
            if hasattr(s, "text"):
                # Attribute-based access (v1.x FetchedTranscriptSnippet)
                segments.append({
                    "text": s.text or "",
                    "start": float(s.start or 0.0),
                    "duration": float(s.duration or 0.0),
                })
            else:
                # Fallback: dict-based access (older versions)
                segments.append({
                    "text": s.get("text", ""),
                    "start": float(s.get("start", 0.0)),
                    "duration": float(s.get("duration", 0.0)),
                })
        language = transcript.language_code
        full_text = " ".join(s["text"] for s in segments)

        return TranscriptResult(
            video_id=video_id,
            transcript_text=full_text,
            segments=segments,
            language=language,
        )

    except TranscriptsDisabled:
        raise TranscriptError(
            "This video has captions/subtitles disabled by the uploader. "
            "Transcript generation is not possible for this video."
        )
    except NoTranscriptFound:
        raise TranscriptError(
            "No transcript was found for this video. The video may not have "
            "captions in any language."
        )
    except VideoUnavailable:
        raise TranscriptError(
            "This video is unavailable. It may be private, age-restricted, "
            "or has been deleted."
        )
    except CouldNotRetrieveTranscript as e:
        reason = str(e).lower()
        if "private" in reason:
            raise TranscriptError(
                "This video is private and its transcript cannot be accessed."
            )
        if "age" in reason:
            raise TranscriptError(
                "This video is age-restricted. Sign-in is required to access its transcript."
            )
        raise TranscriptError(
            "Could not retrieve the transcript for this video. "
            "Please try again later or use a different video."
        )
    except TranscriptError:
        raise
    except Exception as e:
        raise TranscriptError(
            f"An unexpected error occurred while fetching the transcript: {str(e)}"
        )
