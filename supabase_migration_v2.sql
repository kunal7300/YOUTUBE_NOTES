-- Run this in Supabase SQL Editor to add new columns for tags, sharing, and language

ALTER TABLE notes ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
ALTER TABLE notes ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'hinglish';
ALTER TABLE notes ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false;
ALTER TABLE notes ADD COLUMN IF NOT EXISTS share_id UUID;

CREATE INDEX IF NOT EXISTS notes_share_id_idx ON notes(share_id) WHERE share_id IS NOT NULL;

-- Allow public read of shared notes (no auth required)
DROP POLICY IF EXISTS "public_shared_notes" ON notes;
CREATE POLICY "public_shared_notes"
  ON notes FOR SELECT
  USING (is_public = true AND share_id IS NOT NULL);
