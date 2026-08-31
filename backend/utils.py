"""
utils.py – Token counting and transcript chunking helpers.
"""

import re
from typing import List

import tiktoken


# Use cl100k_base encoder (compatible with GPT-4, GPT-4o, and a good estimate for Claude)
_ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return the approximate token count for the given text."""
    return len(_ENCODER.encode(text))


def split_transcript_into_chunks(
    transcript_text: str,
    segments: List[dict],
    max_tokens: int = 1800,
    overlap_tokens: int = 100,
) -> List[str]:
    """
    Split a transcript into sequential chunks where each chunk's token count
    is strictly <= max_tokens. Robust to unpunctuated YouTube transcripts.
    """
    if count_tokens(transcript_text) <= max_tokens:
        return [transcript_text]

    # Split first by timestamped lines (\n), or by punctuation
    lines = [line.strip() for line in transcript_text.split("\n") if line.strip()]
    
    # Break lines into smaller units (sentences or word groups) if any line is too big
    units: List[str] = []
    for line in lines:
        if count_tokens(line) <= max_tokens:
            units.append(line)
        else:
            # Split line into sentence-like pieces or word blocks
            sub_sentences = _split_into_sentences(line)
            for s in sub_sentences:
                if count_tokens(s) <= max_tokens:
                    units.append(s)
                else:
                    # Hard word split for long unpunctuated text blocks
                    words = s.split()
                    buf = []
                    buf_tokens = 0
                    for word in words:
                        wt = count_tokens(word)
                        if buf_tokens + wt > max_tokens:
                            if buf:
                                units.append(" ".join(buf))
                            buf = [word]
                            buf_tokens = wt
                        else:
                            buf.append(word)
                            buf_tokens += wt
                    if buf:
                        units.append(" ".join(buf))

    # Now group units into sequential chunks <= max_tokens
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_tokens = 0

    for unit in units:
        ut = count_tokens(unit)
        if current_tokens + ut > max_tokens:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [unit]
            current_tokens = ut
        else:
            current_chunk.append(unit)
            current_tokens += ut

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks if chunks else [transcript_text]


def _split_into_sentences(text: str) -> List[str]:
    """Naive sentence splitter using punctuation."""
    # Split on . ! ? followed by whitespace
    raw = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in raw if s.strip()]


def _build_overlap(sentences: List[str], overlap_tokens: int) -> List[str]:
    """Return the tail sentences that fit within overlap_tokens."""
    buffer: List[str] = []
    tokens = 0
    for sentence in reversed(sentences):
        t = count_tokens(sentence)
        if tokens + t > overlap_tokens:
            break
        buffer.insert(0, sentence)
        tokens += t
    return buffer


def _try_flush(sentence: str, current_sentences: List[str], chunks: List[str],
               max_tokens: int, overlap_tokens: int) -> None:
    """Helper used in the hard-split path (not called in the main loop)."""
    current_sentences.append(sentence)


def format_segments_as_timestamped_text(segments: List[dict]) -> str:
    """
    Build a clean transcript string from segments WITHOUT timestamps.
    Timestamps are intentionally omitted so they don't leak into the LLM output notes.
    """
    lines = []
    block_texts: List[str] = []
    block_start: float = 0.0
    BLOCK_SECONDS = 30.0

    for i, seg in enumerate(segments):
        start = seg.get("start", 0.0)
        text = seg.get("text", "").strip()

        if i == 0:
            block_start = start

        if start - block_start >= BLOCK_SECONDS and block_texts:
            lines.append(" ".join(block_texts))
            block_texts = []
            block_start = start

        block_texts.append(text)

    if block_texts:
        lines.append(" ".join(block_texts))

    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS string."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
