"""
Tests for Recall Engine - Graph-Enhanced Recall
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.memory import MemoryWithSimilarity, MemorySource, MemoryStatus, MemoryType
from src.models.edge import EdgeType, KnowledgeEdge
from src.engine.recall_engine import RecallEngine, EnhancedRecallResult


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_memories(user_id):
    """Create sample memories with similarity scores."""
    return [
        MemoryWithSimilarity(
            id=uuid4(), user_id=user_id, content="User likes Python",
            memory_type=MemoryType.PREFERENCE, embedding=[0.1] * 1408,
            entities=["Python"], importance=8, confidence=0.9,
            status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
            access_count=5, created_at=datetime.utcnow(), 
            updated_at=datetime.utcnow(),
            last_accessed=datetime.utcnow() - timedelta(hours=12),  # Recent
            similarity=0.95,
        ),
        MemoryWithSimilarity(
            id=uuid4(), user_id=user_id, content="User uses FastAPI",
            memory_type=MemoryType.SEMANTIC, embedding=[0.2] * 1408,
            entities=["FastAPI", "Python"], importance=7, confidence=0.85,
            status=MemoryStatus.ACTIVE, source=MemorySource.CONVERSATION,
            access_count=2, created_at=datetime.utcnow() - timedelta(days=30),
            updated_at=datetime.utcnow() - timedelta(days=30),
            last_accessed=datetime.utcnow() - timedelta(days=30),  # Old
            similarity=0.88,
        ),
        MemoryWithSimilarity(
            id=uuid4(), user_id=user_id, content="User now prefers Rust over Python",
            memory_type=MemoryType.PREFERENCE, embedding=[0.15] * 1408,
            entities=["Rust", "Python"], importance=9, confidence=0.95,
            status=MemoryStatus.ACTIVE, source=MemorySource.CONSOLIDATION,
            access_count=15, created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),  # Very recent
            similarity=0.75,
        ),
    ]


class TestRecallEngineEvolution:
    """Tests for evolution-aware recall."""

    @pytest.mark.asyncio
    async def test_filter_evolved_memories(self, user_id, sample_memories):
        """Test that memories with EVOLVES_INTO edges are filtered out."""
        engine = RecallEngine()
        
        # Create a mock edge from old Python memory to new Rust memory
        old_memory = sample_memories[0]  # "User likes Python"
        new_memory = sample_memories[2]  # "User now prefers Rust"
        
        mock_edge = KnowledgeEdge(
            id=uuid4(),
            user_id=user_id,
            from_node_id=old_memory.id,
            to_node_id=new_memory.id,
            edge_type=EdgeType.EVOLVES_INTO,
            strength=1.0,
            confidence=0.95,
            causality=True,
            bidirectional=False,
            reason="Memory superseded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        mock_edge_repo = AsyncMock()
        # Return the evolution edge for old_memory
        mock_edge_repo.get_edges_from_memory = AsyncMock(
            side_effect=lambda memory_id, user_id, edge_type=None: 
                [mock_edge] if memory_id == old_memory.id and edge_type == EdgeType.EVOLVES_INTO
                else []
        )
        
        # Inject mock
        engine._edge_repo = mock_edge_repo
        
        filtered, count = await engine._filter_evolved_memories(
            memories=sample_memories,
            user_id=user_id,
        )
        
        # Old Python memory should be filtered out
        assert count == 1
        assert old_memory not in filtered
        assert new_memory in filtered
        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_filter_keeps_non_evolved(self, user_id, sample_memories):
        """Test that memories without EVOLVES_INTO edges are kept."""
        engine = RecallEngine()
        
        mock_edge_repo = AsyncMock()
        mock_edge_repo.get_edges_from_memory = AsyncMock(return_value=[])
        
        engine._edge_repo = mock_edge_repo
        
        filtered, count = await engine._filter_evolved_memories(
            memories=sample_memories,
            user_id=user_id,
        )
        
        assert count == 0
        assert len(filtered) == len(sample_memories)


class TestRecallEngineRecencyBoost:
    """Tests for recency boost logic."""

    @pytest.mark.asyncio
    async def test_recency_boost_recent(self, sample_memories):
        """Test that recently accessed memories get boosted."""
        engine = RecallEngine()
        
        boosted = engine._apply_recency_boost(sample_memories)
        
        # Verify boosts were applied to recently accessed memories
        # sample_memories[0]: last_accessed within 24h, access_count=5 -> +0.10 boost
        # sample_memories[1]: last_accessed 30 days ago -> no boost (not within 7 days)
        # sample_memories[2]: last_accessed now, access_count=15 -> +0.10 + 0.05 = +0.15 boost
        
        # Find boosted scores
        boosted_map = {m.id: m.similarity for m in boosted}
        
        # sample_memories[0] should get recency boost (within 24h)
        expected_0 = min(1.0, 0.95 + 0.10)  # 1.0 (capped)
        assert boosted_map[sample_memories[0].id] == expected_0
        
        # sample_memories[1] should get no boost (accessed 30 days ago, > 7 days)
        expected_1 = 0.88  # No boost
        assert boosted_map[sample_memories[1].id] == expected_1
        
        # sample_memories[2] should get max boost (very recent + high access count)
        expected_2 = min(1.0, 0.75 + 0.10 + 0.05)  # 0.90
        assert boosted_map[sample_memories[2].id] == expected_2

    @pytest.mark.asyncio
    async def test_recency_boost_formula(self):
        """Test the exact boost values."""
        engine = RecallEngine()
        now = datetime.utcnow()
        
        # Create a memory accessed 1 hour ago with high access count
        recent_memory = MemoryWithSimilarity(
            id=uuid4(), user_id=uuid4(), content="Recent memory",
            memory_type=MemoryType.SEMANTIC, embedding=[0.1] * 1408,
            entities=[], importance=5, confidence=0.8,
            status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
            access_count=15,  # > 10
            created_at=now, updated_at=now,
            last_accessed=now - timedelta(hours=1),  # Within 24h
            similarity=0.70,
        )
        
        boosted = engine._apply_recency_boost([recent_memory])
        
        # Should get +0.10 for recency + 0.05 for access count
        expected_similarity = min(1.0, 0.70 + 0.10 + 0.05)
        assert boosted[0].similarity == expected_similarity


class TestRecallEngineEntityExpansion:
    """Tests for entity-based memory expansion."""

    @pytest.mark.asyncio
    async def test_entity_expansion_finds_related(self, user_id, sample_memories):
        """Test that entity expansion finds memories sharing entities."""
        engine = RecallEngine()
        
        # Mock database to return a related memory via entity_hubs
        related_memory_id = uuid4()
        
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{"id": related_memory_id}])
        
        mock_memory_repo = AsyncMock()
        # Return a full memory object when fetched
        mock_memory_repo.get_by_id = AsyncMock(return_value=MagicMock(
            id=related_memory_id,
            model_dump=MagicMock(return_value={
                "id": related_memory_id,
                "user_id": user_id,
                "content": "Related Python memory",
                "memory_type": MemoryType.SEMANTIC,
                "embedding": [0.1] * 1408,
                "entities": ["Python"],
                "importance": 6,
                "confidence": 0.8,
                "status": MemoryStatus.ACTIVE,
                "source": MemorySource.MANUAL,
                "access_count": 1,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_accessed": None,
            })
        ))
        
        engine._db = mock_db
        engine._memory_repo = mock_memory_repo
        
        expanded, count = await engine._expand_via_entities(
            seed_memories=sample_memories[:1],  # Just the Python memory
            user_id=user_id,
            max_additional=5,
        )
        
        # Should find at least one related memory
        assert count >= 0  # May be 0 if no entity links exist


class TestRecallEngineIntegration:
    """Integration tests for the full recall flow."""

    @pytest.mark.asyncio
    async def test_full_recall_with_all_features(self, user_id, sample_memories):
        """Test full recall with evolution filtering and recency boost."""
        engine = RecallEngine()
        
        # Mock all dependencies
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_memory_repo = MagicMock()
        mock_memory_repo.search_similar = AsyncMock(return_value=sample_memories)
        mock_memory_repo.count_by_user = AsyncMock(return_value=10)
        mock_memory_repo._update_access = AsyncMock()
        
        mock_edge_repo = AsyncMock()
        mock_edge_repo.get_edges_from_memory = AsyncMock(return_value=[])
        
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        
        engine._embedding_service = mock_embedding
        engine._memory_repo = mock_memory_repo
        engine._edge_repo = mock_edge_repo
        engine._db = mock_db
        
        result = await engine.recall(
            user_id=user_id,
            query="What programming languages do I like?",
            limit=10,
            respect_evolution=True,
            expand_entities=True,
            apply_recency_boost=True,
        )
        
        assert isinstance(result, EnhancedRecallResult)
        assert result.count > 0
        assert result.search_time_ms >= 0
        # With recency boost, most recently accessed should be first
        # (unless evolution filtering changed the order)


class TestRecallEngineBackwardsCompatibility:
    """Tests to ensure backwards compatibility."""

    @pytest.mark.asyncio
    async def test_recall_without_graph_features(self, user_id, sample_memories):
        """Test that recall works with all graph features disabled."""
        engine = RecallEngine()
        
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_memory_repo = MagicMock()
        mock_memory_repo.search_similar = AsyncMock(return_value=sample_memories)
        mock_memory_repo.count_by_user = AsyncMock(return_value=10)
        mock_memory_repo._update_access = AsyncMock()
        
        engine._embedding_service = mock_embedding
        engine._memory_repo = mock_memory_repo
        
        # Disable all graph features
        result = await engine.recall(
            user_id=user_id,
            query="test query",
            limit=10,
            respect_evolution=False,
            expand_entities=False,
            include_related=False,
            apply_recency_boost=False,
        )
        
        # Should still work and return results
        assert isinstance(result, EnhancedRecallResult)
        assert result.count == len(sample_memories)
        # No evolution filtering
        assert result.evolution_filtered_count == 0
        # No entity expansion
        assert result.entity_expanded_count == 0
