"""
Consolidation Engine

Processes conversation transcripts and extracts structured memories.
Handles duplicate detection, conflict resolution, and knowledge graph building.
"""

import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.config import Settings, get_settings
from src.engine.entity_extractor import EntityExtractor, get_entity_extractor
from src.engine.knowledge_graph import KnowledgeGraphManager, get_knowledge_graph
from src.engine.memory_processor import MemoryProcessor
from src.models.consolidation import (
    Claim,
    Conflict,
    ConflictResolution,
    ConsolidationHistory,
    ConsolidationResult,
    ConsolidationStatus,
    DuplicateGroup,
)
from src.models.memory import Memory, MemorySource, MemoryType
from src.services.embedding import EmbeddingService, get_embedding_service
from src.services.llm import LLMService, get_llm_service
from src.storage.database import Database, get_database
from src.storage.repositories.consolidation_repo import ConsolidationRepository
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


class ConsolidationEngine:
    """
    Engine for consolidating conversation transcripts into memories.
    
    Algorithm:
    1. Extract claims from transcript using LLM
    2. Generate embeddings for all claims
    3. Detect duplicates (cosine similarity > 0.85)
    4. Detect conflicts (0.5 < cosine < 0.85 with contradiction)
    5. Resolve conflicts using LLM
    6. Extract entities
    7. Calculate importance
    8. Build knowledge graph
    9. Persist memories and edges
    """
    
    def __init__(
        self,
        settings: Settings | None = None,
        db: Database | None = None,
        llm_service: LLMService | None = None,
        embedding_service: EmbeddingService | None = None,
        entity_extractor: EntityExtractor | None = None,
        knowledge_graph: KnowledgeGraphManager | None = None,
    ):
        self.settings = settings or get_settings()
        self._db = db
        self._llm_service = llm_service
        self._embedding_service = embedding_service
        self._entity_extractor = entity_extractor
        self._knowledge_graph = knowledge_graph
        
        # Thresholds from settings
        self.duplicate_threshold = self.settings.consolidation_duplicate_threshold
        self.conflict_threshold_low = self.settings.consolidation_conflict_threshold_low
        self.conflict_threshold_high = self.settings.consolidation_conflict_threshold_high
    
    # Service getters
    async def _get_db(self) -> Database:
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def _get_llm(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = await get_llm_service()
        return self._llm_service
    
    async def _get_embedding(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = await get_embedding_service()
        return self._embedding_service
    
    async def _get_entity_extractor(self) -> EntityExtractor:
        if self._entity_extractor is None:
            self._entity_extractor = await get_entity_extractor()
        return self._entity_extractor
    
    async def _get_knowledge_graph(self) -> KnowledgeGraphManager:
        if self._knowledge_graph is None:
            self._knowledge_graph = await get_knowledge_graph()
        return self._knowledge_graph
    
    async def consolidate(
        self,
        user_id: UUID,
        session_transcript: str,
        conversation_id: str | None = None,
    ) -> ConsolidationResult:
        """
        Consolidate a session transcript into memories.
        
        Args:
            user_id: Owner user ID
            session_transcript: Full conversation transcript
            conversation_id: Optional conversation reference
            
        Returns:
            ConsolidationResult with all processing details
        """
        start_time = time.time()
        consolidation_id = uuid4()
        
        logger.info(
            "Starting consolidation",
            consolidation_id=str(consolidation_id),
            user_id=str(user_id),
            transcript_length=len(session_transcript),
        )
        
        try:
            # Step 1: Extract claims
            llm = await self._get_llm()
            claims = await llm.extract_claims(session_transcript)
            
            if not claims:
                logger.warning("No claims extracted from transcript")
                return self._empty_result(user_id, consolidation_id, len(session_transcript))
            
            logger.info("Claims extracted", count=len(claims))
            
            # Step 2: Generate embeddings
            embedding_service = await self._get_embedding()
            claim_texts = [c.claim for c in claims]
            embeddings = await embedding_service.embed_batch(claim_texts)
            
            # Step 3: Find duplicates
            duplicates = await self._find_duplicates(claims, embeddings)
            
            # Step 4: Find conflicts
            conflicts = await self._find_conflicts(claims, embeddings)
            
            # Step 5: Resolve conflicts
            resolutions = await self._resolve_conflicts(conflicts)
            
            # Step 6: Build final claim list (merged duplicates, resolved conflicts)
            final_claims = self._build_final_claims(claims, duplicates, resolutions)
            
            # Step 7: Extract entities for each claim (parallel)
            entity_extractor = await self._get_entity_extractor()

            # Collect claims that need entity extraction
            claims_needing_entities = [c for c in final_claims if not c.entities]
            if claims_needing_entities:
                # Extract entities in parallel
                claim_texts = [c.claim for c in claims_needing_entities]
                entity_results = await asyncio.gather(*[
                    entity_extractor.extract(text) for text in claim_texts
                ])

                # Assign results back
                for claim, entities in zip(claims_needing_entities, entity_results):
                    claim.entities = entities

            # Step 8: Create memories (parallel batch processing)
            memory_processor = MemoryProcessor()
            created_memories: list[Memory] = []

            # Prepare memory data for batch processing
            memory_batch_data = []
            for claim in final_claims:
                # Determine memory type
                memory_type = memory_processor.infer_memory_type(
                    claim.claim,
                    claim.claim_type
                )

                # Get embedding (reuse if available)
                embedding = embeddings[claims.index(claim)] if claim in claims else None

                memory_batch_data.append({
                    "content": claim.claim,
                    "memory_type": memory_type,
                    "entities": claim.entities,
                    "confidence": claim.confidence,
                    "source": MemorySource.CONSOLIDATION,
                    "source_id": conversation_id,
                    "metadata": {
                        "consolidation_id": str(consolidation_id),
                        "claim_type": claim.claim_type,
                        "source_in_transcript": claim.source,
                    },
                    "embedding": embedding,  # Will be generated if None
                })

            # Process memories in batch
            if memory_batch_data:
                # Group into smaller batches to avoid overwhelming the system
                batch_size = 10
                for i in range(0, len(memory_batch_data), batch_size):
                    batch = memory_batch_data[i:i + batch_size]

                    # For claims without embeddings, generate them
                    claims_without_embeddings = [
                        data for data in batch if data.get("embedding") is None
                    ]

                    if claims_without_embeddings:
                        texts = [data["content"] for data in claims_without_embeddings]
                        batch_embeddings = await embedding_service.embed_batch(texts)

                        # Assign embeddings back
                        for data, emb in zip(claims_without_embeddings, batch_embeddings):
                            data["embedding"] = emb

                    # Use batch processing for memories
                    batch_memories = await memory_processor.process_memories_batch(
                        user_id, batch
                    )
                    created_memories.extend(batch_memories)
            
            # Step 9: Build knowledge graph
            kg = await self._get_knowledge_graph()
            
            # Collect all entities and map to memories
            all_entities = set()
            entity_to_memory: dict[str, UUID] = {}
            
            for memory in created_memories:
                for entity in memory.entities:
                    all_entities.add(entity)
                    entity_to_memory[entity] = memory.id
            
            # Infer relationships
            relationships = await llm.infer_relationships(final_claims, list(all_entities))
            
            # Create edges
            edges = await kg.create_edges_from_relationships(
                user_id=user_id,
                relationships=relationships,
                entity_to_memory=entity_to_memory,
            )
            
            # Step 10: Detect patterns
            patterns = await llm.detect_patterns(final_claims)
            
            # Calculate timing
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create result
            result = ConsolidationResult(
                consolidation_id=consolidation_id,
                user_id=user_id,
                session_transcript_length=len(session_transcript),
                claims_extracted=len(claims),
                new_memories_count=len(created_memories),
                new_memory_ids=[m.id for m in created_memories],
                merged_count=sum(len(d.claims) - 1 for d in duplicates),
                conflicts_resolved=len(resolutions),
                edges_created=len(edges),
                patterns_detected=patterns,
                key_entities=list(all_entities)[:20],
                processing_time_ms=processing_time_ms,
                status=ConsolidationStatus.COMPLETED,
            )
            
            # Save history
            await self._save_history(result, conversation_id)
            
            logger.info(
                "Consolidation completed",
                consolidation_id=str(consolidation_id),
                memories_created=len(created_memories),
                edges_created=len(edges),
                processing_time_ms=processing_time_ms,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Consolidation failed",
                consolidation_id=str(consolidation_id),
                error=str(e),
            )
            
            return ConsolidationResult(
                consolidation_id=consolidation_id,
                user_id=user_id,
                session_transcript_length=len(session_transcript),
                claims_extracted=0,
                new_memories_count=0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                status=ConsolidationStatus.FAILED,
                error_message=str(e),
            )
    
    async def _find_duplicates(
        self,
        claims: list[Claim],
        embeddings: list[list[float]],
    ) -> list[DuplicateGroup]:
        """Find duplicate claims using embedding similarity."""
        embedding_service = await self._get_embedding()
        
        duplicate_pairs = await embedding_service.find_duplicates(
            embeddings,
            threshold=self.duplicate_threshold,
        )
        
        # Group duplicates
        groups: list[DuplicateGroup] = []
        used_indices: set[int] = set()
        
        for i, j, similarity in duplicate_pairs:
            if i in used_indices and j in used_indices:
                continue
            
            # Find or create group
            group_found = False
            for group in groups:
                group_indices = [claims.index(c) for c in group.claims]
                if i in group_indices or j in group_indices:
                    if i not in group_indices:
                        group.claims.append(claims[i])
                        used_indices.add(i)
                    if j not in group_indices:
                        group.claims.append(claims[j])
                        used_indices.add(j)
                    group_found = True
                    break
            
            if not group_found:
                groups.append(DuplicateGroup(
                    claims=[claims[i], claims[j]],
                    canonical=claims[i],  # First is canonical
                    similarity=similarity,
                ))
                used_indices.add(i)
                used_indices.add(j)
        
        logger.info("Duplicates found", groups=len(groups))
        return groups
    
    async def _find_conflicts(
        self,
        claims: list[Claim],
        embeddings: list[list[float]],
    ) -> list[Conflict]:
        """Find potentially conflicting claims."""
        embedding_service = await self._get_embedding()
        conflicts: list[Conflict] = []
        
        # Find pairs in conflict range
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                similarity = await embedding_service.similarity(
                    embeddings[i],
                    embeddings[j]
                )
                
                if self.conflict_threshold_low < similarity <= self.conflict_threshold_high:
                    # Check if they might be conflicting (same type, different values)
                    if claims[i].claim_type == claims[j].claim_type == "preference":
                        conflicts.append(Conflict(
                            claim_a=claims[i],
                            claim_b=claims[j],
                            similarity=similarity,
                            conflict_type="preference_conflict",
                        ))
        
        logger.info("Potential conflicts found", count=len(conflicts))
        return conflicts
    
    async def _resolve_conflicts(
        self,
        conflicts: list[Conflict],
    ) -> list[ConflictResolution]:
        """Resolve detected conflicts using LLM."""
        if not conflicts:
            return []
        
        llm = await self._get_llm()
        resolutions: list[ConflictResolution] = []
        
        for conflict in conflicts:
            resolution = await llm.resolve_conflict(conflict)
            resolutions.append(resolution)
        
        return resolutions
    
    def _build_final_claims(
        self,
        original_claims: list[Claim],
        duplicates: list[DuplicateGroup],
        resolutions: list[ConflictResolution],
    ) -> list[Claim]:
        """Build final claim list after merging and resolving."""
        final_claims: list[Claim] = []
        used_claims: set[str] = set()
        
        # Add canonical claims from duplicate groups
        for group in duplicates:
            canonical = group.canonical
            # Boost confidence for duplicates (mentioned multiple times)
            canonical.confidence = min(1.0, canonical.confidence + 0.1 * len(group.claims))
            final_claims.append(canonical)
            for claim in group.claims:
                used_claims.add(claim.claim)
        
        # Add evolved memories from conflict resolutions
        for resolution in resolutions:
            if resolution.evolved_memory:
                # Create new claim from evolution
                evolved_claim = Claim(
                    claim=resolution.evolved_memory,
                    source="conflict_resolution",
                    confidence=resolution.confidence,
                    claim_type="preference",
                )
                final_claims.append(evolved_claim)
            
            # Mark original claims as used
            used_claims.add(resolution.original_conflict.claim_a.claim)
            used_claims.add(resolution.original_conflict.claim_b.claim)
        
        # Add remaining unique claims
        for claim in original_claims:
            if claim.claim not in used_claims:
                final_claims.append(claim)
        
        return final_claims
    
    async def _save_history(
        self,
        result: ConsolidationResult,
        conversation_id: str | None,
    ) -> None:
        """Save consolidation history to database."""
        db = await self._get_db()
        repo = ConsolidationRepository(db)
        
        history = ConsolidationHistory(
            id=result.consolidation_id,
            user_id=result.user_id,
            consolidation_date=datetime.utcnow().date(),
            conversation_id=conversation_id,
            session_transcript_length=result.session_transcript_length,
            claims_extracted=result.claims_extracted,
            new_memories_created=result.new_memories_count,
            merged_count=result.merged_count,
            conflicts_resolved=result.conflicts_resolved,
            edges_created=result.edges_created,
            processing_time_ms=result.processing_time_ms,
            patterns_detected=result.patterns_detected,
            key_entities=result.key_entities,
            status=result.status,
            error_message=result.error_message,
        )
        
        await repo.create(history)
    
    def _empty_result(
        self,
        user_id: UUID,
        consolidation_id: UUID,
        transcript_length: int,
    ) -> ConsolidationResult:
        """Create an empty result when no claims were extracted."""
        return ConsolidationResult(
            consolidation_id=consolidation_id,
            user_id=user_id,
            session_transcript_length=transcript_length,
            claims_extracted=0,
            new_memories_count=0,
            processing_time_ms=0,
            status=ConsolidationStatus.COMPLETED,
        )


# Singleton instance
_consolidation_engine: ConsolidationEngine | None = None


async def get_consolidation_engine() -> ConsolidationEngine:
    """Get or create the global consolidation engine."""
    global _consolidation_engine
    
    if _consolidation_engine is None:
        _consolidation_engine = ConsolidationEngine()
    
    return _consolidation_engine
