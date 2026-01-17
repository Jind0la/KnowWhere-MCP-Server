"""
Tests for Recall Tool
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


class TestRecallBasic:
    @pytest.mark.asyncio
    async def test_recall_basic(self, user_id, sample_memories_with_similarity):
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_repo = MagicMock()
        mock_repo.search_similar = AsyncMock(return_value=sample_memories_with_similarity)
        mock_repo.count_by_user = AsyncMock(return_value=10)
        mock_repo._update_access = AsyncMock()
        
        with patch("src.tools.recall.get_embedding_service", AsyncMock(return_value=mock_embedding)), \
             patch("src.tools.recall.get_database", AsyncMock()), \
             patch("src.tools.recall.MemoryRepository", return_value=mock_repo):
            
            result = await recall(user_id=user_id, query="Python preferences")
        
        assert isinstance(result, RecallOutput)
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_recall_empty_results(self, user_id):
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_repo = MagicMock()
        mock_repo.search_similar = AsyncMock(return_value=[])
        mock_repo.count_by_user = AsyncMock(return_value=0)
        
        with patch("src.tools.recall.get_embedding_service", AsyncMock(return_value=mock_embedding)), \
             patch("src.tools.recall.get_database", AsyncMock()), \
             patch("src.tools.recall.MemoryRepository", return_value=mock_repo):
            
            result = await recall(user_id=user_id, query="nonexistent")
        
        assert result.count == 0


class TestRecallFilters:
    @pytest.mark.asyncio
    async def test_recall_with_filters(self, user_id, sample_memories_with_similarity):
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_repo = MagicMock()
        mock_repo.search_similar = AsyncMock(return_value=[sample_memories_with_similarity[0]])
        mock_repo.count_by_user = AsyncMock(return_value=5)
        mock_repo._update_access = AsyncMock()
        
        with patch("src.tools.recall.get_embedding_service", AsyncMock(return_value=mock_embedding)), \
             patch("src.tools.recall.get_database", AsyncMock()), \
             patch("src.tools.recall.MemoryRepository", return_value=mock_repo):
            
            result = await recall(
                user_id=user_id,
                query="Python",
                filters={"memory_type": "preference"},
            )
        
        assert result.count == 1


class TestRecallLimit:
    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, user_id, sample_memories_with_similarity):
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_repo = MagicMock()
        mock_repo.search_similar = AsyncMock(return_value=[sample_memories_with_similarity[0]])
        mock_repo.count_by_user = AsyncMock(return_value=100)
        mock_repo._update_access = AsyncMock()
        
        with patch("src.tools.recall.get_embedding_service", AsyncMock(return_value=mock_embedding)), \
             patch("src.tools.recall.get_database", AsyncMock()), \
             patch("src.tools.recall.MemoryRepository", return_value=mock_repo):
            
            result = await recall(user_id=user_id, query="Python", limit=1)
        
        call_kwargs = mock_repo.search_similar.call_args.kwargs
        assert call_kwargs.get('limit') == 1

    @pytest.mark.asyncio
    async def test_recall_limit_bounds(self, user_id, sample_memories_with_similarity):
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_repo = MagicMock()
        mock_repo.search_similar = AsyncMock(return_value=sample_memories_with_similarity)
        mock_repo.count_by_user = AsyncMock(return_value=100)
        mock_repo._update_access = AsyncMock()
        
        with patch("src.tools.recall.get_embedding_service", AsyncMock(return_value=mock_embedding)), \
             patch("src.tools.recall.get_database", AsyncMock()), \
             patch("src.tools.recall.MemoryRepository", return_value=mock_repo):
            
            await recall(user_id=user_id, query="Python", limit=100)
            call_kwargs = mock_repo.search_similar.call_args.kwargs
            assert call_kwargs.get('limit') <= 50


class TestRecallOutput:
    @pytest.mark.asyncio
    async def test_output_structure(self, user_id, sample_memories_with_similarity):
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 1408)
        
        mock_repo = MagicMock()
        mock_repo.search_similar = AsyncMock(return_value=sample_memories_with_similarity)
        mock_repo.count_by_user = AsyncMock(return_value=10)
        mock_repo._update_access = AsyncMock()
        
        with patch("src.tools.recall.get_embedding_service", AsyncMock(return_value=mock_embedding)), \
             patch("src.tools.recall.get_database", AsyncMock()), \
             patch("src.tools.recall.MemoryRepository", return_value=mock_repo):
            
            result = await recall(user_id=user_id, query="Python")
        
        assert hasattr(result, 'query')
        assert hasattr(result, 'count')
        assert hasattr(result, 'total_available')
        assert hasattr(result, 'memories')
        assert hasattr(result, 'search_time_ms')
        # Verify memories have similarity scores
        assert all(hasattr(m, 'similarity') for m in result.memories)
