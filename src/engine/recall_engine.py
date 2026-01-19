"""
Recall Engine

Graph-enhanced recall with learning capabilities.
This engine provides intelligent memory retrieval that uses:
- Vector similarity search (primary)
- Evolution awareness (EVOLVES_INTO edges filter obsolete memories)
- Entity-based expansion (via Entity Hubs)
- Recency and access frequency boosts
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.models.edge import EdgeType
from src.models.memory import Memory, MemoryWithSimilarity
from src.models.requests import RecallFilters
from src.services.embedding import EmbeddingService, get_embedding_service
from src.storage.database import Database, get_database
from src.storage.repositories.edge_repo import EdgeRepository
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


class EnhancedRecallResult:
    """Enhanced recall result with context about how memories were found."""
    
    def __init__(
        self,
        memories: list[MemoryWithSimilarity],
        query: str,
        total_available: int,
        search_time_ms: int,
        evolution_filtered_count: int = 0,
        entity_expanded_count: int = 0,
    ):
        self.memories = memories
        self.query = query
        self.count = len(memories)
        self.total_available = total_available
        self.search_time_ms = search_time_ms
        self.evolution_filtered_count = evolution_filtered_count
        self.entity_expanded_count = entity_expanded_count


class RecallEngine:
    """
    Graph-enhanced recall with learning capabilities.
    
    Algorithm:
    1. Vector similarity search (core retrieval)
    2. Evolution Check: Filter out memories with outgoing EVOLVES_INTO edges
    3. Entity Expansion: Via Entity Hubs find additional related memories
    4. Recency Boost: Recently accessed memories get higher scores
    5. Access Frequency: Often-accessed memories are prioritized
    
    The engine respects the knowledge graph to provide smarter recall
    that mimics how human memory works - associative, evolving, and
    learning from usage patterns.
    """
    
    def __init__(
        self,
        db: Database | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self._db = db
        self._embedding_service = embedding_service
        self._memory_repo: MemoryRepository | None = None
        self._edge_repo: EdgeRepository | None = None
    
    async def _get_db(self) -> Database:
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = await get_embedding_service()
        return self._embedding_service
    
    async def _get_memory_repo(self) -> MemoryRepository:
        if self._memory_repo is None:
            db = await self._get_db()
            self._memory_repo = MemoryRepository(db)
        return self._memory_repo
    
    async def _get_edge_repo(self) -> EdgeRepository:
        if self._edge_repo is None:
            db = await self._get_db()
            self._edge_repo = EdgeRepository(db)
        return self._edge_repo
    
    async def recall(
        self,
        user_id: UUID,
        query: str,
        filters: RecallFilters | None = None,
        limit: int = 10,
        offset: int = 0,
        # Graph-enhanced options
        respect_evolution: bool = True,
        expand_entities: bool = True,
        include_related: bool = False,
        # Learning options
        apply_recency_boost: bool = True,
    ) -> EnhancedRecallResult:
        """
        Perform graph-enhanced recall.
        
        Args:
            user_id: User ID for memory isolation
            query: Natural language search query
            filters: Optional filters (memory_type, entity, date_range, importance_min)
            limit: Maximum results to return
            offset: Pagination offset
            respect_evolution: If True, filter out memories superseded by newer versions
            expand_entities: If True, include memories that share entities with top results
            include_related: If True, include memories connected via RELATED_TO edges
            apply_recency_boost: If True, boost recently accessed memories
            
        Returns:
            EnhancedRecallResult with memories and metadata
        """
        import time
        start_time = time.time()
        
        logger.info(
            "RecallEngine.recall started",
            user_id=str(user_id),
            query=query[:100],
            respect_evolution=respect_evolution,
            expand_entities=expand_entities,
        )
        
        # Step 1: Generate query embedding
        embedding_service = await self._get_embedding_service()
        query_embedding = await embedding_service.embed(query)
        
        # Step 2: Primary vector search (fetch more than needed for filtering)
        memory_repo = await self._get_memory_repo()
        
        # Request extra results to allow for filtering
        search_limit = limit * 2 if respect_evolution else limit
        
        primary_results = await memory_repo.search_similar(
            embedding=query_embedding,
            user_id=user_id,
            limit=search_limit,
            memory_type=filters.memory_type if filters else None,
            min_importance=filters.importance_min if filters else None,
            entity=filters.entity if filters else None,
            date_range=filters.date_range.value if filters and filters.date_range else None,
        )
        
        # Step 3: Filter evolved memories
        evolution_filtered_count = 0
        if respect_evolution and primary_results:
            primary_results, evolution_filtered_count = await self._filter_evolved_memories(
                memories=primary_results,
                user_id=user_id,
            )
        
        # Step 4: Entity expansion (add memories that share entities)
        entity_expanded_count = 0
        if expand_entities and primary_results and len(primary_results) < limit:
            expanded_memories, entity_expanded_count = await self._expand_via_entities(
                seed_memories=primary_results,
                user_id=user_id,
                max_additional=limit - len(primary_results),
            )
            primary_results.extend(expanded_memories)
        
        # Step 5: Include related memories via edges
        if include_related and primary_results and len(primary_results) < limit:
            related_memories = await self._get_graph_related_memories(
                seed_memories=primary_results,
                user_id=user_id,
                max_additional=limit - len(primary_results),
            )
            primary_results.extend(related_memories)
        
        # Step 6: Apply recency boost (re-rank based on access patterns)
        if apply_recency_boost:
            primary_results = self._apply_recency_boost(primary_results)
        
        # Step 7: Apply offset and limit
        if offset > 0:
            primary_results = primary_results[offset:]
        primary_results = primary_results[:limit]
        
        # Step 8: Update access timestamps
        for memory in primary_results:
            await memory_repo._update_access(memory.id)
        
        # Get total count
        total_available = await memory_repo.count_by_user(user_id)
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "RecallEngine.recall completed",
            results_count=len(primary_results),
            evolution_filtered=evolution_filtered_count,
            entity_expanded=entity_expanded_count,
            search_time_ms=search_time_ms,
        )
        
        return EnhancedRecallResult(
            memories=primary_results,
            query=query,
            total_available=total_available,
            search_time_ms=search_time_ms,
            evolution_filtered_count=evolution_filtered_count,
            entity_expanded_count=entity_expanded_count,
        )
    
    async def _filter_evolved_memories(
        self,
        memories: list[MemoryWithSimilarity],
        user_id: UUID,
    ) -> tuple[list[MemoryWithSimilarity], int]:
        """
        Filter out memories that have been superseded by newer versions.
        
        A memory is superseded if it has an outgoing EVOLVES_INTO edge.
        The target memory (newer version) is preferred.
        
        Returns:
            (filtered_memories, count_of_filtered)
        """
        if not memories:
            return memories, 0
        
        edge_repo = await self._get_edge_repo()
        memory_ids = {m.id for m in memories}
        
        # Find memories that have outgoing EVOLVES_INTO edges
        obsolete_ids: set[UUID] = set()
        
        for memory in memories:
            edges = await edge_repo.get_edges_from_memory(
                memory_id=memory.id,
                user_id=user_id,
                edge_type=EdgeType.EVOLVES_INTO,
            )
            
            if edges:
                # This memory has evolved into something newer
                obsolete_ids.add(memory.id)
                
                # Check if the newer version is already in results
                newer_ids = {e.to_node_id for e in edges}
                if not newer_ids.intersection(memory_ids):
                    # The newer version is NOT in results - we should warn
                    logger.debug(
                        "Memory has newer version not in results",
                        obsolete_id=str(memory.id),
                        newer_ids=[str(nid) for nid in newer_ids],
                    )
        
        # Filter out obsolete memories
        filtered = [m for m in memories if m.id not in obsolete_ids]
        filtered_count = len(memories) - len(filtered)
        
        if filtered_count > 0:
            logger.info(
                "Filtered evolved memories",
                filtered_count=filtered_count,
                remaining_count=len(filtered),
            )
        
        return filtered, filtered_count
    
    async def _expand_via_entities(
        self,
        seed_memories: list[MemoryWithSimilarity],
        user_id: UUID,
        max_additional: int = 5,
    ) -> tuple[list[MemoryWithSimilarity], int]:
        """
        Find additional memories that share entities with the seed memories.
        
        Uses the memory_entity_links table to find memories linked
        to the same Entity Hubs.
        
        Returns:
            (additional_memories, count_added)
        """
        if not seed_memories or max_additional <= 0:
            return [], 0
        
        db = await self._get_db()
        memory_repo = await self._get_memory_repo()
        
        # Collect all entities from seed memories
        seed_ids = {m.id for m in seed_memories}
        seed_entities: set[str] = set()
        
        for memory in seed_memories:
            seed_entities.update(e.lower() for e in memory.entities)
        
        if not seed_entities:
            return [], 0
        
        # Find memories that share these entities (via memory_entity_links)
        query = """
            SELECT DISTINCT m.id
            FROM memory_entity_links mel
            JOIN entity_hubs eh ON eh.id = mel.entity_id
            JOIN memories m ON m.id = mel.memory_id
            WHERE mel.user_id = $1
              AND LOWER(eh.entity_name) = ANY($2)
              AND m.status = 'active'
              AND m.id != ALL($3)
            LIMIT $4
        """
        
        rows = await db.fetch(
            query,
            user_id,
            list(seed_entities),
            list(seed_ids),
            max_additional,
        )
        
        if not rows:
            return [], 0
        
        # Fetch full memory objects
        additional_memories: list[MemoryWithSimilarity] = []
        for row in rows:
            memory = await memory_repo.get_by_id(row["id"], user_id)
            if memory:
                # Wrap as MemoryWithSimilarity with lower similarity score
                mem_with_sim = MemoryWithSimilarity(
                    **memory.model_dump(exclude={'embedding'}),
                    similarity=0.5,  # Lower score for entity-expanded results
                )
                additional_memories.append(mem_with_sim)
        
        return additional_memories, len(additional_memories)
    
    async def _get_graph_related_memories(
        self,
        seed_memories: list[MemoryWithSimilarity],
        user_id: UUID,
        max_additional: int = 5,
    ) -> list[MemoryWithSimilarity]:
        """
        Find memories connected to seeds via RELATED_TO or DEPENDS_ON edges.
        
        Returns:
            List of related memories (may be empty)
        """
        if not seed_memories or max_additional <= 0:
            return []
        
        edge_repo = await self._get_edge_repo()
        memory_repo = await self._get_memory_repo()
        
        seed_ids = {m.id for m in seed_memories}
        related_ids: set[UUID] = set()
        
        # Get edges from seed memories
        for memory in seed_memories[:3]:  # Limit to top 3 to avoid explosion
            edges = await edge_repo.get_edges_from_memory(
                memory_id=memory.id,
                user_id=user_id,
            )
            
            for edge in edges:
                if edge.edge_type in (EdgeType.RELATED_TO, EdgeType.DEPENDS_ON, EdgeType.SUPPORTS):
                    if edge.to_node_id not in seed_ids:
                        related_ids.add(edge.to_node_id)
                        if len(related_ids) >= max_additional:
                            break
            
            if len(related_ids) >= max_additional:
                break
        
        # Fetch full memory objects
        related_memories: list[MemoryWithSimilarity] = []
        for memory_id in list(related_ids)[:max_additional]:
            memory = await memory_repo.get_by_id(memory_id, user_id)
            if memory:
                mem_with_sim = MemoryWithSimilarity(
                    **memory.model_dump(exclude={'embedding'}),
                    similarity=0.4,  # Lower score for graph-related results
                )
                related_memories.append(mem_with_sim)
        
        return related_memories
    
    def _apply_recency_boost(
        self,
        memories: list[MemoryWithSimilarity],
    ) -> list[MemoryWithSimilarity]:
        """
        Re-rank memories based on recency and access patterns.
        
        Boost formula:
        - Recently accessed (< 24h): +0.10
        - Recently accessed (< 7d): +0.05
        - High access count (> 10): +0.05
        
        Final score = similarity + boosts (capped at 1.0)
        """
        if not memories:
            return memories
        
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        
        boosted = []
        for memory in memories:
            boost = 0.0
            
            # Recency boost
            if memory.last_accessed:
                # Handle both timezone-aware and naive datetimes
                last_accessed = memory.last_accessed
                if last_accessed.tzinfo is None:
                    # Make naive datetime UTC-aware
                    last_accessed = last_accessed.replace(tzinfo=timezone.utc)
                
                age = now - last_accessed
                if age < timedelta(hours=24):
                    boost += 0.10
                elif age < timedelta(days=7):
                    boost += 0.05
            
            # Access frequency boost
            if memory.access_count and memory.access_count > 10:
                boost += 0.05
            
            # Apply boost to similarity
            boosted_similarity = min(1.0, memory.similarity + boost)
            
            # Create new object with boosted similarity
            boosted_memory = MemoryWithSimilarity(
                **{k: v for k, v in memory.model_dump(exclude={'embedding'}).items() if k != 'similarity'},
                similarity=boosted_similarity,
            )
            boosted.append(boosted_memory)
        
        # Re-sort by boosted similarity
        boosted.sort(key=lambda m: m.similarity, reverse=True)
        
        return boosted


# Singleton instance
_recall_engine: RecallEngine | None = None


async def get_recall_engine() -> RecallEngine:
    """Get or create the global recall engine."""
    global _recall_engine
    
    if _recall_engine is None:
        _recall_engine = RecallEngine()
    
    return _recall_engine
