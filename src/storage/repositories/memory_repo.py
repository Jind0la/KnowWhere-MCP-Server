"""
Memory Repository

Data access layer for Memory entities with vector search support.
"""

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from src.models.memory import (
    Memory,
    MemoryCreate,
    MemoryStatus,
    MemoryType,
    MemoryUpdate,
    MemoryWithSimilarity,
)
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class MemoryRepository:
    """
    Repository for Memory CRUD operations.
    
    Provides:
    - Create, read, update, delete operations
    - Vector similarity search
    - Filtering by type, entity, date range
    - Access tracking
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create(self, memory: MemoryCreate) -> Memory:
        """
        Create a new memory.
        
        Args:
            memory: Memory creation data
            
        Returns:
            Created Memory with ID
        """
        query = """
            INSERT INTO memories (
                user_id, content, memory_type, embedding, entities,
                importance, confidence, source, source_id, metadata,
                domain, category, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
        """
        
        import json
        logger.debug("Executing memory creation query", user_id=str(memory.user_id), status=memory.status.value)
        try:
            row = await self.db.fetchrow(
                query,
                memory.user_id,
                memory.content,
                memory.memory_type.value,
                memory.embedding,
                json.dumps(memory.entities),
                memory.importance,
                memory.confidence,
                memory.source.value,
                memory.source_id,
                json.dumps(memory.metadata) if memory.metadata else None,
                memory.domain,
                memory.category,
                memory.status.value,
            )
            logger.info("Memory created", memory_id=row["id"], user_id=memory.user_id)
            return self._row_to_memory(row)
        except Exception as e:
            logger.error("Memory creation query failed", error=str(e), user_id=str(memory.user_id))
            raise
    
    async def get_by_id(
        self,
        memory_id: UUID,
        user_id: UUID,
        update_access: bool = False,
    ) -> Memory | None:
        """
        Get a memory by ID.
        
        Args:
            memory_id: Memory UUID
            user_id: Owner user ID (for security)
            update_access: Whether to increment access count
            
        Returns:
            Memory or None if not found
        """
        query = """
            SELECT * FROM memories
            WHERE id = $1 AND user_id = $2 AND status = 'active'
        """
        
        row = await self.db.fetchrow(query, memory_id, user_id)
        
        if row is None:
            return None
        
        if update_access:
            await self._update_access(memory_id)
        
        return self._row_to_memory(row)
    
    async def search_similar(
        self,
        embedding: list[float],
        user_id: UUID,
        limit: int = 10,
        memory_type: MemoryType | None = None,
        min_importance: int | None = None,
        entity: str | None = None,
        date_range: str | None = None,
        status: MemoryStatus | None = MemoryStatus.ACTIVE,
        domain: str | None = None,
        category_prefix: str | None = None,
    ) -> list[MemoryWithSimilarity]:
        """
        Search for similar memories using vector similarity.
        
        Args:
            embedding: Query embedding vector
            user_id: User ID for isolation
            limit: Maximum results
            memory_type: Filter by type
            min_importance: Minimum importance filter
            entity: Filter by entity
            date_range: Time filter (last_7_days, last_30_days, etc.)
            
        Returns:
            List of memories with similarity scores
        """
        # Build dynamic query with filters
        conditions = ["user_id = $2"]
        params: list[Any] = [embedding, user_id]
        param_idx = 3 # $1=embedding, $2=user_id, $3 and beyond for filters
        
        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1
        else:
            # Default to excluding deleted/superseded if no status provided
            conditions.append(f"status NOT IN ('deleted', 'superseded')")
        
        if memory_type is not None:
            conditions.append(f"memory_type = ${param_idx}")
            params.append(memory_type.value)
            param_idx += 1
        
        if min_importance is not None:
            conditions.append(f"importance >= ${param_idx}")
            params.append(min_importance)
            param_idx += 1
        
        if entity is not None:
            conditions.append(f"entities @> ${param_idx}::jsonb")
            params.append(f'["{entity}"]')
            param_idx += 1
        
        if date_range is not None:
            date_filter = self._get_date_filter(date_range)
            if date_filter:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(date_filter)
                param_idx += 1
        
        # Hierarchy filters
        if domain is not None:
            conditions.append(f"domain = ${param_idx}")
            params.append(domain)
            param_idx += 1
        
        if category_prefix is not None:
            conditions.append(f"category ILIKE ${param_idx}")
            params.append(f"{category_prefix}%")
            param_idx += 1
        
        # Add limit to params
        params.append(limit)
        limit_idx = param_idx
        
        query = f"""
            SELECT *,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM memories
            WHERE {' AND '.join(conditions)}
            ORDER BY embedding <=> $1::vector
            LIMIT ${limit_idx}
        """
        
        rows = await self.db.fetch(query, *params)
        
        return [self._row_to_memory_with_similarity(row) for row in rows]
    
    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        memory_type: MemoryType | None = None,
        status: MemoryStatus | None = MemoryStatus.ACTIVE,
    ) -> list[Memory]:
        """List memories for a user. If status is None, returns all non-deleted memories."""
        conditions = ["user_id = $1"]
        params: list[Any] = [user_id]
        param_idx = 2

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1
        else:
            conditions.append("status NOT IN ('deleted', 'superseded')")
        
        if memory_type is not None:
            conditions.append(f"memory_type = ${param_idx}")
            params.append(memory_type.value)
            param_idx += 1
        
        query = f"""
            SELECT * FROM memories
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        
        rows = await self.db.fetch(query, *params)
        return [self._row_to_memory(row) for row in rows]
    
    async def get_preferences(self, user_id: UUID, limit: int = 50) -> list[Memory]:
        """Get user's preference memories."""
        query = """
            SELECT * FROM memories
            WHERE user_id = $1 
                AND status = 'active' 
                AND memory_type = 'preference'
            ORDER BY importance DESC, created_at DESC
            LIMIT $2
        """
        
        rows = await self.db.fetch(query, user_id, limit)
        return [self._row_to_memory(row) for row in rows]
    
    async def update(
        self,
        memory_id: UUID,
        user_id: UUID,
        update_data: MemoryUpdate,
    ) -> Memory | None:
        """Update a memory."""
        # Build update query dynamically
        updates = []
        params: list[Any] = []
        param_idx = 1
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            if value is not None:
                if field == "memory_type":
                    value = value.value
                elif field == "status":
                    value = value.value
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not updates:
            return await self.get_by_id(memory_id, user_id)
        
        params.extend([memory_id, user_id])
        
        query = f"""
            UPDATE memories
            SET {', '.join(updates)}
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, *params)
        return self._row_to_memory(row) if row else None
    
    async def soft_delete(self, memory_id: UUID, user_id: UUID) -> bool:
        """
        Soft delete a memory (GDPR-compliant).
        
        Sets status to 'deleted' and records deletion timestamp.
        """
        query = """
            UPDATE memories
            SET status = 'deleted', deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND status = 'active'
            RETURNING id
        """
        
        result = await self.db.fetchval(query, memory_id, user_id)
        
        if result:
            logger.info("Memory soft-deleted", memory_id=memory_id, user_id=user_id)
            return True
        return False
    
    async def hard_delete(self, memory_id: UUID, user_id: UUID) -> bool:
        """Permanently delete a memory."""
        query = """
            DELETE FROM memories
            WHERE id = $1 AND user_id = $2
            RETURNING id
        """
        
        result = await self.db.fetchval(query, memory_id, user_id)
        
        if result:
            logger.info("Memory hard-deleted", memory_id=memory_id, user_id=user_id)
            return True
        return False
    
    async def count_by_user(
        self,
        user_id: UUID,
        status: MemoryStatus = MemoryStatus.ACTIVE,
    ) -> int:
        """Count memories for a user."""
        query = """
            SELECT COUNT(*) FROM memories
            WHERE user_id = $1 AND status = $2
        """
        return await self.db.fetchval(query, user_id, status.value) or 0
    
    async def get_entities_for_user(self, user_id: UUID, limit: int = 100) -> list[str]:
        """Get all unique entities for a user."""
        query = """
            SELECT DISTINCT jsonb_array_elements_text(entities) as entity
            FROM memories
            WHERE user_id = $1 AND status NOT IN ('deleted', 'superseded')
            LIMIT $2
        """
        rows = await self.db.fetch(query, user_id, limit)
        return [row["entity"] for row in rows]

    async def get_memory_stats(self, user_id: UUID) -> dict[str, Any]:
        """Get comprehensive memory statistics for a user."""
        query = """
            SELECT
                COUNT(*) as total_memories,
                COUNT(CASE WHEN memory_type = 'preference' THEN 1 END) as preference_count,
                COUNT(CASE WHEN memory_type = 'semantic' THEN 1 END) as semantic_count,
                COUNT(CASE WHEN memory_type = 'episodic' THEN 1 END) as episodic_count,
                COUNT(CASE WHEN memory_type = 'procedural' THEN 1 END) as procedural_count,
                COUNT(CASE WHEN memory_type = 'meta' THEN 1 END) as meta_count,
                AVG(importance) as avg_importance,
                MAX(created_at) as last_memory_date,
                MIN(created_at) as first_memory_date,
                SUM(access_count) as total_accesses
            FROM memories
            WHERE user_id = $1 AND status NOT IN ('deleted', 'superseded')
        """

        row = await self.db.fetchrow(query, user_id)

        if not row:
            return {
                "total_memories": 0,
                "by_type": {
                    "preference": 0,
                    "semantic": 0,
                    "episodic": 0,
                    "procedural": 0,
                    "meta": 0,
                },
                "avg_importance": 0.0,
                "last_memory_date": None,
                "first_memory_date": None,
                "total_accesses": 0,
            }

        return {
            "total_memories": row["total_memories"],
            "by_type": {
                "preference": row["preference_count"],
                "semantic": row["semantic_count"],
                "episodic": row["episodic_count"],
                "procedural": row["procedural_count"],
                "meta": row["meta_count"],
            },
            "avg_importance": float(row["avg_importance"] or 0.0),
            "last_memory_date": row["last_memory_date"].isoformat() if row["last_memory_date"] else None,
            "first_memory_date": row["first_memory_date"].isoformat() if row["first_memory_date"] else None,
            "total_accesses": row["total_accesses"] or 0,
        }

    async def get_unique_domains_categories(self, user_id: UUID) -> dict[str, list[str]]:
        """
        Get all unique domains and categories for usage in LLM context.
        Returns a dict with 'domains' and 'categories' lists.
        """
        query_domains = """
            SELECT DISTINCT domain 
            FROM memories 
            WHERE user_id = $1 AND domain IS NOT NULL AND status = 'active'
            ORDER BY domain
            LIMIT 50
        """
        
        query_categories = """
            SELECT DISTINCT category 
            FROM memories 
            WHERE user_id = $1 AND category IS NOT NULL AND status = 'active'
            ORDER BY category
            LIMIT 100
        """
        
        domains = await self.db.fetch(query_domains, user_id)
        categories = await self.db.fetch(query_categories, user_id)
        
        return {
            "domains": [r["domain"] for r in domains if r["domain"]],
            "categories": [r["category"] for r in categories if r["category"]]
        }


    async def get_memories_by_type(
        self,
        user_id: UUID,
        memory_type: MemoryType,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Memory]:
        """Get memories filtered by type."""
        query = """
            SELECT * FROM memories
            WHERE user_id = $1 AND memory_type = $2 AND status = 'active'
            ORDER BY importance DESC, created_at DESC
            LIMIT $3 OFFSET $4
        """

        rows = await self.db.fetch(query, user_id, memory_type.value, limit, offset)
        return [self._row_to_memory(row) for row in rows]
    
    async def _update_access(self, memory_id: UUID) -> None:
        """Update access count and timestamp."""
        query = """
            UPDATE memories
            SET access_count = access_count + 1, last_accessed = NOW()
            WHERE id = $1
        """
        await self.db.execute(query, memory_id)
    
    def _get_date_filter(self, date_range: str) -> datetime | None:
        """Convert date range string to datetime."""
        now = datetime.utcnow()
        ranges = {
            "last_7_days": now - timedelta(days=7),
            "last_30_days": now - timedelta(days=30),
            "last_year": now - timedelta(days=365),
            "all_time": None,
        }
        return ranges.get(date_range)
    
    def _row_to_memory(self, row: Any) -> Memory:
        """Convert database row to Memory model."""
        # Parse JSONB fields if they're strings
        entities = row["entities"] or []
        if isinstance(entities, str):
            entities = json.loads(entities)
        
        metadata = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return Memory(
            id=row["id"],
            user_id=row["user_id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            embedding=row["embedding"],
            entities=entities,
            importance=row["importance"],
            confidence=row["confidence"],
            status=MemoryStatus(row["status"]),
            superseded_by=row["superseded_by"],
            source=row["source"],
            source_id=row["source_id"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
            metadata=metadata,
            domain=row.get("domain"),
            category=row.get("category"),
        )
    
    def _row_to_memory_with_similarity(self, row: Any) -> MemoryWithSimilarity:
        """Convert database row to MemoryWithSimilarity model."""
        memory = self._row_to_memory(row)
        return MemoryWithSimilarity(
            **memory.model_dump(),
            similarity=float(row["similarity"]),
        )
