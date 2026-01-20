"""
Memory Processor

Processes different memory types and handles memory creation.
"""

from datetime import datetime
from uuid import UUID

from src.config import Settings, get_settings
import structlog

from src.models.memory import (
    Memory,
    MemoryCreate,
    MemorySource,
    MemoryType,
    MemoryStatus,
    MemoryUpdate,
)
from src.models.edge import EdgeCreate, EdgeType
from src.storage.repositories.edge_repo import EdgeRepository
from src.services.embedding import EmbeddingService, get_embedding_service
from src.storage.cache import CacheService, get_cache
from src.storage.database import Database, get_database
from src.storage.repositories.memory_repo import MemoryRepository
from src.services.llm import get_llm_service
from src.services.entity_hub_service import get_entity_hub_service

logger = structlog.get_logger(__name__)


class MemoryProcessor:
    """
    Processor for creating and managing memories.
    
    Handles:
    - Memory type classification
    - Embedding generation
    - Importance calculation
    - Memory persistence
    """
    
    # Default importance by memory type
    DEFAULT_IMPORTANCE = {
        MemoryType.EPISODIC: 5,
        MemoryType.SEMANTIC: 6,
        MemoryType.PREFERENCE: 8,
        MemoryType.PROCEDURAL: 7,
        MemoryType.META: 7,
    }
    
    def __init__(
        self,
        db: Database | None = None,
        embedding_service: EmbeddingService | None = None,
        cache: CacheService | None = None,
    ):
        self._db = db
        self._embedding_service = embedding_service
        self._cache = cache
        self._memory_repo: MemoryRepository | None = None
    
    async def _get_db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def _get_embedding_service(self) -> EmbeddingService:
        """Get embedding service instance."""
        if self._embedding_service is None:
            self._embedding_service = await get_embedding_service()
        return self._embedding_service
    
    async def _get_cache(self) -> CacheService:
        """Get cache instance."""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache
    
    async def _get_memory_repo(self) -> MemoryRepository:
        """Get memory repository instance."""
        if self._memory_repo is None:
            db = await self._get_db()
            self._memory_repo = MemoryRepository(db)
        return self._memory_repo
    
    async def process_memory(
        self,
        user_id: UUID,
        content: str,
        memory_type: MemoryType,
        entities: list[str] | None = None,
        importance: int | None = None,
        confidence: float = 0.8,
        source: MemorySource = MemorySource.CONVERSATION,
        source_id: str | None = None,
        metadata: dict | None = None,
        embedding: list[float] | None = None,
        domain: str | None = None,
        category: str | None = None,
        skip_entity_extraction: bool = False,
    ) -> tuple[Memory, str]:
        """
        Process and create a new memory.

        Steps:
        1. Generate embedding (if not provided)
        2. Calculate importance if not provided
        3. Classify content (domain/category) if not provided
        4. Detect duplicates/conflicts (Hygiene)
        5. Extract and link entities (Graph)
        6. Persist to database
        7. Invalidate cache

        Args:
            user_id: Owner user ID
            content: Memory content
            memory_type: Type of memory
            entities: Optional pre-extracted entities
            importance: Optional importance override
            confidence: Confidence score
            source: Memory source
            source_id: Reference ID
            metadata: Additional metadata
            embedding: Optional pre-computed embedding
            domain: Optional pre-classified domain
            category: Optional pre-classified category
            skip_entity_extraction: Skip automated graph linking (useful for imports)

        Returns:
            tuple of (Memory, status string)
            status can be: "created", "updated", "refined"
        """
        logger.info(
            "Processing memory",
            user_id=str(user_id),
            memory_type=memory_type.value,
            content_length=len(content),
        )

        # 1. Generate embedding if not provided
        if embedding is None:
            embedding_service = await self._get_embedding_service()
            embedding = await embedding_service.embed(content)

        # 2. Calculate importance if not provided
        if importance is None:
            importance = self._calculate_importance(content, memory_type, entities)

        # 3. Classify content (Semantic Space) if not provided
        if not domain or not category:
            from src.services.llm import get_llm_service
            try:
                llm_service = await get_llm_service()
                # If we're missing classification, we try to get it
                classification = await llm_service.classify_content(content)
                domain = domain or classification.get("domain")
                category = category or classification.get("category")
            except Exception as e:
                logger.warning("Classification failed", error=str(e))
        
        # Normalize classification
        domain = domain.strip().title() if domain else None
        category = category.strip().title() if category else None

        # --- 4. Hygiene Section: Deduplication & Conflict Detection ---
        repo = await self._get_memory_repo()
        
        # Search for similar existing memories
        similar_memories = await repo.search_similar(embedding, user_id, limit=3)
        
        for sim in similar_memories:
            # A. Exact or near-exact duplicate (> 0.95 similarity)
            if sim.similarity > 0.95:
                logger.info(
                    "Duplicate memory detected - updating existing",
                    existing_id=str(sim.id),
                    similarity=sim.similarity
                )
                # Incremental update
                update_data = MemoryUpdate(access_count=sim.access_count + 1)
                updated = await repo.update(sim.id, user_id, update_data)
                
                # Invalidate user cache
                cache = await self._get_cache()
                await cache.invalidate_user_cache(str(user_id))
                
                return updated if updated else sim, "updated"

            # B. Potential conflict (using configured threshold for LLM check)
            settings = get_settings()
            if sim.similarity > settings.consolidation_conflict_threshold_low:
                # Late import to avoid circular dependency
                from src.services.llm import get_llm_service
                llm_service = await get_llm_service()
                is_contradiction = await llm_service.check_for_contradiction(sim.content, content)
                
                if is_contradiction:
                    logger.info(
                        "Logical contradiction detected - triggering automatic refinement",
                        old_id=str(sim.id),
                        similarity=sim.similarity
                    )
                    memory = await self._refine_existing_memory(
                        user_id=user_id,
                        old_memory=sim,
                        new_content=content,
                        new_memory_type=memory_type,
                        new_embedding=embedding,
                        new_entities=entities,
                        new_domain=domain,
                        new_category=category,
                        new_importance=importance,
                        new_source=source,
                        new_source_id=source_id,
                        new_metadata=metadata
                    )
                    return memory, "refined"

        # --- 5. Extract and link entities (Graph Navigation) ---
        extracted_entities = entities or []
        entity_records = []
        
        if not skip_entity_extraction:
            try:
                from src.services.entity_hub_service import get_entity_hub_service
                entity_hub_service = await get_entity_hub_service()
                
                # Extrahiere und lerne neue Entitäten
                extraction_result = await entity_hub_service.extract_and_learn(user_id, content)
                entity_records = extraction_result.entities
                
                # Merge mit übergebenen Entitäten
                learned_names = [e.name for e in entity_records]
                for name in learned_names:
                    if name not in extracted_entities:
                        extracted_entities.append(name)
            except Exception as e:
                logger.warning("Entity extraction/linking failed", error=str(e))

        # 6. Create memory
        memory_create = MemoryCreate(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            entities=extracted_entities,
            domain=domain,
            category=category,
            importance=importance,
            confidence=confidence,
            source=source,
            source_id=source_id,
            metadata=metadata or {},
        )

        # Persist
        memory = await repo.create(memory_create)

        # --- 7. Graph Linking: Connect memory to entity hubs ---
        if entity_records:
            try:
                await entity_hub_service.link_memory_to_entities(
                    memory=memory,
                    entities=entity_records,
                )
            except Exception as e:
                logger.warning("Graph linking failed", error=str(e))

        # Invalidate cache
        cache = await self._get_cache()
        await cache.invalidate_user_cache(str(user_id))

        logger.info(
            "Memory created successfully",
            memory_id=str(memory.id),
            memory_type=memory_type.value,
            importance=importance,
            entities_count=len(extracted_entities),
        )

        return memory, "created"

    async def process_memories_batch(
        self,
        user_id: UUID,
        memory_data: list[dict],
    ) -> list[Memory]:
        """
        Process multiple memories in batch for better performance.

        Args:
            user_id: Owner user ID
            memory_data: List of memory data dicts with keys:
                content, memory_type, entities, importance, confidence, source, source_id, metadata, embedding (optional)

        Returns:
            List of created Memory objects
        """
        if not memory_data:
            return []

        logger.info(
            "Processing memories batch",
            user_id=str(user_id),
            count=len(memory_data),
        )

        # Separate data with and without embeddings
        data_with_embeddings = [d for d in memory_data if d.get("embedding")]
        data_without_embeddings = [d for d in memory_data if not d.get("embedding")]

        # Generate embeddings for data without them
        embedding_service = await self._get_embedding_service()
        embeddings = []

        if data_without_embeddings:
            contents = [data["content"] for data in data_without_embeddings]
            batch_embeddings = await embedding_service.embed_batch(contents)
            embeddings.extend(batch_embeddings)

        # Combine all embeddings in original order
        all_embeddings = []
        embed_idx = 0

        for data in memory_data:
            if data.get("embedding"):
                all_embeddings.append(data["embedding"])
            else:
                all_embeddings.append(embeddings[embed_idx])
                embed_idx += 1

        # Process each memory
        memories = []
        for i, data in enumerate(memory_data):
            memory_type = data["memory_type"]
            content = data["content"]

            # Calculate importance if not provided
            importance = data.get("importance")
            if importance is None:
                importance = self._calculate_importance(
                    content, memory_type, data.get("entities")
                )

            # Create memory
            memory_create = MemoryCreate(
                user_id=user_id,
                content=content,
                memory_type=memory_type,
                embedding=all_embeddings[i],
                entities=data.get("entities", []),
                domain=data.get("domain"),
                category=data.get("category"),
                importance=importance,
                confidence=data.get("confidence", 0.8),
                source=data.get("source", MemorySource.CONVERSATION),
                source_id=data.get("source_id"),
                metadata=data.get("metadata", {}),
            )

            # Persist
            repo = await self._get_memory_repo()
            memory = await repo.create(memory_create)
            memories.append(memory)

        # Invalidate user cache once for all
        cache = await self._get_cache()
        await cache.invalidate_user_cache(str(user_id))

        logger.info(
            "Batch memory creation completed",
            count=len(memories),
            user_id=str(user_id),
        )

        return memories
    
    async def process_episodic(
        self,
        user_id: UUID,
        content: str,
        entities: list[str] | None = None,
        **kwargs,
    ) -> tuple[Memory, str]:
        """
        Process an episodic memory (specific event/conversation).
        
        Example: "In session #42, user mentioned preferring async/await"
        """
        return await self.process_memory(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.EPISODIC,
            entities=entities,
            **kwargs,
        )
    
    async def process_semantic(
        self,
        user_id: UUID,
        content: str,
        entities: list[str] | None = None,
        **kwargs,
    ) -> tuple[Memory, str]:
        """
        Process a semantic memory (facts and relationships).
        
        Example: "TypeScript is a superset of JavaScript"
        """
        return await self.process_memory(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.SEMANTIC,
            entities=entities,
            **kwargs,
        )
    
    async def process_preference(
        self,
        user_id: UUID,
        content: str,
        entities: list[str] | None = None,
        **kwargs,
    ) -> tuple[Memory, str]:
        """
        Process a preference memory (user preferences).
        
        Example: "User prefers async/await over callbacks"
        """
        # Preferences are generally more important
        importance = kwargs.pop("importance", None) or 8
        
        return await self.process_memory(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.PREFERENCE,
            entities=entities,
            importance=importance,
            **kwargs,
        )
    
    async def process_procedural(
        self,
        user_id: UUID,
        content: str,
        entities: list[str] | None = None,
        **kwargs,
    ) -> tuple[Memory, str]:
        """
        Process a procedural memory (how-to knowledge).
        
        Example: "To setup React with TypeScript: npm create vite --template react-ts"
        """
        return await self.process_memory(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.PROCEDURAL,
            entities=entities,
            **kwargs,
        )
    
    async def process_meta(
        self,
        user_id: UUID,
        content: str,
        entities: list[str] | None = None,
        **kwargs,
    ) -> tuple[Memory, str]:
        """
        Process a meta-cognitive memory (knowledge about the user's knowledge).
        
        Example: "User is struggling with async/await concepts"
        """
        return await self.process_memory(
            user_id=user_id,
            content=content,
            memory_type=MemoryType.META,
            entities=entities,
            **kwargs,
        )
    
    def _calculate_importance(
        self,
        content: str,
        memory_type: MemoryType,
        entities: list[str] | None = None,
    ) -> int:
        """
        Calculate importance score based on content and type.
        
        Factors:
        - Base importance by type
        - Content length (longer = potentially more detailed)
        - Number of entities (more entities = more connections)
        """
        # Start with default for type
        base = self.DEFAULT_IMPORTANCE.get(memory_type, 5)
        
        # Adjust based on content length
        if len(content) > 500:
            base += 1
        elif len(content) < 50:
            base -= 1
        
        # Adjust based on entities
        if entities:
            if len(entities) >= 3:
                base += 1
            elif len(entities) >= 5:
                base += 2
        
        # Clamp to valid range
        return max(1, min(10, base))
    
    def infer_memory_type(self, content: str, claim_type: str | None = None) -> MemoryType:
        """
        Infer memory type from content and optional claim type.
        
        Args:
            content: Memory content
            claim_type: Claim type from extraction (if available)
            
        Returns:
            Inferred MemoryType
        """
        # Map claim types to memory types
        if claim_type:
            type_mapping = {
                "preference": MemoryType.PREFERENCE,
                "fact": MemoryType.SEMANTIC,
                "learning": MemoryType.EPISODIC,
                "decision": MemoryType.EPISODIC,
                "how_to": MemoryType.PROCEDURAL,
                "struggle": MemoryType.META,
            }
            if claim_type in type_mapping:
                return type_mapping[claim_type]
        
        # Heuristic based on content
        content_lower = content.lower()
        
        # Preference indicators
        preference_keywords = [
            "prefer", "like", "love", "hate", "dislike",
            "favorite", "rather", "always use", "never use",
            "better than", "instead of",
        ]
        if any(kw in content_lower for kw in preference_keywords):
            return MemoryType.PREFERENCE
        
        # Procedural indicators
        procedural_keywords = [
            "how to", "step by step", "to do this",
            "first,", "then,", "finally,",
            "run", "execute", "install", "configure",
        ]
        if any(kw in content_lower for kw in procedural_keywords):
            return MemoryType.PROCEDURAL
        
        # Meta-cognitive indicators
        meta_keywords = [
            "struggling with", "confused about", "learning",
            "don't understand", "trying to figure out",
            "getting better at", "expertise in",
        ]
        if any(kw in content_lower for kw in meta_keywords):
            return MemoryType.META
        
        # Episodic indicators (specific events)
        episodic_keywords = [
            "today", "yesterday", "last week",
            "during the session", "mentioned that",
            "said that", "told me",
        ]
        if any(kw in content_lower for kw in episodic_keywords):
            return MemoryType.EPISODIC
        
        # Default to semantic
        return MemoryType.SEMANTIC

    async def _refine_existing_memory(
        self,
        user_id: UUID,
        old_memory: Memory,
        new_content: str,
        new_memory_type: MemoryType,
        new_embedding: list[float],
        new_entities: list[str] | None,
        new_domain: str | None,
        new_category: str | None,
        new_importance: int,
        new_source: MemorySource,
        new_source_id: str | None,
        new_metadata: dict | None
    ) -> Memory:
        """
        Internal helper to refine an existing memory automatically.
        Archives the old one as SUPERSEDED and creates a new one with EVOLVES_INTO edge.
        """
        db = await self._get_db()
        memory_repo = await self._get_memory_repo()
        edge_repo = EdgeRepository(db)
        
        # 1. Create the new memory record
        new_memory_create = MemoryCreate(
            user_id=user_id,
            content=new_content,
            memory_type=new_memory_type,
            embedding=new_embedding,
            entities=new_entities or [],
            domain=new_domain or old_memory.domain,
            category=new_category or old_memory.category,
            importance=new_importance,
            confidence=1.0,  # High confidence for explicit updates
            source=new_source,
            source_id=new_source_id,
            metadata={
                **(new_metadata or {}),
                "refined_automatically": True,
                "refined_from": str(old_memory.id)
            }
        )
        new_memory = await memory_repo.create(new_memory_create)
        
        # 2. Link new memory to entities (via entity hub service)
        try:
            entity_hub_service = await get_entity_hub_service()
            # We assume extraction happened before calling this, or we learned them
            # Let's verify entities are learned if they were provided
            if new_entities:
                 learn_result = await entity_hub_service.extract_and_learn(user_id, new_content)
                 await entity_hub_service.link_memory_to_entities(
                    memory=new_memory,
                    entities=learn_result.entities,
                )
        except Exception as e:
            logger.warning("Entity linking in auto-refinement failed", error=str(e))

        # 3. Update old memory status to SUPERSEDED
        await memory_repo.update(old_memory.id, user_id, MemoryUpdate(
            status=MemoryStatus.SUPERSEDED,
            superseded_by=new_memory.id
        ))
        
        # 4. Create EVOLVES_INTO edge in graph
        edge_create = EdgeCreate(
            user_id=user_id,
            from_node_id=old_memory.id,
            to_node_id=new_memory.id,
            edge_type=EdgeType.EVOLVES_INTO,
            strength=1.0,
            confidence=1.0,
            reason="Automated conflict resolution - Knowledge evolution",
            metadata={"auto_generated": True, "type": "hygiene_refinement"}
        )
        await edge_repo.create(edge_create)
        
        # 5. Invalidate user cache
        cache = await self._get_cache()
        await cache.invalidate_user_cache(str(user_id))
        
        return new_memory
