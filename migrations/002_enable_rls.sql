-- =============================================================================
-- Knowwhere Memory MCP Server - Row Level Security (RLS)
-- Version: 1.0.0
-- Enables data isolation at the database level
-- =============================================================================

-- =============================================================================
-- ENABLE RLS ON ALL USER-OWNED TABLES
-- =============================================================================

ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE consolidation_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- RLS POLICIES FOR MEMORIES
-- =============================================================================

-- Users can only see their own memories
CREATE POLICY memories_select_own ON memories
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Users can only insert their own memories
CREATE POLICY memories_insert_own ON memories
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

-- Users can only update their own memories
CREATE POLICY memories_update_own ON memories
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

-- Users can only delete their own memories
CREATE POLICY memories_delete_own ON memories
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- =============================================================================
-- RLS POLICIES FOR KNOWLEDGE EDGES
-- =============================================================================

CREATE POLICY edges_select_own ON knowledge_edges
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY edges_insert_own ON knowledge_edges
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY edges_update_own ON knowledge_edges
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY edges_delete_own ON knowledge_edges
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- =============================================================================
-- RLS POLICIES FOR CONSOLIDATION HISTORY
-- =============================================================================

CREATE POLICY consolidation_select_own ON consolidation_history
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY consolidation_insert_own ON consolidation_history
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

-- No update/delete policies - consolidation history is append-only for audit

-- =============================================================================
-- RLS POLICIES FOR FILES
-- =============================================================================

CREATE POLICY files_select_own ON files
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY files_insert_own ON files
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY files_update_own ON files
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY files_delete_own ON files
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- =============================================================================
-- RLS POLICIES FOR DOCUMENT CHUNKS
-- =============================================================================

CREATE POLICY chunks_select_own ON document_chunks
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY chunks_insert_own ON document_chunks
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY chunks_update_own ON document_chunks
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY chunks_delete_own ON document_chunks
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- =============================================================================
-- RLS POLICIES FOR API KEYS
-- =============================================================================

CREATE POLICY api_keys_select_own ON api_keys
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY api_keys_insert_own ON api_keys
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY api_keys_update_own ON api_keys
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY api_keys_delete_own ON api_keys
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- =============================================================================
-- SERVICE ROLE BYPASS
-- =============================================================================
-- Create a service role that bypasses RLS for admin/migration tasks

CREATE ROLE knowwhere_service NOLOGIN;
GRANT ALL ON ALL TABLES IN SCHEMA public TO knowwhere_service;

-- Service role can bypass RLS
ALTER TABLE memories FORCE ROW LEVEL SECURITY;
ALTER TABLE knowledge_edges FORCE ROW LEVEL SECURITY;
ALTER TABLE consolidation_history FORCE ROW LEVEL SECURITY;
ALTER TABLE files FORCE ROW LEVEL SECURITY;
ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;

-- Grant service role bypass
ALTER ROLE knowwhere_service BYPASSRLS;

-- =============================================================================
-- HELPER FUNCTION TO SET USER CONTEXT
-- =============================================================================

CREATE OR REPLACE FUNCTION set_current_user_id(user_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_uuid::TEXT, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- SCHEMA VERSION
-- =============================================================================

INSERT INTO schema_migrations (version) VALUES ('002_enable_rls')
ON CONFLICT (version) DO NOTHING;
