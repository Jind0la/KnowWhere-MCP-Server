"""
Memory Processor

Processes different memory types and handles memory creation.
"""

from datetime import datetime
from uuid import UUID

import structlog

from src.models.memory import (
    Memory,
    MemoryCreate,
    MemorySource,
    MemoryType,
)
from src.services.embedding import EmbeddingService, get_embedding_service
from src.storage.cache import CacheService, get_cache
from src.storage.database import Database, get_database
from src.storage.repositories.memory_repo import MemoryRepository

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
    ) -> Memory:
        """
        Process and create a new memory.

        Steps:
        1. Generate embedding
        2. Calculate importance if not provided
        3. Persist to database
        4. Invalidate cache

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

        Returns:
            Created Memory
        """
        logger.info(
            "Processing memory",
            user_id=str(user_id),
            memory_type=memory_type.value,
            content_length=len(content),
        )

        # Generate embedding
        embedding_service = await self._get_embedding_service()
        embedding = await embedding_service.embed(content)

        # Calculate importance if not provided
        if importance is None:
            importance = self._calculate_importance(content, memory_type, entities)

        # Create memory
        memory_create = MemoryCreate(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            entities=entities or [],
            importance=importance,
            confidence=confidence,
            source=source,
            source_id=source_id,
            metadata=metadata or {},
        )

        # Persist
        repo = await self._get_memory_repo()
        memory = await repo.create(memory_create)

        # Invalidate user cache
        cache = await self._get_cache()
        await cache.invalidate_user_cache(str(user_id))

        logger.info(
            "Memory created",
            memory_id=str(memory.id),
            memory_type=memory_type.value,
            importance=importance,
        )

        return memory

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
        
        # Calculate importance if not provided
        if importance is None:
            importance = self._calculate_importance(content, memory_type, entities)
        
        # Create memory
        memory_create = MemoryCreate(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            entities=entities or [],
            importance=importance,
            confidence=confidence,
            source=source,
            source_id=source_id,
            metadata=metadata or {},
        )
        
        # Persist
        repo = await self._get_memory_repo()
        memory = await repo.create(memory_create)
        
        # Invalidate user cache
        cache = await self._get_cache()
        await cache.invalidate_user_cache(str(user_id))
        
        logger.info(
            "Memory created",
            memory_id=str(memory.id),
            memory_type=memory_type.value,
            importance=importance,
        )
        
        return memory
    
    async def process_episodic(
        self,
        user_id: UUID,
        content: str,
        entities: list[str] | None = None,
        **kwargs,
    ) -> Memory:
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
    ) -> Memory:
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
    ) -> Memory:
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
    ) -> Memory:
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
    ) -> Memory:
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
