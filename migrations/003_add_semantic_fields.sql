-- Migration: Add semantic hierarchy fields to memories table

ALTER TABLE memories
ADD COLUMN IF NOT EXISTS domain TEXT,
ADD COLUMN IF NOT EXISTS category TEXT;

-- Create index for faster filtering/clustering
CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);

COMMENT ON COLUMN memories.domain IS 'High-level project or domain (e.g. Knowwhere, Personal)';
COMMENT ON COLUMN memories.category IS 'Functional category or topic (e.g. Backend, Auth)';
