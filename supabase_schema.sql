-- Safe re-run version — drops existing policies before recreating
-- Run this in: Supabase Dashboard → SQL Editor → New Query

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Tables (IF NOT EXISTS — safe to re-run) ──────────────────
CREATE TABLE IF NOT EXISTS notes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users NOT NULL,
  title       TEXT,
  youtube_url TEXT,
  content     TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS note_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  note_id     UUID REFERENCES notes ON DELETE CASCADE,
  chunk_text  TEXT,
  embedding   VECTOR(384),
  chunk_index INT
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  note_id    UUID REFERENCES notes ON DELETE CASCADE,
  user_id    UUID REFERENCES auth.users NOT NULL,
  role       TEXT CHECK (role IN ('user', 'assistant')),
  content    TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Enable RLS ────────────────────────────────────────────────
ALTER TABLE notes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE note_chunks   ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- ── Drop old policies (safe) then recreate ────────────────────
DROP POLICY IF EXISTS "users_own_notes"    ON notes;
DROP POLICY IF EXISTS "users_own_chunks"   ON note_chunks;
DROP POLICY IF EXISTS "users_own_messages" ON chat_messages;

CREATE POLICY "users_own_notes"
  ON notes FOR ALL
  USING (auth.uid() = user_id);

CREATE POLICY "users_own_chunks"
  ON note_chunks FOR ALL
  USING (note_id IN (SELECT id FROM notes WHERE user_id = auth.uid()));

CREATE POLICY "users_own_messages"
  ON chat_messages FOR ALL
  USING (auth.uid() = user_id);

-- ── Vector index ──────────────────────────────────────────────
DROP INDEX IF EXISTS note_chunks_embedding_idx;
CREATE INDEX note_chunks_embedding_idx
  ON note_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- ── Similarity search function ────────────────────────────────
CREATE OR REPLACE FUNCTION match_note_chunks(
  p_note_id       UUID,
  query_embedding VECTOR(384),
  match_count     INT DEFAULT 3
)
RETURNS TABLE (chunk_text TEXT, similarity FLOAT)
LANGUAGE sql STABLE
AS $$
  SELECT
    nc.chunk_text,
    1 - (nc.embedding <=> query_embedding) AS similarity
  FROM note_chunks nc
  WHERE nc.note_id = p_note_id
  ORDER BY nc.embedding <=> query_embedding
  LIMIT match_count;
$$;
