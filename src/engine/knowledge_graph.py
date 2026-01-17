"""
Knowledge Graph Manager

Manages relationships between memories in the knowledge graph.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from src.models.edge import EdgeCreate, EdgeType, KnowledgeEdge
from src.models.memory import Memory, MemoryType
from src.storage.database import Database, get_database
from src.storage.repositories.edge_repo import EdgeRepository
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


class KnowledgeGraphManager:
    """
    Manages the knowledge graph of memory relationships.
    
    Provides:
    - Edge creation and management
    - Graph traversal
    - Evolution tracking
    - Pattern detection
    """
    
    def __init__(self, db: Database | None = None):
        self._db = db
        self._edge_repo: EdgeRepository | None = None
        self._memory_repo: MemoryRepository | None = None
    
    async def _get_db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def _get_edge_repo(self) -> EdgeRepository:
        """Get edge repository."""
        if self._edge_repo is None:
            db = await self._get_db()
            self._edge_repo = EdgeRepository(db)
        return self._edge_repo
    
    async def _get_memory_repo(self) -> MemoryRepository:
        """Get memory repository."""
        if self._memory_repo is None:
            db = await self._get_db()
            self._memory_repo = MemoryRepository(db)
        return self._memory_repo
    
    async def create_edge(
        self,
        user_id: UUID,
        from_memory_id: UUID,
        to_memory_id: UUID,
        edge_type: EdgeType,
        strength: float = 0.7,
        confidence: float = 0.8,
        reason: str | None = None,
        causality: bool = False,
        bidirectional: bool = False,
    ) -> KnowledgeEdge:
        """
        Create a relationship between two memories.
        
        Args:
            user_id: Owner user ID
            from_memory_id: Source memory
            to_memory_id: Target memory
            edge_type: Type of relationship
            strength: Relationship strength (0-1)
            confidence: Confidence in this relationship
            reason: Why this relationship exists
            causality: Is this a causal relationship?
            bidirectional: Does it work both ways?
            
        Returns:
            Created KnowledgeEdge
        """
        edge_create = EdgeCreate(
            user_id=user_id,
            from_node_id=from_memory_id,
            to_node_id=to_memory_id,
            edge_type=edge_type,
            strength=strength,
            confidence=confidence,
            reason=reason,
            causality=causality,
            bidirectional=bidirectional,
        )
        
        repo = await self._get_edge_repo()
        edge = await repo.create(edge_create)
        
        logger.info(
            "Edge created",
            edge_id=str(edge.id),
            edge_type=edge_type.value,
            from_node=str(from_memory_id),
            to_node=str(to_memory_id),
        )
        
        return edge
    
    async def create_edges_from_relationships(
        self,
        user_id: UUID,
        relationships: list[dict[str, Any]],
        entity_to_memory: dict[str, UUID],
    ) -> list[KnowledgeEdge]:
        """
        Create edges from extracted relationships.
        
        Args:
            user_id: Owner user ID
            relationships: List of relationship dicts from LLM
            entity_to_memory: Mapping of entity names to memory IDs
            
        Returns:
            List of created edges
        """
        edges: list[KnowledgeEdge] = []
        repo = await self._get_edge_repo()
        
        # Map relationship types to edge types
        type_mapping = {
            "likes": EdgeType.LIKES,
            "dislikes": EdgeType.DISLIKES,
            "leads_to": EdgeType.LEADS_TO,
            "related_to": EdgeType.RELATED_TO,
            "depends_on": EdgeType.DEPENDS_ON,
            "evolves_into": EdgeType.EVOLVES_INTO,
            "contradicts": EdgeType.CONTRADICTS,
            "supports": EdgeType.SUPPORTS,
        }
        
        edges_to_create: list[EdgeCreate] = []
        
        for rel in relationships:
            from_entity = rel.get("from_entity", "")
            to_entity = rel.get("to_entity", "")
            rel_type = rel.get("relationship_type", "related_to")
            confidence = float(rel.get("confidence", 0.7))
            
            # Get memory IDs for entities
            from_memory_id = entity_to_memory.get(from_entity)
            to_memory_id = entity_to_memory.get(to_entity)
            
            if not from_memory_id or not to_memory_id:
                continue
            
            if from_memory_id == to_memory_id:
                continue
            
            edge_type = type_mapping.get(rel_type, EdgeType.RELATED_TO)
            
            edges_to_create.append(EdgeCreate(
                user_id=user_id,
                from_node_id=from_memory_id,
                to_node_id=to_memory_id,
                edge_type=edge_type,
                strength=confidence,
                confidence=confidence,
                reason=f"Inferred from entities: {from_entity} -> {to_entity}",
                causality=edge_type in (EdgeType.LEADS_TO, EdgeType.EVOLVES_INTO),
            ))
        
        if edges_to_create:
            edges = await repo.create_many(edges_to_create)
        
        logger.info("Edges created from relationships", count=len(edges))
        return edges
    
    async def link_related_memories(
        self,
        user_id: UUID,
        new_memory: Memory,
        existing_memories: list[Memory],
        similarity_threshold: float = 0.7,
    ) -> list[KnowledgeEdge]:
        """
        Link a new memory to related existing memories.
        
        Creates RELATED_TO edges for similar memories.
        """
        edges: list[KnowledgeEdge] = []
        repo = await self._get_edge_repo()
        
        for existing in existing_memories:
            if existing.id == new_memory.id:
                continue
            
            # Determine edge type based on memory types
            edge_type = self._determine_edge_type(new_memory, existing)
            
            # Create edge
            edge_create = EdgeCreate(
                user_id=user_id,
                from_node_id=new_memory.id,
                to_node_id=existing.id,
                edge_type=edge_type,
                strength=similarity_threshold,
                confidence=0.8,
                reason="Automatically linked based on similarity",
            )
            
            try:
                edge = await repo.create(edge_create)
                edges.append(edge)
            except Exception as e:
                # May fail on duplicate - that's OK
                logger.debug("Edge creation skipped", error=str(e))
        
        return edges
    
    async def get_related_memories(
        self,
        user_id: UUID,
        memory_id: UUID,
        depth: int = 2,
        min_strength: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Get memories related to a given memory through the graph.
        
        Args:
            user_id: User ID for isolation
            memory_id: Starting memory
            depth: How many hops to traverse
            min_strength: Minimum edge strength
            
        Returns:
            List of related memory info with relationship details
        """
        repo = await self._get_edge_repo()
        edges_with_nodes = await repo.get_related_memories(
            memory_id=memory_id,
            user_id=user_id,
            depth=depth,
            min_strength=min_strength,
        )
        
        return [
            {
                "memory_id": str(e.to_node_id),
                "content_preview": e.to_node_content[:200] if e.to_node_content else "",
                "edge_type": e.edge_type.value,
                "strength": e.strength,
            }
            for e in edges_with_nodes
        ]
    
    async def get_evolution_timeline(
        self,
        user_id: UUID,
        entity_name: str,
        time_window: str = "all_time",
    ) -> list[dict[str, Any]]:
        """
        Get the evolution timeline for an entity.
        
        Tracks how mentions of an entity changed over time.
        
        Args:
            user_id: User ID
            entity_name: Entity to track
            time_window: Time filter
            
        Returns:
            Timeline of evolution events
        """
        memory_repo = await self._get_memory_repo()
        edge_repo = await self._get_edge_repo()
        
        # Get date filter
        date_filter = self._get_date_filter(time_window)
        
        # Find all memories mentioning this entity
        all_memories = await memory_repo.list_by_user(
            user_id=user_id,
            limit=500,
        )
        
        # Filter by entity and date
        entity_lower = entity_name.lower()
        relevant_memories = []
        
        for m in all_memories:
            # Check entities list
            if any(entity_lower in e.lower() for e in m.entities):
                if date_filter is None or m.created_at >= date_filter:
                    relevant_memories.append(m)
            # Check content
            elif entity_lower in m.content.lower():
                if date_filter is None or m.created_at >= date_filter:
                    relevant_memories.append(m)
        
        # Sort by date
        relevant_memories.sort(key=lambda m: m.created_at)
        
        # Build timeline
        timeline: list[dict[str, Any]] = []
        prev_memory: Memory | None = None
        
        for memory in relevant_memories:
            event = {
                "date": memory.created_at.isoformat(),
                "memory_id": str(memory.id),
                "content_summary": memory.content[:100],
                "memory_type": memory.memory_type.value,
                "importance": memory.importance,
            }
            
            # Determine change type
            if prev_memory is None:
                event["change_type"] = "introduced"
            else:
                # Check if there's an evolution edge
                edges = await edge_repo.get_edges_from_memory(
                    memory_id=prev_memory.id,
                    user_id=user_id,
                )
                
                evolution_edge = next(
                    (e for e in edges if e.to_node_id == memory.id and e.edge_type == EdgeType.EVOLVES_INTO),
                    None
                )
                
                if evolution_edge:
                    event["change_type"] = "evolved"
                elif memory.importance > prev_memory.importance:
                    event["change_type"] = "strengthened"
                elif memory.importance < prev_memory.importance:
                    event["change_type"] = "weakened"
                else:
                    event["change_type"] = "mentioned"
            
            timeline.append(event)
            prev_memory = memory
        
        return timeline
    
    async def find_contradictions(
        self,
        user_id: UUID,
        memory_id: UUID,
    ) -> list[KnowledgeEdge]:
        """Find memories that contradict the given memory."""
        repo = await self._get_edge_repo()
        
        # Get edges of type CONTRADICTS
        from_edges = await repo.get_edges_from_memory(
            memory_id=memory_id,
            user_id=user_id,
            edge_type=EdgeType.CONTRADICTS,
        )
        
        to_edges = await repo.get_edges_to_memory(
            memory_id=memory_id,
            user_id=user_id,
            edge_type=EdgeType.CONTRADICTS,
        )
        
        return from_edges + to_edges
    
    async def mark_superseded(
        self,
        user_id: UUID,
        old_memory_id: UUID,
        new_memory_id: UUID,
        reason: str | None = None,
    ) -> KnowledgeEdge:
        """
        Mark that one memory has been superseded by another.
        
        Creates an EVOLVES_INTO edge.
        """
        return await self.create_edge(
            user_id=user_id,
            from_memory_id=old_memory_id,
            to_memory_id=new_memory_id,
            edge_type=EdgeType.EVOLVES_INTO,
            strength=1.0,
            confidence=0.95,
            reason=reason or "Memory superseded by newer version",
            causality=True,
        )
    
    async def delete_edges_for_memory(
        self,
        user_id: UUID,
        memory_id: UUID,
    ) -> int:
        """Delete all edges connected to a memory."""
        repo = await self._get_edge_repo()
        count = await repo.delete_for_memory(memory_id, user_id)
        logger.info("Edges deleted for memory", memory_id=str(memory_id), count=count)
        return count
    
    def _determine_edge_type(
        self,
        new_memory: Memory,
        existing_memory: Memory,
    ) -> EdgeType:
        """Determine appropriate edge type between two memories."""
        # Preferences relating to preferences might indicate evolution
        if (new_memory.memory_type == MemoryType.PREFERENCE and 
            existing_memory.memory_type == MemoryType.PREFERENCE):
            # If similar entities, might be evolution
            common_entities = set(new_memory.entities) & set(existing_memory.entities)
            if common_entities:
                return EdgeType.EVOLVES_INTO
        
        # Default to related
        return EdgeType.RELATED_TO
    
    def _get_date_filter(self, time_window: str) -> datetime | None:
        """Convert time window string to datetime filter."""
        now = datetime.utcnow()
        windows = {
            "last_7_days": now - timedelta(days=7),
            "last_30_days": now - timedelta(days=30),
            "last_year": now - timedelta(days=365),
            "all_time": None,
        }
        return windows.get(time_window)


# Singleton instance
_knowledge_graph: KnowledgeGraphManager | None = None


async def get_knowledge_graph() -> KnowledgeGraphManager:
    """Get or create the global knowledge graph manager."""
    global _knowledge_graph
    
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraphManager()
    
    return _knowledge_graph
