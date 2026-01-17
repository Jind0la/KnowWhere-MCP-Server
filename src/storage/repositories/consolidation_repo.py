"""
Consolidation Repository

Data access layer for consolidation history.
"""

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

import structlog

from src.models.consolidation import ConsolidationHistory, ConsolidationStatus
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class ConsolidationRepository:
    """
    Repository for Consolidation History CRUD operations.
    
    Provides:
    - Create and query consolidation records
    - Analytics queries
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create(self, history: ConsolidationHistory) -> ConsolidationHistory:
        """Create a new consolidation history record."""
        query = """
            INSERT INTO consolidation_history (
                id, user_id, consolidation_date, session_id, conversation_id,
                session_transcript_length, claims_extracted, memories_processed,
                new_memories_created, merged_count, conflicts_resolved, edges_created,
                processing_time_ms, tokens_used, embedding_cost_usd,
                duplicate_similarity_threshold, conflict_similarity_range,
                patterns_detected, key_entities, sentiment_analysis,
                status, error_message, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20, $21, $22, $23
            )
            RETURNING *
        """
        
        # Serialize lists/dicts to JSON for database storage
        patterns_json = json.dumps(history.patterns_detected) if history.patterns_detected else "[]"
        entities_json = json.dumps(history.key_entities) if history.key_entities else "[]"
        sentiment_json = json.dumps(history.sentiment_analysis) if history.sentiment_analysis else "{}"
        metadata_json = json.dumps(history.metadata) if history.metadata else "{}"
        
        row = await self.db.fetchrow(
            query,
            history.id,
            history.user_id,
            history.consolidation_date,
            history.session_id,
            history.conversation_id,
            history.session_transcript_length,
            history.claims_extracted,
            history.memories_processed,
            history.new_memories_created,
            history.merged_count,
            history.conflicts_resolved,
            history.edges_created,
            history.processing_time_ms,
            history.tokens_used,
            history.embedding_cost_usd,
            history.duplicate_similarity_threshold,
            history.conflict_similarity_range,
            patterns_json,
            entities_json,
            sentiment_json,
            history.status.value,
            history.error_message,
            metadata_json,
        )
        
        logger.info(
            "Consolidation history created",
            consolidation_id=row["id"],
            user_id=history.user_id,
            new_memories=history.new_memories_created,
        )
        
        return self._row_to_history(row)
    
    async def get_by_id(self, consolidation_id: UUID, user_id: UUID) -> ConsolidationHistory | None:
        """Get a consolidation record by ID."""
        query = """
            SELECT * FROM consolidation_history
            WHERE id = $1 AND user_id = $2
        """
        row = await self.db.fetchrow(query, consolidation_id, user_id)
        return self._row_to_history(row) if row else None
    
    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        status: ConsolidationStatus | None = None,
    ) -> list[ConsolidationHistory]:
        """List consolidation history for a user."""
        conditions = ["user_id = $1"]
        params: list[Any] = [user_id]
        
        if status is not None:
            conditions.append("status = $2")
            params.append(status.value)
        
        query = f"""
            SELECT * FROM consolidation_history
            WHERE {' AND '.join(conditions)}
            ORDER BY consolidation_date DESC, created_at DESC
            LIMIT {limit} OFFSET {offset}
        """
        
        rows = await self.db.fetch(query, *params)
        return [self._row_to_history(row) for row in rows]
    
    async def get_by_date_range(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[ConsolidationHistory]:
        """Get consolidations within a date range."""
        query = """
            SELECT * FROM consolidation_history
            WHERE user_id = $1 
                AND consolidation_date >= $2 
                AND consolidation_date <= $3
            ORDER BY consolidation_date DESC
        """
        
        rows = await self.db.fetch(query, user_id, start_date, end_date)
        return [self._row_to_history(row) for row in rows]
    
    async def get_latest(self, user_id: UUID) -> ConsolidationHistory | None:
        """Get the most recent consolidation for a user."""
        query = """
            SELECT * FROM consolidation_history
            WHERE user_id = $1 AND status = 'completed'
            ORDER BY consolidation_date DESC, created_at DESC
            LIMIT 1
        """
        row = await self.db.fetchrow(query, user_id)
        return self._row_to_history(row) if row else None
    
    async def update_status(
        self,
        consolidation_id: UUID,
        user_id: UUID,
        status: ConsolidationStatus,
        error_message: str | None = None,
    ) -> bool:
        """Update consolidation status."""
        query = """
            UPDATE consolidation_history
            SET status = $3, error_message = $4
            WHERE id = $1 AND user_id = $2
            RETURNING id
        """
        result = await self.db.fetchval(query, consolidation_id, user_id, status.value, error_message)
        return result is not None
    
    async def get_stats(self, user_id: UUID) -> dict[str, Any]:
        """Get aggregated stats for a user's consolidations."""
        query = """
            SELECT 
                COUNT(*) as total_consolidations,
                SUM(new_memories_created) as total_memories_created,
                SUM(merged_count) as total_merged,
                SUM(conflicts_resolved) as total_conflicts_resolved,
                SUM(edges_created) as total_edges_created,
                AVG(processing_time_ms) as avg_processing_time_ms,
                SUM(tokens_used) as total_tokens_used,
                SUM(embedding_cost_usd) as total_embedding_cost
            FROM consolidation_history
            WHERE user_id = $1 AND status = 'completed'
        """
        
        row = await self.db.fetchrow(query, user_id)
        
        if not row:
            return {}
        
        return {
            "total_consolidations": row["total_consolidations"] or 0,
            "total_memories_created": row["total_memories_created"] or 0,
            "total_merged": row["total_merged"] or 0,
            "total_conflicts_resolved": row["total_conflicts_resolved"] or 0,
            "total_edges_created": row["total_edges_created"] or 0,
            "avg_processing_time_ms": float(row["avg_processing_time_ms"] or 0),
            "total_tokens_used": row["total_tokens_used"] or 0,
            "total_embedding_cost": float(row["total_embedding_cost"] or 0),
        }
    
    async def count_by_user(
        self,
        user_id: UUID,
        status: ConsolidationStatus | None = None,
    ) -> int:
        """Count consolidations for a user."""
        if status:
            query = "SELECT COUNT(*) FROM consolidation_history WHERE user_id = $1 AND status = $2"
            return await self.db.fetchval(query, user_id, status.value) or 0
        else:
            query = "SELECT COUNT(*) FROM consolidation_history WHERE user_id = $1"
            return await self.db.fetchval(query, user_id) or 0
    
    async def delete_old_records(self, user_id: UUID, days_to_keep: int = 365) -> int:
        """Delete old consolidation records (data retention)."""
        query = """
            DELETE FROM consolidation_history
            WHERE user_id = $1 
                AND consolidation_date < CURRENT_DATE - $2::int
            RETURNING id
        """
        rows = await self.db.fetch(query, user_id, days_to_keep)
        return len(rows)
    
    def _row_to_history(self, row: Any) -> ConsolidationHistory:
        """Convert database row to ConsolidationHistory model."""
        # Parse JSON fields
        patterns = row["patterns_detected"]
        if isinstance(patterns, str):
            patterns = json.loads(patterns) if patterns else []
        
        entities = row["key_entities"]
        if isinstance(entities, str):
            entities = json.loads(entities) if entities else []
        
        sentiment = row["sentiment_analysis"]
        if isinstance(sentiment, str):
            sentiment = json.loads(sentiment) if sentiment else {}
        
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        
        return ConsolidationHistory(
            id=row["id"],
            user_id=row["user_id"],
            consolidation_date=row["consolidation_date"],
            session_id=row["session_id"],
            conversation_id=row["conversation_id"],
            session_transcript_length=row["session_transcript_length"],
            claims_extracted=row["claims_extracted"],
            memories_processed=row["memories_processed"],
            new_memories_created=row["new_memories_created"],
            merged_count=row["merged_count"],
            conflicts_resolved=row["conflicts_resolved"],
            edges_created=row["edges_created"],
            processing_time_ms=row["processing_time_ms"],
            tokens_used=row["tokens_used"],
            embedding_cost_usd=row["embedding_cost_usd"],
            duplicate_similarity_threshold=row["duplicate_similarity_threshold"],
            conflict_similarity_range=row["conflict_similarity_range"],
            patterns_detected=patterns or [],
            key_entities=entities or [],
            sentiment_analysis=sentiment or {},
            status=ConsolidationStatus(row["status"]),
            error_message=row["error_message"],
            created_at=row["created_at"],
            metadata=metadata or {},
        )
