"""
Tests for Recall Tool

Updated to work with the new RecallEngine-based recall.
"""

from datetime import datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.memory import MemoryWithSimilarity, MemorySource, MemoryStatus, MemoryType
from src.models.requests import RecallOutput
from src.tools.recall import recall


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_memories_with_similarity(user_id):
    """Create sample memories WITH similarity scores (required by RecallOutput)."""
    return [
        MemoryWithSimilarity(
            id=uuid4(), user_id=user_id, content="User likes Python",
            memory_type=MemoryType.PREFERENCE, embedding=[0.1] * 1408,
            entities=["Python"], importance=8, confidence=0.9,
            status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
            access_count=1, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            similarity=0.95,
        ),
        MemoryWithSimilarity(
            id=uuid4(), user_id=user_id, content="User uses FastAPI",
            memory_type=MemoryType.SEMANTIC, embedding=[0.2] * 1408,
            entities=["FastAPI", "Python"], importance=7, confidence=0.85,
            status=MemoryStatus.ACTIVE, source=MemorySource.CONVERSATION,
            access_count=2, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            similarity=0.88,
        ),
    ]


def create_mock_recall_result(memories, query="test"):
    """Create a mock EnhancedRecallResult."""
    mock = MagicMock()
    mock.memories = memories
    mock.count = len(memories)
    mock.total_available = 10
    mock.search_time_ms = 50
    mock.evolution_filtered_count = 0
    mock.entity_expanded_count = 0
    mock.query = query
    return mock


class TestRecallBasic:
    @pytest.mark.asyncio
    async def test_recall_basic(self, user_id, sample_memories_with_similarity):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result(sample_memories_with_similarity)
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            result = await recall(user_id=user_id, query="Python preferences")
        
        assert isinstance(result, RecallOutput)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_recall_empty_results(self, user_id):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result([])
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            result = await recall(user_id=user_id, query="nonexistent")
        
        assert result.count == 0


class TestRecallFilters:
    @pytest.mark.asyncio
    async def test_recall_with_filters(self, user_id, sample_memories_with_similarity):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result([sample_memories_with_similarity[0]])
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            result = await recall(
                user_id=user_id,
                query="Python",
                filters={"memory_type": "preference"},
            )
        
        assert result.count == 1
        # Verify filters were passed to engine
        call_kwargs = mock_engine.recall.call_args.kwargs
        assert call_kwargs.get("filters") is not None
        assert call_kwargs["filters"].memory_type == MemoryType.PREFERENCE


class TestRecallLimit:
    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, user_id, sample_memories_with_similarity):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result([sample_memories_with_similarity[0]])
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            await recall(user_id=user_id, query="Python", limit=1)
        
        call_kwargs = mock_engine.recall.call_args.kwargs
        assert call_kwargs.get('limit') == 1

    @pytest.mark.asyncio
    async def test_recall_limit_bounds(self, user_id, sample_memories_with_similarity):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result(sample_memories_with_similarity)
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            await recall(user_id=user_id, query="Python", limit=100)
        
        call_kwargs = mock_engine.recall.call_args.kwargs
        # Limit should be capped at 50
        assert call_kwargs.get('limit') <= 50


class TestRecallOutput:
    @pytest.mark.asyncio
    async def test_output_structure(self, user_id, sample_memories_with_similarity):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result(sample_memories_with_similarity, query="Python")
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            result = await recall(user_id=user_id, query="Python")
        
        assert hasattr(result, 'query')
        assert hasattr(result, 'count')
        assert hasattr(result, 'total_available')
        assert hasattr(result, 'memories')
        assert hasattr(result, 'search_time_ms')
        # Verify memories have similarity scores
        assert all(hasattr(m, 'similarity') for m in result.memories)


class TestRecallGraphFeatures:
    """Test that graph-enhanced features are enabled by default."""
    
    @pytest.mark.asyncio
    async def test_graph_features_enabled(self, user_id, sample_memories_with_similarity):
        mock_engine = AsyncMock()
        mock_engine.recall = AsyncMock(
            return_value=create_mock_recall_result(sample_memories_with_similarity)
        )
        
        with patch("src.tools.recall.get_recall_engine", AsyncMock(return_value=mock_engine)):
            await recall(user_id=user_id, query="Python")
        
        call_kwargs = mock_engine.recall.call_args.kwargs
        
        # Verify graph-enhanced features are enabled
        assert call_kwargs.get('respect_evolution') is True
        assert call_kwargs.get('expand_entities') is True
        assert call_kwargs.get('apply_recency_boost') is True
