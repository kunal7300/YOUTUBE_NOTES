"""
main.py – FastAPI v3 — All endpoints.
"""

import json
import re
import asyncio

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from dependencies import get_settings
from transcript import fetch_transcript, TranscriptError, fetch_transcript_debug
from utils import count_tokens, split_transcript_into_chunks, format_segments_as_timestamped_text
from llm import stream_notes, call_llm, QUIZ_PROMPT, FLASHCARD_PROMPT, SUMMARY_PROMPT
from sse import token_to_sse, error_sse
from auth import get_current_user
import db
import rag

# ── App setup ────────────────────────────────────────────────────────────────

settings = get_settings()
app = FastAPI(title="YT Notes + RAG", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    url: str
    language: str = "hinglish"  # english | hindi | hinglish
    model: Optional[str] = None  # Groq free model override
    transcript_text: Optional[str] = None  # Pre-fetched transcript from client

class StoreNotesRequest(BaseModel):
    youtube_url: str
    title: str
    notes_text: str
    language: str = "hinglish"
    tags: list[str] = []

class ChatRequest(BaseModel):
    note_id: str
    question: str

class UpdateTagsRequest(BaseModel):
    tags: list[str]

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.1.0"}

@app.get("/debug-transcript")
async def debug_transcript(url: str = Query(...)):
    """Diagnostic endpoint: test all 4 transcript layers and report results."""
    return fetch_transcript_debug(url)

# ── Generate Notes (public) ───────────────────────────────────────────────────

@app.post("/generate-notes")
async def generate_notes(body: GenerateRequest):
    async def _pipeline():
        # If client sent pre-fetched transcript, use it directly
        if body.transcript_text and body.transcript_text.strip():
            transcript_text = body.transcript_text.strip()
        else:
            try:
                result = fetch_transcript(body.url)
            except TranscriptError as e:
                async for event in error_sse(e.user_message): yield event
                return
            except Exception as e:
                async for event in error_sse(f"Unexpected error: {str(e)}"): yield event
                return
            transcript_text = format_segments_as_timestamped_text(result.segments)

        current_settings = get_settings()
        max_tokens = current_settings["max_transcript_tokens"]
        total_tokens = count_tokens(transcript_text)
        is_chunked = total_tokens > max_tokens

        chunks = (
            split_transcript_into_chunks(transcript_text, [], max_tokens=max_tokens)
            if is_chunked else [transcript_text]
        )

        try:
            token_gen = stream_notes(chunks, is_chunked=is_chunked, language=body.language, model=body.model)
            async for event in token_to_sse(token_gen):
                yield event
        except Exception as e:
            async for event in error_sse(f"Error during generation: {str(e)}"): yield event

    return StreamingResponse(_pipeline(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── Store Notes + Embed ───────────────────────────────────────────────────────

@app.post("/store-notes")
async def store_notes(body: StoreNotesRequest, user: dict = Depends(get_current_user)):
    token = user["token"]
    try:
        # 1. Save note to DB immediately
        note = db.save_note(
            user_id=user["user_id"], youtube_url=body.youtube_url,
            title=body.title, content=body.notes_text,
            tags=body.tags, language=body.language, token=token,
        )
        note_id = note["id"]

        # 2. Run embedding in background — don't block the response
        async def _embed_bg():
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, rag.embed_and_store, note_id, body.notes_text, token)
            except Exception as e:
                print(f"[embed_bg] Warning: embedding failed for {note_id}: {e}")

        asyncio.create_task(_embed_bg())

        # 3. Return right away — chat works even before embedding finishes
        return {
            "note_id": note_id,
            "title": body.title,
            "message": "Saved! Indexing in background…",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store notes: {str(e)}")

# ── RAG Chat ──────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(body: ChatRequest, user: dict = Depends(get_current_user)):
    token = user["token"]
    note = db.get_note_by_id(body.note_id, user["user_id"], token)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    async def _pipeline():
        full_answer = []
        try:
            async for tok in rag.stream_rag_answer(body.note_id, body.question, token):
                full_answer.append(tok)
                yield f"data: {json.dumps({'token': tok})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
        try:
            db.save_message(body.note_id, user["user_id"], "user", body.question, token)
            db.save_message(body.note_id, user["user_id"], "assistant", "".join(full_answer), token)
        except Exception:
            pass
        yield "data: [DONE]\n\n"

    return StreamingResponse(_pipeline(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── My Notes ─────────────────────────────────────────────────────────────────

@app.get("/my-notes")
async def my_notes(user: dict = Depends(get_current_user)):
    notes = db.get_user_notes(user["user_id"], user["token"])
    return {"notes": notes}

@app.get("/my-notes/{note_id}")
async def get_note(note_id: str, user: dict = Depends(get_current_user)):
    note = db.get_note_by_id(note_id, user["user_id"], user["token"])
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    return note

@app.delete("/my-notes/{note_id}")
async def delete_note(note_id: str, user: dict = Depends(get_current_user)):
    token = user["token"]
    note = db.get_note_by_id(note_id, user["user_id"], token)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    db.delete_note(note_id, user["user_id"], token)
    return {"message": "Deleted."}

# ── Search Notes ──────────────────────────────────────────────────────────────

@app.get("/search-notes")
async def search_notes(q: str = Query(..., min_length=1), user: dict = Depends(get_current_user)):
    results = db.search_notes(user["user_id"], q, user["token"])
    return {"results": results}

# ── Tags ──────────────────────────────────────────────────────────────────────

@app.put("/tags/{note_id}")
async def update_tags(note_id: str, body: UpdateTagsRequest, user: dict = Depends(get_current_user)):
    token = user["token"]
    note = db.get_note_by_id(note_id, user["user_id"], token)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    db.update_tags(note_id, user["user_id"], body.tags, token)
    return {"tags": body.tags}

# ── Quiz (per-topic 3-4 questions) ────────────────────────────────────────────

@app.get("/quiz/{note_id}")
async def get_quiz(note_id: str, user: dict = Depends(get_current_user)):
    note = db.get_note_by_id(note_id, user["user_id"], user["token"])
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    
    content = note["content"][:4000]
    prompt = QUIZ_PROMPT.format(notes=content)
    try:
        raw = await call_llm(prompt, json_mode=True)
        clean = re.sub(r"```json?\s*|\s*```", "", raw).strip()
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start == -1:
            raise ValueError("No JSON found in response")
        data = json.loads(clean[start:end])
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")

# ── Flashcards ────────────────────────────────────────────────────────────────

@app.get("/flashcards/{note_id}")
async def get_flashcards(note_id: str, user: dict = Depends(get_current_user)):
    note = db.get_note_by_id(note_id, user["user_id"], user["token"])
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    
    content = note["content"][:4000]
    prompt = FLASHCARD_PROMPT.format(notes=content)
    try:
        raw = await call_llm(prompt, json_mode=True)
        clean = re.sub(r"```json?\s*|\s*```", "", raw).strip()
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start == -1:
            raise ValueError("No JSON found in response")
        data = json.loads(clean[start:end])
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flashcard generation failed: {str(e)}")

# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/summary/{note_id}")
async def get_summary(note_id: str, user: dict = Depends(get_current_user)):
    note = db.get_note_by_id(note_id, user["user_id"], user["token"])
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    
    content = note["content"][:4000]
    prompt = SUMMARY_PROMPT.format(notes=content)
    try:
        summary = await call_llm(prompt, json_mode=False)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")

# ── Share Note ────────────────────────────────────────────────────────────────

@app.post("/share/{note_id}")
async def share_note(note_id: str, user: dict = Depends(get_current_user)):
    token = user["token"]
    note = db.get_note_by_id(note_id, user["user_id"], token)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    share_id = db.make_note_public(note_id, user["user_id"], token)
    return {"share_id": share_id, "share_url": f"/shared/{share_id}"}

@app.get("/shared/{share_id}")
@app.get("/public/note/{share_id}")
async def public_note(share_id: str):
    note = db.get_public_note(share_id)
    if not note:
        raise HTTPException(status_code=404, detail="Shared note not found or expired.")
    return note

# ── Chat History ──────────────────────────────────────────────────────────────

@app.get("/chat-history/{note_id}")
async def chat_history(note_id: str, user: dict = Depends(get_current_user)):
    token = user["token"]
    note = db.get_note_by_id(note_id, user["user_id"], token)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    messages = db.get_chat_history(note_id, user["user_id"], token)
    return {"messages": messages}
