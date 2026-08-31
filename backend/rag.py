"""
rag.py — RAG pipeline: embed text, store chunks, retrieve relevant context.
Uses sentence-transformers (local, free) for embeddings.
Uses Supabase pgvector for similarity search.
"""

from __future__ import annotations
import os
from typing import AsyncGenerator
from db import save_chunks, search_similar_chunks
from dependencies import get_settings

# Model is loaded lazily on first use (avoids slow startup)
_model = None
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # lazy import
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_text(text: str) -> list[float]:
    """Return a 384-dim embedding vector for the given text."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


# ── Chunking ─────────────────────────────────────────────────────────────────

def _chunk_notes(notes_text: str, max_chars: int = 800) -> list[str]:
    """
    Split notes into overlapping chunks for embedding.
    Splits on double newlines (section boundaries) first.
    """
    # Split on markdown section boundaries
    sections = [s.strip() for s in notes_text.split("\n\n") if s.strip()]
    chunks: list[str] = []
    current = ""

    for section in sections:
        if len(current) + len(section) + 2 <= max_chars:
            current = (current + "\n\n" + section).strip()
        else:
            if current:
                chunks.append(current)
            # If single section > max_chars, hard split
            if len(section) > max_chars:
                words = section.split()
                buf = ""
                for word in words:
                    if len(buf) + len(word) + 1 <= max_chars:
                        buf = (buf + " " + word).strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = word
                if buf:
                    chunks.append(buf)
            else:
                current = section

    if current:
        chunks.append(current)

    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def embed_and_store(note_id: str, notes_text: str, token: str) -> int:
    """
    Chunk the notes, embed each chunk, and store in Supabase pgvector.
    Returns the number of chunks stored.
    """
    chunks = _chunk_notes(notes_text)
    rows = []
    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        rows.append({
            "chunk_text": chunk,
            "embedding": embedding,
            "chunk_index": i,
        })
    save_chunks(note_id, rows, token)
    return len(chunks)


def retrieve_context(note_id: str, question: str, token: str, top_k: int = 3) -> list[str]:
    """
    Embed the question and retrieve the top_k most relevant note chunks.
    """
    query_embedding = embed_text(question)
    return search_similar_chunks(note_id, query_embedding, token, top_k=top_k)


# ── RAG Prompt Builder ────────────────────────────────────────────────────────

RAG_SYSTEM_PROMPT = (
    "You are a helpful study assistant. Answer questions based ONLY on the provided notes context. "
    "Use English + Hinglish. Be concise and accurate. "
    "If the answer is not in the notes, say 'Yeh notes mein nahi hai'."
)

def build_rag_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks)
    return f"""Here are the relevant notes:

{context}

---

Question: {question}

Answer (based only on the notes above):"""


# ── Streaming RAG Chat ────────────────────────────────────────────────────────

async def stream_rag_answer(
    note_id: str,
    question: str,
    token: str,
) -> AsyncGenerator[str, None]:
    """
    Full RAG pipeline: retrieve context → build prompt → stream LLM answer.
    """
    settings = get_settings()
    provider = settings["provider"]

    # 1. Retrieve relevant chunks
    context_chunks = retrieve_context(note_id, question, token, top_k=3)
    if not context_chunks:
        yield "Notes mein koi relevant content nahi mila. Please try rephrasing your question."
        return

    # 2. Build prompt
    prompt = build_rag_prompt(question, context_chunks)

    # 3. Stream from LLM
    if provider == "groq":
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings["groq_api_key"])
        stream = await client.chat.completions.create(
            model=settings["groq_model"],
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": f"/no_think\n\n{prompt}"},
            ],
            stream=True,
            temperature=0.2,
            max_tokens=1024,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    elif provider == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings["openai_api_key"])
        stream = await client.chat.completions.create(
            model=settings["openai_model"],
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            temperature=0.2,
            max_tokens=1024,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    else:
        yield "RAG chat is currently only supported with Groq and OpenAI providers."
