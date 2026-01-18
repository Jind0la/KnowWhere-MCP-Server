"""
Edge Repository

Data access layer for Knowledge Graph edges.
"""

from typing import Any
from uuid import UUID

import structlog

from src.models.edge import EdgeCreate, EdgeType, EdgeUpdate, EdgeWithNodes, KnowledgeEdge
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class EdgeRepository:
    """
    Repository for Knowledge Edge CRUD operations.
    
    Provides:
    - Create, read, update, delete operations
    - Graph traversal queries
    - Relationship strength queries
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create(self, edge: EdgeCreate) -> KnowledgeEdge:
        """Create a new knowledge edge."""
        query = """
            INSERT INTO knowledge_edges (
                user_id, from_node_id, to_node_id, edge_type,
                strength, confidence, causality, bidirectional, reason, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            edge.user_id,
            edge.from_node_id,
            edge.to_node_id,
            edge.edge_type.value,
            edge.strength,
            edge.confidence,
            edge.causality,
            edge.bidirectional,
            edge.reason,
            edge.metadata,
        )
        
        logger.info(
            "Edge created",
            edge_id=row["id"],
            from_node=edge.from_node_id,
            to_node=edge.to_node_id,
            edge_type=edge.edge_type.value,
        )
        
        return self._row_to_edge(row)
    
    async def create_many(self, edges: list[EdgeCreate]) -> list[KnowledgeEdge]:
        """Create multiple edges in a batch."""
        if not edges:
            return []
        
        query = """
            INSERT INTO knowledge_edges (
                user_id, from_node_id, to_node_id, edge_type,
                strength, confidence, causality, bidirectional, reason, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (user_id, from_node_id, to_node_id, edge_type) DO UPDATE
            SET strength = EXCLUDED.strength,
                confidence = EXCLUDED.confidence,
                updated_at = NOW()
            RETURNING *
        """
        
        results = []
        for edge in edges:
            row = await self.db.fetchrow(
                query,
                edge.user_id,
                edge.from_node_id,
                edge.to_node_id,
                edge.edge_type.value,
                edge.strength,
                edge.confidence,
                edge.causality,
                edge.bidirectional,
                edge.reason,
                edge.metadata,
            )
            results.append(self._row_to_edge(row))
        
        logger.info("Batch edges created", count=len(results))
        return results
    
    async def get_by_id(self, edge_id: UUID, user_id: UUID) -> KnowledgeEdge | None:
        """Get an edge by ID."""
        query = """
            SELECT * FROM knowledge_edges
            WHERE id = $1 AND user_id = $2
        """
        row = await self.db.fetchrow(query, edge_id, user_id)
        return self._row_to_edge(row) if row else None
    
    async def get_edges_from_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
        edge_type: EdgeType | None = None,
    ) -> list[KnowledgeEdge]:
        """Get all edges starting from a memory."""
        conditions = ["user_id = $1", "from_node_id = $2"]
        params: list[Any] = [user_id, memory_id]
        
        if edge_type is not None:
            conditions.append("edge_type = $3")
            params.append(edge_type.value)
        
        query = f"""
            SELECT * FROM knowledge_edges
            WHERE {' AND '.join(conditions)}
            ORDER BY strength DESC
        """
        
        rows = await self.db.fetch(query, *params)
        return [self._row_to_edge(row) for row in rows]
    
    async def get_edges_to_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
        edge_type: EdgeType | None = None,
    ) -> list[KnowledgeEdge]:
        """Get all edges pointing to a memory."""
        conditions = ["user_id = $1", "to_node_id = $2"]
        params: list[Any] = [user_id, memory_id]
        
        if edge_type is not None:
            conditions.append("edge_type = $3")
            params.append(edge_type.value)
        
        query = f"""
            SELECT * FROM knowledge_edges
            WHERE {' AND '.join(conditions)}
            ORDER BY strength DESC
        """
        
        rows = await self.db.fetch(query, *params)
        return [self._row_to_edge(row) for row in rows]
    
    async def get_all_edges_for_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
    ) -> list[KnowledgeEdge]:
        """Get all edges connected to a memory (both directions)."""
        query = """
            SELECT * FROM knowledge_edges
            WHERE user_id = $1 AND (from_node_id = $2 OR to_node_id = $2)
            ORDER BY strength DESC
        """
        
        rows = await self.db.fetch(query, user_id, memory_id)
        return [self._row_to_edge(row) for row in rows]
    
    async def get_related_memories(
        self,
        memory_id: UUID,
        user_id: UUID,
        depth: int = 1,
        min_strength: float = 0.5,
    ) -> list[EdgeWithNodes]:
        """
        Get related memories through knowledge graph traversal.
        
        Args:
            memory_id: Starting memory
            user_id: User isolation
            depth: How many hops to traverse
            min_strength: Minimum edge strength
            
        Returns:
            List of edges with node content
        """
        query = """
            WITH RECURSIVE related AS (
                SELECT 
                    e.id, e.from_node_id, e.to_node_id, e.edge_type,
                    e.strength, e.confidence, e.causality, e.bidirectional,
                    e.reason, e.metadata, e.created_at, e.updated_at,
                    1 as depth
                FROM knowledge_edges e
                WHERE e.user_id = $1 
                    AND e.from_node_id = $2
                    AND e.strength >= $4
                
                UNION ALL
                
                SELECT 
                    e.id, e.from_node_id, e.to_node_id, e.edge_type,
                    e.strength, e.confidence, e.causality, e.bidirectional,
                    e.reason, e.metadata, e.created_at, e.updated_at,
                    r.depth + 1
                FROM knowledge_edges e
                INNER JOIN related r ON e.from_node_id = r.to_node_id
                WHERE e.user_id = $1 
                    AND r.depth < $3
                    AND e.strength >= $4
            )
            SELECT DISTINCT ON (r.id)
                r.*,
                m_from.content as from_node_content,
                m_to.content as to_node_content
            FROM related r
            LEFT JOIN memories m_from ON r.from_node_id = m_from.id
            LEFT JOIN memories m_to ON r.to_node_id = m_to.id
            ORDER BY r.id, r.strength DESC
        """
        
        rows = await self.db.fetch(query, user_id, memory_id, depth, min_strength)
        return [self._row_to_edge_with_nodes(row) for row in rows]
    
    async def find_path(
        self,
        from_memory_id: UUID,
        to_memory_id: UUID,
        user_id: UUID,
        max_depth: int = 5,
    ) -> list[KnowledgeEdge]:
        """Find shortest path between two memories."""
        query = """
            WITH RECURSIVE path AS (
                SELECT 
                    ARRAY[e.id] as edge_path,
                    ARRAY[e.from_node_id, e.to_node_id] as node_path,
                    e.to_node_id as current_node,
                    1 as depth
                FROM knowledge_edges e
                WHERE e.user_id = $1 AND e.from_node_id = $2
                
                UNION ALL
                
                SELECT 
                    p.edge_path || e.id,
                    p.node_path || e.to_node_id,
                    e.to_node_id,
                    p.depth + 1
                FROM knowledge_edges e
                INNER JOIN path p ON e.from_node_id = p.current_node
                WHERE e.user_id = $1 
                    AND p.depth < $4
                    AND NOT (e.to_node_id = ANY(p.node_path))
            )
            SELECT edge_path
            FROM path
            WHERE current_node = $3
            ORDER BY depth
            LIMIT 1
        """
        
        row = await self.db.fetchrow(query, user_id, from_memory_id, to_memory_id, max_depth)
        
        if not row or not row["edge_path"]:
            return []
        
        # Fetch all edges in the path
        edge_ids = row["edge_path"]
        edges_query = """
            SELECT * FROM knowledge_edges
            WHERE id = ANY($1)
        """
        edge_rows = await self.db.fetch(edges_query, edge_ids)
        
        # Return in path order
        edge_map = {row["id"]: self._row_to_edge(row) for row in edge_rows}
        return [edge_map[eid] for eid in edge_ids if eid in edge_map]
    
    async def update(
        self,
        edge_id: UUID,
        user_id: UUID,
        update_data: EdgeUpdate,
    ) -> KnowledgeEdge | None:
        """Update an edge."""
        updates = []
        params: list[Any] = []
        param_idx = 1
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            if value is not None:
                if field == "edge_type":
                    value = value.value
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not updates:
            return await self.get_by_id(edge_id, user_id)
        
        params.extend([edge_id, user_id])
        
        query = f"""
            UPDATE knowledge_edges
            SET {', '.join(updates)}
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, *params)
        return self._row_to_edge(row) if row else None
    
    async def delete(self, edge_id: UUID, user_id: UUID) -> bool:
        """Delete an edge."""
        query = """
            DELETE FROM knowledge_edges
            WHERE id = $1 AND user_id = $2
            RETURNING id
        """
        result = await self.db.fetchval(query, edge_id, user_id)
        return result is not None
    
    async def delete_for_memory(self, memory_id: UUID, user_id: UUID) -> int:
        """Delete all edges connected to a memory."""
        query = """
            DELETE FROM knowledge_edges
            WHERE user_id = $1 AND (from_node_id = $2 OR to_node_id = $2)
        """
        result = await self.db.execute(query, user_id, memory_id)
        # Extract count from "DELETE N"
        count = int(result.split()[-1]) if result else 0
        logger.info("Edges deleted for memory", memory_id=memory_id, count=count)
        return count
    
    async def count_by_user(self, user_id: UUID) -> int:
        """Count edges for a user."""
        query = "SELECT COUNT(*) FROM knowledge_edges WHERE user_id = $1"
        return await self.db.fetchval(query, user_id) or 0

    async def get_edges_for_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
    ) -> list[KnowledgeEdge]:
        """Get all edges connected to a specific memory (alias for get_all_edges_for_memory)."""
        return await self.get_all_edges_for_memory(memory_id, user_id)

    async def get_all_for_user(
        self,
        user_id: UUID,
        limit: int = 100,
    ) -> list[KnowledgeEdge]:
        """Get all edges for a user with limit."""
        query = """
            SELECT * FROM knowledge_edges
            WHERE user_id = $1
            ORDER BY strength DESC, created_at DESC
            LIMIT $2
        """
        rows = await self.db.fetch(query, user_id, limit)
        return [self._row_to_edge(row) for row in rows]
    
    def _row_to_edge(self, row: Any) -> KnowledgeEdge:
        """Convert database row to KnowledgeEdge model."""
        import json
        
        # Handle JSONB field that might come as string
        metadata = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        
        return KnowledgeEdge(
            id=row["id"],
            user_id=row["user_id"],
            from_node_id=row["from_node_id"],
            to_node_id=row["to_node_id"],
            edge_type=EdgeType(row["edge_type"]),
            strength=row["strength"],
            confidence=row["confidence"],
            causality=row["causality"],
            bidirectional=row["bidirectional"],
            reason=row["reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=metadata,
        )
    
    def _row_to_edge_with_nodes(self, row: Any) -> EdgeWithNodes:
        """Convert database row to EdgeWithNodes model."""
        edge = self._row_to_edge(row)
        return EdgeWithNodes(
            **edge.model_dump(),
            from_node_content=row.get("from_node_content"),
            to_node_content=row.get("to_node_content"),
        )
