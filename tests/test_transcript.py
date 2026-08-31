"""
tests/test_transcript.py – Unit tests for transcript.py
Run with: pytest tests/test_transcript.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from unittest.mock import patch, MagicMock
from transcript import fetch_transcript, TranscriptError, _extract_video_id


# ─── _extract_video_id ────────────────────────────────────────────────────────

class TestExtractVideoId:
    def test_standard_watch_url(self):
        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert _extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self):
        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(TranscriptError):
            _extract_video_id("https://example.com/not-a-youtube-url")


# ─── Helpers ──────────────────────────────────────────────────────────────────

MOCK_SEGMENTS = [
    {"text": "Hello world.", "start": 0.0, "duration": 2.5},
    {"text": "This is a test.", "start": 2.5, "duration": 3.0},
]


def _make_mock_transcript(segments=None, language_code="en"):
    """Build a mock Transcript object matching the v1.x API."""
    mock = MagicMock()
    mock.fetch.return_value = segments or MOCK_SEGMENTS
    mock.language_code = language_code
    return mock


def _make_mock_transcript_list(transcript):
    """Build a mock TranscriptList that returns the given transcript."""
    mock_list = MagicMock()
    mock_list.find_manually_created_transcript.return_value = transcript
    mock_list.__iter__ = MagicMock(return_value=iter([transcript]))
    return mock_list


# ─── fetch_transcript ─────────────────────────────────────────────────────────

class TestFetchTranscript:
    @patch("transcript.YouTubeTranscriptApi")
    def test_success(self, MockApi):
        """Instance-based: YouTubeTranscriptApi().list(video_id)"""
        transcript = _make_mock_transcript()
        mock_instance = MagicMock()
        mock_instance.list.return_value = _make_mock_transcript_list(transcript)
        MockApi.return_value = mock_instance

        result = fetch_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.video_id == "dQw4w9WgXcQ"
        assert "Hello world." in result.transcript_text
        assert result.language == "en"

    @patch("transcript.YouTubeTranscriptApi")
    def test_transcripts_disabled(self, MockApi):
        from youtube_transcript_api._errors import TranscriptsDisabled
        mock_instance = MagicMock()
        mock_instance.list.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")
        MockApi.return_value = mock_instance

        with pytest.raises(TranscriptError) as exc_info:
            fetch_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "disabled" in exc_info.value.user_message.lower()

    @patch("transcript.YouTubeTranscriptApi")
    def test_no_transcript_found(self, MockApi):
        from youtube_transcript_api._errors import NoTranscriptFound
        mock_instance = MagicMock()
        mock_instance.list.side_effect = NoTranscriptFound("dQw4w9WgXcQ", [], {})
        MockApi.return_value = mock_instance

        with pytest.raises(TranscriptError) as exc_info:
            fetch_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "no transcript" in exc_info.value.user_message.lower()

    @patch("transcript.YouTubeTranscriptApi")
    def test_video_unavailable(self, MockApi):
        from youtube_transcript_api._errors import VideoUnavailable
        mock_instance = MagicMock()
        mock_instance.list.side_effect = VideoUnavailable("dQw4w9WgXcQ")
        MockApi.return_value = mock_instance

        with pytest.raises(TranscriptError) as exc_info:
            fetch_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "unavailable" in exc_info.value.user_message.lower()
