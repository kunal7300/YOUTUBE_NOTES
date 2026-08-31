"""
tests/test_llm.py – Unit tests for llm.py streaming behavior.
Run with: pytest tests/test_llm.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from llm import stream_notes


async def _collect(async_gen):
    """Collect all yielded values from an async generator."""
    result = []
    async for item in async_gen:
        result.append(item)
    return result


class TestStreamNotes:
    @pytest.mark.asyncio
    @patch("llm.get_settings")
    @patch("llm._stream_openai")
    async def test_single_chunk_openai(self, mock_stream, mock_settings):
        mock_settings.return_value = {
            "provider": "openai",
            "openai_api_key": "test",
            "openai_model": "gpt-4o-mini",
        }

        async def fake_stream(prompt, settings):
            for token in ["## Topic\n", "- bullet one\n", "- bullet two\n"]:
                yield token

        mock_stream.side_effect = fake_stream

        tokens = await _collect(stream_notes(["transcript text"], is_chunked=False))
        assert "## Topic\n" in tokens
        assert "- bullet one\n" in tokens

    @pytest.mark.asyncio
    @patch("llm.get_settings")
    @patch("llm._stream_openai")
    async def test_multi_chunk_inserts_separator(self, mock_stream, mock_settings):
        mock_settings.return_value = {
            "provider": "openai",
            "openai_api_key": "test",
            "openai_model": "gpt-4o-mini",
        }

        async def fake_stream(prompt, settings):
            yield "Part content\n"

        mock_stream.side_effect = fake_stream

        tokens = await _collect(stream_notes(["chunk1", "chunk2"], is_chunked=True))
        full = "".join(tokens)
        # Should contain the separator between chunks
        assert "---" in full

    @pytest.mark.asyncio
    @patch("llm.get_settings")
    @patch("llm._stream_anthropic")
    async def test_single_chunk_anthropic(self, mock_stream, mock_settings):
        mock_settings.return_value = {
            "provider": "anthropic",
            "anthropic_api_key": "test",
            "anthropic_model": "claude-3-5-sonnet-20240620",
        }

        async def fake_stream(prompt, settings):
            yield "## Anthropic Notes\n"

        mock_stream.side_effect = fake_stream

        tokens = await _collect(stream_notes(["transcript text"], is_chunked=False))
        assert "## Anthropic Notes\n" in tokens
