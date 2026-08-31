"""
db.py — Supabase client + helper functions for notes, chunks, and chat messages.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_supabase: Client | None = None
_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def get_supabase() -> Client:
    """Return a singleton Supabase client (anon key — for auth verification only)."""
    global _supabase
    if _supabase is None:
        if not _SUPABASE_URL or not _SUPABASE_ANON_KEY:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)
    return _supabase


def get_user_supabase(access_token: str) -> Client:
    """
    Return a Supabase client with the user's JWT set on PostgREST.
    This makes auth.uid() resolve correctly so RLS policies work server-side.
    """
    client = create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)
    # Set the user JWT so PostgREST uses it for auth.uid()
    client.postgrest.auth(access_token)
    return client


# ── Notes ────────────────────────────────────────────────────────────────────

def save_note(user_id: str, youtube_url: str, title: str, content: str,
              token: str, tags: list = None, language: str = "hinglish") -> dict:
    """Insert a new note and return the created row."""
    sb = get_user_supabase(token)
    result = (
        sb.table("notes")
        .insert({
            "user_id": user_id,
            "youtube_url": youtube_url,
            "title": title,
            "content": content,
            "tags": tags or [],
            "language": language,
        })
        .execute()
    )
    return result.data[0]


def get_user_notes(user_id: str, token: str) -> list[dict]:
    """Return all notes for the given user (newest first)."""
    sb = get_user_supabase(token)
    result = (
        sb.table("notes")
        .select("id, title, youtube_url, created_at, tags, language")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def get_note_by_id(note_id: str, user_id: str, token: str) -> dict | None:
    """Return a single note if it belongs to the user."""
    sb = get_user_supabase(token)
    try:
        result = (
            sb.table("notes")
            .select("*")
            .eq("id", note_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def delete_note(note_id: str, user_id: str, token: str) -> bool:
    """Delete a note if it belongs to the user."""
    sb = get_user_supabase(token)
    sb.table("notes").delete().eq("id", note_id).eq("user_id", user_id).execute()
    return True


def search_notes(user_id: str, query: str, token: str) -> list[dict]:
    """Full-text search across title and content."""
    sb = get_user_supabase(token)
    q = f"%{query}%"
    result = (
        sb.table("notes")
        .select("id, title, youtube_url, created_at, tags")
        .eq("user_id", user_id)
        .or_(f"title.ilike.{q},content.ilike.{q}")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def update_tags(note_id: str, user_id: str, tags: list, token: str) -> None:
    """Update tags on a note."""
    sb = get_user_supabase(token)
    sb.table("notes").update({"tags": tags}).eq("id", note_id).eq("user_id", user_id).execute()


def make_note_public(note_id: str, user_id: str, token: str) -> str:
    """Make a note public and return the share_id."""
    import uuid
    share_id = str(uuid.uuid4())
    sb = get_user_supabase(token)
    sb.table("notes").update({
        "is_public": True,
        "share_id": share_id,
    }).eq("id", note_id).eq("user_id", user_id).execute()
    return share_id


def get_public_note(share_id: str) -> dict | None:
    """Return a publicly shared note by share_id (no auth required)."""
    sb = get_supabase()
    try:
        result = (
            sb.table("notes")
            .select("id, title, youtube_url, content, created_at, tags")
            .eq("share_id", share_id)
            .eq("is_public", True)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


# ── Note Chunks (for RAG) ────────────────────────────────────────────────────

def save_chunks(note_id: str, chunks: list[dict], token: str) -> None:
    """Insert note chunks with their embeddings."""
    sb = get_user_supabase(token)
    rows = [
        {
            "note_id": note_id,
            "chunk_text": c["chunk_text"],
            "embedding": c["embedding"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]
    sb.table("note_chunks").insert(rows).execute()


def search_similar_chunks(note_id: str, query_embedding: list[float], token: str, top_k: int = 3) -> list[str]:
    """Use pgvector cosine similarity to find the top_k most relevant chunks."""
    sb = get_user_supabase(token)
    result = sb.rpc(
        "match_note_chunks",
        {"p_note_id": note_id, "query_embedding": query_embedding, "match_count": top_k},
    ).execute()
    return [row["chunk_text"] for row in result.data]


# ── Chat Messages ────────────────────────────────────────────────────────────

def save_message(note_id: str, user_id: str, role: str, content: str, token: str) -> None:
    """Save a single chat message."""
    sb = get_user_supabase(token)
    sb.table("chat_messages").insert({
        "note_id": note_id, "user_id": user_id, "role": role, "content": content,
    }).execute()


def get_chat_history(note_id: str, user_id: str, token: str) -> list[dict]:
    """Return all chat messages for a note (oldest first)."""
    sb = get_user_supabase(token)
    result = (
        sb.table("chat_messages")
        .select("role, content, created_at")
        .eq("note_id", note_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return result.data

