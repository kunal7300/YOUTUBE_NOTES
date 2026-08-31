"""
tests/test_integration.py – Integration test using FastAPI TestClient.
Run with: pytest tests/test_integration.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import json
from unittest.mock import patch, MagicMock

# Set required env vars before importing app
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("CORS_ORIGIN", "http://localhost:5173")
os.environ.setdefault("MAX_TRANSCRIPT_TOKENS", "8000")


MOCK_SEGMENTS = [
    {"text": "Welcome to this lecture on Python.", "start": 0.0, "duration": 3.0},
    {"text": "Today we will cover functions and classes.", "start": 3.0, "duration": 3.5},
    {"text": "Let us start with functions.", "start": 6.5, "duration": 2.5},
]


def _make_mock_result():
    result = MagicMock()
    result.video_id = "testVideoId"
    result.transcript_text = "Welcome to this lecture on Python. Today we will cover functions."
    result.segments = MOCK_SEGMENTS
    result.language = "en"
    return result


def _parse_sse_body(body: str) -> list:
    """Parse SSE body into list of parsed JSON payloads."""
    payloads = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if raw == "[DONE]":
            payloads.append("[DONE]")
            continue
        try:
            payloads.append(json.loads(raw))
        except Exception:
            pass
    return payloads


class TestHealthEndpoint:
    def test_health(self):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestGenerateNotesEndpoint:
    @patch("main.fetch_transcript")
    @patch("main.stream_notes")
    def test_successful_streaming(self, mock_stream, mock_fetch):
        from fastapi.testclient import TestClient
        from main import app

        mock_fetch.return_value = _make_mock_result()

        async def fake_stream(chunks, is_chunked):
            for token in ["## Introduction\n", "- Key point one\n", "- Key point two\n"]:
                yield token

        mock_stream.side_effect = fake_stream

        client = TestClient(app, raise_server_exceptions=False)
        # Use stream=True to read SSE without blocking
        with client.stream(
            "POST",
            "/generate-notes",
            json={"url": "https://www.youtube.com/watch?v=testVideoId"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            body = response.read().decode()

        payloads = _parse_sse_body(body)
        tokens = [p["token"] for p in payloads if isinstance(p, dict) and "token" in p]
        full = "".join(tokens)
        assert "## Introduction" in full
        assert "[DONE]" in payloads

    @patch("main.fetch_transcript")
    def test_transcript_error_returns_sse_error(self, mock_fetch):
        from fastapi.testclient import TestClient
        from transcript import TranscriptError
        from main import app

        mock_fetch.side_effect = TranscriptError("This video is private.")

        client = TestClient(app, raise_server_exceptions=False)
        with client.stream(
            "POST",
            "/generate-notes",
            json={"url": "https://www.youtube.com/watch?v=privateVideo"},
        ) as response:
            assert response.status_code == 200
            body = response.read().decode()

        payloads = _parse_sse_body(body)
        errors = [p["error"] for p in payloads if isinstance(p, dict) and "error" in p]
        assert len(errors) > 0
        assert "private" in errors[0].lower()
