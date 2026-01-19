-- =============================================================================
-- Knowwhere Memory MCP Server - Entity Hubs Migration
-- Version: 003
-- Zettelkasten-style entity management with self-learning dictionary
-- =============================================================================

-- =============================================================================
-- ENTITY HUBS TABLE (Zettelkasten Nodes)
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_hubs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Entity Identity
    entity_name VARCHAR(255) NOT NULL,           -- "Sarah" (normalized, lowercase)
    display_name VARCHAR(255),                   -- "Sarah" (original casing)
    canonical_name VARCHAR(500),                 -- "Sarah (Freundin)" (user-defined label)
    
    -- Zettelkasten Classification
    category VARCHAR(100),                        -- "Personal Contacts", "Rezepte", "Events"
    hub_type VARCHAR(50) DEFAULT 'concept' CHECK (
        hub_type IN ('person', 'place', 'event', 'recipe', 'concept', 'tech', 'project', 'organization')
    ),
    
    -- Learning Stats
    usage_count INT DEFAULT 1,
    memory_count INT DEFAULT 0,                   -- How many memories reference this
    last_used TIMESTAMPTZ DEFAULT NOW(),
    
    -- Aliases for fuzzy matching (e.g., ["Sara", "sarah's"])
    aliases TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Optional: Vector embedding for semantic entity matching
    embedding vector(1408),
    
    -- Source: how was this entity learned?
    source VARCHAR(50) DEFAULT 'llm' CHECK (
        source IN ('llm', 'user_defined', 'system', 'imported')
    ),
    
    -- Confidence in this entity classification
    confidence FLOAT DEFAULT 0.8 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique per user (normalized name)
    CONSTRAINT unique_user_entity UNIQUE (user_id, entity_name)
);

-- Indexes for entity_hubs
CREATE INDEX IF NOT EXISTS idx_entity_hubs_user ON entity_hubs(user_id);
CREATE INDEX IF NOT EXISTS idx_entity_hubs_user_type ON entity_hubs(user_id, hub_type);
CREATE INDEX IF NOT EXISTS idx_entity_hubs_user_category ON entity_hubs(user_id, category);
CREATE INDEX IF NOT EXISTS idx_entity_hubs_usage ON entity_hubs(user_id, usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_entity_hubs_memory_count ON entity_hubs(user_id, memory_count DESC);

-- Full-text search on entity names
CREATE INDEX IF NOT EXISTS idx_entity_hubs_name_trgm ON entity_hubs 
    USING gin(entity_name gin_trgm_ops);

-- Alias search
CREATE INDEX IF NOT EXISTS idx_entity_hubs_aliases ON entity_hubs USING gin(aliases);

-- Optional: Vector similarity search for entities
CREATE INDEX IF NOT EXISTS idx_entity_hubs_embedding ON entity_hubs 
    USING hnsw (embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

-- =============================================================================
-- MEMORY-ENTITY JUNCTION TABLE (Links memories to entity hubs)
-- =============================================================================

CREATE TABLE IF NOT EXISTS memory_entity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entity_hubs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Link Metadata
    strength FLOAT DEFAULT 1.0 CHECK (strength >= 0.0 AND strength <= 1.0),
    is_primary BOOLEAN DEFAULT FALSE,             -- Main entity of the memory
    mention_count INT DEFAULT 1,                  -- How many times mentioned in this memory
    
    -- Context: where in the memory is this entity?
    context_snippet VARCHAR(500),                 -- Surrounding text
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint
    CONSTRAINT unique_memory_entity UNIQUE (memory_id, entity_id)
);

-- Indexes for memory_entity_links
CREATE INDEX IF NOT EXISTS idx_mel_memory ON memory_entity_links(memory_id);
CREATE INDEX IF NOT EXISTS idx_mel_entity ON memory_entity_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_mel_user ON memory_entity_links(user_id);
CREATE INDEX IF NOT EXISTS idx_mel_primary ON memory_entity_links(entity_id, is_primary) 
    WHERE is_primary = TRUE;

-- =============================================================================
-- TRIGGER: Update entity usage stats
-- =============================================================================

CREATE OR REPLACE FUNCTION update_entity_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Increment usage count and memory count
        UPDATE entity_hubs 
        SET 
            usage_count = usage_count + 1,
            memory_count = memory_count + 1,
            last_used = NOW(),
            updated_at = NOW()
        WHERE id = NEW.entity_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        -- Decrement memory count
        UPDATE entity_hubs 
        SET 
            memory_count = GREATEST(0, memory_count - 1),
            updated_at = NOW()
        WHERE id = OLD.entity_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_entity_stats ON memory_entity_links;
CREATE TRIGGER trigger_update_entity_stats
    AFTER INSERT OR DELETE ON memory_entity_links
    FOR EACH ROW EXECUTE FUNCTION update_entity_stats();

-- =============================================================================
-- TRIGGER: Auto-update updated_at for entity_hubs
-- =============================================================================

DROP TRIGGER IF EXISTS update_entity_hubs_updated_at ON entity_hubs;
CREATE TRIGGER update_entity_hubs_updated_at 
    BEFORE UPDATE ON entity_hubs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTION: Find memories by entity
-- =============================================================================

CREATE OR REPLACE FUNCTION find_memories_by_entity(
    p_user_id UUID,
    p_entity_name VARCHAR,
    p_limit INT DEFAULT 20
)
RETURNS TABLE (
    memory_id UUID,
    content TEXT,
    memory_type VARCHAR,
    importance INT,
    link_strength FLOAT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.content,
        m.memory_type,
        m.importance,
        mel.strength,
        m.created_at
    FROM memory_entity_links mel
    INNER JOIN memories m ON m.id = mel.memory_id
    INNER JOIN entity_hubs eh ON eh.id = mel.entity_id
    WHERE eh.user_id = p_user_id 
        AND LOWER(eh.entity_name) = LOWER(p_entity_name)
        AND m.status = 'active'
    ORDER BY mel.is_primary DESC, mel.strength DESC, m.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- HELPER FUNCTION: Get related memories via shared entities
-- =============================================================================

CREATE OR REPLACE FUNCTION get_related_memories_via_entities(
    p_memory_id UUID,
    p_user_id UUID,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    memory_id UUID,
    content TEXT,
    shared_entity_count INT,
    shared_entities TEXT[],
    total_strength FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH source_entities AS (
        -- Get entities of the source memory
        SELECT entity_id FROM memory_entity_links WHERE memory_id = p_memory_id
    ),
    related AS (
        -- Find other memories that share these entities
        SELECT 
            mel.memory_id,
            COUNT(DISTINCT mel.entity_id)::INT AS shared_count,
            ARRAY_AGG(DISTINCT eh.display_name) AS entities,
            SUM(mel.strength) AS total_str
        FROM memory_entity_links mel
        INNER JOIN source_entities se ON se.entity_id = mel.entity_id
        INNER JOIN entity_hubs eh ON eh.id = mel.entity_id
        WHERE mel.memory_id != p_memory_id
            AND mel.user_id = p_user_id
        GROUP BY mel.memory_id
    )
    SELECT 
        r.memory_id,
        m.content,
        r.shared_count,
        r.entities,
        r.total_str
    FROM related r
    INNER JOIN memories m ON m.id = r.memory_id
    WHERE m.status = 'active'
    ORDER BY r.shared_count DESC, r.total_str DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SCHEMA VERSION
-- =============================================================================

INSERT INTO schema_migrations (version) VALUES ('003_entity_hubs')
ON CONFLICT (version) DO NOTHING;

-- Done!
