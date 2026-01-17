"""
Tests for Delete Tool
"""

from datetime import datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
from src.models.requests import DeleteOutput
from src.tools.delete import delete_memory


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_memory(user_id):
    return Memory(
        id=uuid4(), user_id=user_id, content="Test memory",
        memory_type=MemoryType.SEMANTIC, embedding=[0.1] * 1408,
        entities=["Test"], importance=5, confidence=0.8,
        status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
        access_count=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )


class TestDeleteBasic:
    @pytest.mark.asyncio
    async def test_delete_not_found(self, user_id):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        
        with patch("src.tools.delete.get_database", AsyncMock()), \
             patch("src.tools.delete.MemoryRepository", return_value=mock_repo):
            
            with pytest.raises(ValueError) as exc_info:
                await delete_memory(user_id=user_id, memory_id=uuid4())
            
            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_soft_delete(self, user_id, sample_memory):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_memory)
        mock_repo.soft_delete = AsyncMock(return_value=True)
        
        mock_kg = AsyncMock()
        mock_kg.delete_edges_for_memory = AsyncMock(return_value=2)
        
        mock_cache = AsyncMock()
        
        with patch("src.tools.delete.get_database", AsyncMock()), \
             patch("src.tools.delete.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.delete.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.delete.get_cache", AsyncMock(return_value=mock_cache)):
            
            result = await delete_memory(user_id=user_id, memory_id=sample_memory.id)
        
        assert isinstance(result, DeleteOutput)
        assert result.deleted is True
        assert result.deletion_type == "soft"

    @pytest.mark.asyncio
    async def test_hard_delete(self, user_id, sample_memory):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_memory)
        mock_repo.hard_delete = AsyncMock(return_value=True)
        
        mock_kg = AsyncMock()
        mock_kg.delete_edges_for_memory = AsyncMock(return_value=1)
        
        mock_cache = AsyncMock()
        
        with patch("src.tools.delete.get_database", AsyncMock()), \
             patch("src.tools.delete.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.delete.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.delete.get_cache", AsyncMock(return_value=mock_cache)):
            
            result = await delete_memory(user_id=user_id, memory_id=sample_memory.id, hard_delete=True)
        
        assert result.deletion_type == "hard"


class TestDeleteEdges:
    @pytest.mark.asyncio
    async def test_delete_removes_edges(self, user_id, sample_memory):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_memory)
        mock_repo.soft_delete = AsyncMock(return_value=True)
        
        mock_kg = AsyncMock()
        mock_kg.delete_edges_for_memory = AsyncMock(return_value=5)
        
        mock_cache = AsyncMock()
        
        with patch("src.tools.delete.get_database", AsyncMock()), \
             patch("src.tools.delete.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.delete.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.delete.get_cache", AsyncMock(return_value=mock_cache)):
            
            result = await delete_memory(user_id=user_id, memory_id=sample_memory.id)
        
        assert result.related_edges_removed == 5


class TestDeleteOutput:
    @pytest.mark.asyncio
    async def test_output_structure(self, user_id, sample_memory):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=sample_memory)
        mock_repo.soft_delete = AsyncMock(return_value=True)
        
        mock_kg = AsyncMock()
        mock_kg.delete_edges_for_memory = AsyncMock(return_value=0)
        
        mock_cache = AsyncMock()
        
        with patch("src.tools.delete.get_database", AsyncMock()), \
             patch("src.tools.delete.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.delete.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.delete.get_cache", AsyncMock(return_value=mock_cache)):
            
            result = await delete_memory(user_id=user_id, memory_id=sample_memory.id)
        
        assert hasattr(result, 'memory_id')
        assert hasattr(result, 'deleted')
        assert hasattr(result, 'deleted_at')
        assert hasattr(result, 'deletion_type')
