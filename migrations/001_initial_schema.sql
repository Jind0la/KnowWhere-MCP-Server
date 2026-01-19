-- =============================================================================
-- Knowwhere Memory MCP Server - Initial Database Schema
-- Version: 1.0.0
-- PostgreSQL 14+ with pgvector extension
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- USERS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Authentication
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    auth_provider VARCHAR(50) DEFAULT 'email',
    password_hash VARCHAR(255),
    
    -- Profile
    username VARCHAR(100) UNIQUE,
    full_name VARCHAR(255),
    avatar_url VARCHAR(500),
    bio TEXT,
    
    -- Subscription & Plan
    tier VARCHAR(50) DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    monthly_quota_requests INT DEFAULT 100000,
    monthly_quota_storage_bytes BIGINT DEFAULT 1073741824,
    
    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    suspended_at TIMESTAMPTZ,
    suspension_reason TEXT,
    
    -- Metadata
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_users_tier ON users(tier);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- =============================================================================
-- MEMORIES TABLE (Core Entity)
-- =============================================================================

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Content
    content TEXT NOT NULL,
    content_preview VARCHAR(500),
    
    -- Vector Embedding (pgvector - 1408 dimensions for text-embedding-3-large)
    embedding vector(1408) NOT NULL,
    
    -- Classification
    memory_type VARCHAR(50) NOT NULL CHECK (
        memory_type IN ('episodic', 'semantic', 'preference', 'procedural', 'meta')
    ),
    
    -- Entities & Tags
    entities JSONB DEFAULT '[]',
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Scoring
    importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
    confidence FLOAT DEFAULT 0.8 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    
    -- Status & Lifecycle
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    superseded_by UUID REFERENCES memories(id) ON DELETE SET NULL,
    
    -- Source Tracking
    source VARCHAR(50) DEFAULT 'conversation' CHECK (
        source IN ('conversation', 'document', 'import', 'manual', 'consolidation')
    ),
    source_id VARCHAR(255),
    conversation_id VARCHAR(255),
    
    -- Access Tracking
    access_count INT DEFAULT 0,
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_user_status ON memories(user_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(user_id, importance DESC) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(user_id, last_accessed DESC) WHERE status = 'active';

-- Vector similarity index (HNSW for best recall)
CREATE INDEX IF NOT EXISTS idx_memories_embedding_hnsw ON memories 
    USING hnsw (embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64);

-- Entity search
CREATE INDEX IF NOT EXISTS idx_memories_entities ON memories USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING GIN(tags);

-- Soft delete tracking
CREATE INDEX IF NOT EXISTS idx_memories_deleted ON memories(user_id, deleted_at) WHERE deleted_at IS NOT NULL;

-- =============================================================================
-- KNOWLEDGE EDGES TABLE (Graph Relationships)
-- =============================================================================

CREATE TABLE IF NOT EXISTS knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Graph Relationship
    from_node_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    to_node_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    
    -- Edge Characteristics
    edge_type VARCHAR(50) NOT NULL CHECK (
        edge_type IN ('leads_to', 'related_to', 'contradicts', 'supports', 'likes', 'dislikes', 'depends_on', 'evolves_into')
    ),
    strength FLOAT DEFAULT 0.7 CHECK (strength >= 0.0 AND strength <= 1.0),
    confidence FLOAT DEFAULT 0.8 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    
    -- Semantics
    causality BOOLEAN DEFAULT FALSE,
    bidirectional BOOLEAN DEFAULT FALSE,
    reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT no_self_reference CHECK (from_node_id != to_node_id)
);

