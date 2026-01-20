-- Migration: Add DRAFT status to memories
-- Author: Antigravity
-- Date: 2026-01-20

-- 1. Drop the old check constraint
ALTER TABLE memories DROP CONSTRAINT IF EXISTS memories_status_check;

-- 2. Add the new check constraint including 'draft', 'superseded'
ALTER TABLE memories ADD CONSTRAINT memories_status_check 
CHECK (status IN ('active', 'draft', 'archived', 'deleted', 'superseded'));

-- 3. Update version tracking
INSERT INTO schema_migrations (version) VALUES ('005_add_draft_status')
ON CONFLICT (version) DO NOTHING;