-- Unique constraint on user + from + to + type
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_user_from_to ON knowledge_edges(user_id, from_node_id, to_node_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_from_node ON knowledge_edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_to_node ON knowledge_edges(to_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_user_type ON knowledge_edges(user_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_strength ON knowledge_edges(user_id, strength DESC) WHERE strength > 0.7;

-- =============================================================================
-- CONSOLIDATION HISTORY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS consolidation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Session Info
    consolidation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    session_id VARCHAR(255),
    conversation_id VARCHAR(255),
    
    -- Processing Stats
    session_transcript_length INT DEFAULT 0,
    claims_extracted INT DEFAULT 0,
    memories_processed INT DEFAULT 0,
    new_memories_created INT DEFAULT 0,
    merged_count INT DEFAULT 0,
    conflicts_resolved INT DEFAULT 0,
    edges_created INT DEFAULT 0,
    
    -- Performance
    processing_time_ms INT DEFAULT 0,
    tokens_used INT DEFAULT 0,
    embedding_cost_usd FLOAT DEFAULT 0.0,
    
    -- Quality Metrics
    duplicate_similarity_threshold FLOAT DEFAULT 0.85,
    conflict_similarity_range VARCHAR(50) DEFAULT '0.5-0.85',
    
    -- Analysis
    patterns_detected JSONB DEFAULT '[]',
    key_entities JSONB DEFAULT '[]',
    sentiment_analysis JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(50) DEFAULT 'completed' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_consolidation_user_date ON consolidation_history(user_id, consolidation_date DESC);
CREATE INDEX IF NOT EXISTS idx_consolidation_status ON consolidation_history(status) WHERE status != 'completed';

-- =============================================================================
-- FILES TABLE (Document Uploads)
-- =============================================================================

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- File Metadata
    filename VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    file_type VARCHAR(100),
    mime_type VARCHAR(100),
    
    -- Storage
    storage_path VARCHAR(1000) NOT NULL,
    storage_provider VARCHAR(50) DEFAULT 's3' CHECK (storage_provider IN ('s3', 'r2', 'gcs')),
    
    -- Processing
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (
        processing_status IN ('pending', 'processing', 'completed', 'failed')
    ),
    processed_at TIMESTAMPTZ,
    
    -- Chunks
    total_chunks INT DEFAULT 0,
    chunks_processed INT DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    extraction_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON files(processing_status) WHERE processing_status != 'completed';
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(user_id, created_at DESC);

-- =============================================================================
-- DOCUMENT CHUNKS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Content
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    start_page INT,
    end_page INT,
    
    -- Embedding
    embedding vector(1408),
    embedding_generated BOOLEAN DEFAULT FALSE,
    
    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON document_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON document_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks 
    USING hnsw (embedding vector_cosine_ops) 
    WHERE embedding IS NOT NULL AND status = 'active';

-- =============================================================================
-- API KEYS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Key Details
    key_prefix VARCHAR(20) NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_secret_hash VARCHAR(255),
    
    -- Permissions
    scopes TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Usage
    rate_limit_requests_per_minute INT DEFAULT 1000,
    last_used_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
    expires_at TIMESTAMPTZ,
    
    -- Metadata
    name VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status) WHERE status = 'active';

-- =============================================================================
-- ACCESS LOGS TABLE (Audit Trail)
-- =============================================================================

CREATE TABLE IF NOT EXISTS access_logs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Context
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    request_id VARCHAR(36),
    
    -- Operation
    operation VARCHAR(100),
    endpoint VARCHAR(255),
    
    -- Request Details
    request_payload JSONB,
    response_status INT,
    response_time_ms INT,
    
    -- Resources
    accessed_memory_ids UUID[],
    accessed_file_ids UUID[],
    
    -- Client Info
    user_agent VARCHAR(500),
    ip_address INET,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_access_logs_user_date ON access_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_operation ON access_logs(operation, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_status ON access_logs(response_status);

-- =============================================================================
-- TRIGGER FUNCTIONS
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_memories_updated_at ON memories;
CREATE TRIGGER update_memories_updated_at BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_knowledge_edges_updated_at ON knowledge_edges;
CREATE TRIGGER update_knowledge_edges_updated_at BEFORE UPDATE ON knowledge_edges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_files_updated_at ON files;
CREATE TRIGGER update_files_updated_at BEFORE UPDATE ON files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-generate content preview
CREATE OR REPLACE FUNCTION generate_content_preview()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_preview = LEFT(NEW.content, 500);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS generate_memory_preview ON memories;
CREATE TRIGGER generate_memory_preview BEFORE INSERT OR UPDATE OF content ON memories
    FOR EACH ROW EXECUTE FUNCTION generate_content_preview();

-- =============================================================================
-- ROW LEVEL SECURITY (Optional - enable if using Supabase Auth)
-- =============================================================================

-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE knowledge_edges ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE consolidation_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE files ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE access_logs ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Search memories by vector similarity
CREATE OR REPLACE FUNCTION search_memories_by_vector(
    p_user_id UUID,
    p_embedding vector(1408),
    p_limit INT DEFAULT 10,
    p_memory_type VARCHAR DEFAULT NULL,
    p_min_importance INT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    memory_type VARCHAR,
    importance INT,
    similarity FLOAT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.content,
        m.memory_type,
        m.importance,
        (1 - (m.embedding <=> p_embedding))::FLOAT AS similarity,
        m.created_at
    FROM memories m
    WHERE m.user_id = p_user_id 
        AND m.status = 'active'
        AND (p_memory_type IS NULL OR m.memory_type = p_memory_type)
        AND (p_min_importance IS NULL OR m.importance >= p_min_importance)
    ORDER BY m.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Get related memories via knowledge graph
CREATE OR REPLACE FUNCTION get_related_memories(
    p_memory_id UUID,
    p_user_id UUID,
    p_depth INT DEFAULT 1
)
RETURNS TABLE (
    memory_id UUID,
    content TEXT,
    edge_type VARCHAR,
    strength FLOAT,
    depth INT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE related AS (
        -- Base case: direct connections
        SELECT 
            CASE WHEN e.from_node_id = p_memory_id THEN e.to_node_id ELSE e.from_node_id END AS memory_id,
            e.edge_type,
            e.strength,
            1 AS depth
        FROM knowledge_edges e
        WHERE e.user_id = p_user_id
            AND (e.from_node_id = p_memory_id OR (e.bidirectional AND e.to_node_id = p_memory_id))
        
        UNION
        
        -- Recursive case
        SELECT 
            CASE WHEN e.from_node_id = r.memory_id THEN e.to_node_id ELSE e.from_node_id END,
            e.edge_type,
            e.strength,
            r.depth + 1
        FROM knowledge_edges e
        INNER JOIN related r ON (e.from_node_id = r.memory_id OR (e.bidirectional AND e.to_node_id = r.memory_id))
        WHERE e.user_id = p_user_id AND r.depth < p_depth
    )
    SELECT r.memory_id, m.content, r.edge_type, r.strength, r.depth
    FROM related r
    INNER JOIN memories m ON m.id = r.memory_id
    WHERE m.status = 'active';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- INITIAL DATA (Optional)
-- =============================================================================

-- You can uncomment and modify this to create a test user
-- INSERT INTO users (email, email_verified, tier) 
-- VALUES ('test@knowwhere.ai', true, 'pro')
-- ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- SCHEMA VERSION TRACKING
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO schema_migrations (version) VALUES ('001_initial_schema')
ON CONFLICT (version) DO NOTHING;

-- Done!
-- Run: psql -h your-host -U postgres -d your-db -f 001_initial_schema.sql
