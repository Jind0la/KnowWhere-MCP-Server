"""
Tests for Export Tool
"""

from datetime import datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
from src.models.requests import ExportOutput, ExportFormat
from src.tools.export import export_memories


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_memories(user_id):
    return [
        Memory(
            id=uuid4(), user_id=user_id, content="Test memory 1",
            memory_type=MemoryType.SEMANTIC, embedding=[0.1] * 1408,
            entities=["Test"], importance=5, confidence=0.8,
            status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
            access_count=1, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        ),
        Memory(
            id=uuid4(), user_id=user_id, content="Test memory 2",
            memory_type=MemoryType.PREFERENCE, embedding=[0.2] * 1408,
            entities=["Python"], importance=8, confidence=0.9,
            status=MemoryStatus.ACTIVE, source=MemorySource.CONVERSATION,
            access_count=5, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        ),
    ]


class TestExportBasic:
    @pytest.mark.asyncio
    async def test_export_json(self, user_id, sample_memories):
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=sample_memories)
        
        with patch("src.tools.export.get_database", AsyncMock()), \
             patch("src.tools.export.MemoryRepository", return_value=mock_repo):
            
            result = await export_memories(user_id=user_id, format="json")
        
        assert isinstance(result, ExportOutput)
        assert result.format == ExportFormat.JSON
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_export_csv(self, user_id, sample_memories):
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=sample_memories)
        
        with patch("src.tools.export.get_database", AsyncMock()), \
             patch("src.tools.export.MemoryRepository", return_value=mock_repo):
            
            result = await export_memories(user_id=user_id, format="csv")
        
        assert result.format == ExportFormat.CSV
        assert isinstance(result.data, str)
        assert "id,content" in result.data


class TestExportFilters:
    @pytest.mark.asyncio
    async def test_export_with_filter(self, user_id, sample_memories):
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[sample_memories[1]])
        
        with patch("src.tools.export.get_database", AsyncMock()), \
             patch("src.tools.export.MemoryRepository", return_value=mock_repo):
            
            result = await export_memories(
                user_id=user_id,
                format="json",
                filters={"memory_type": "preference"}
            )
        
        assert result.count == 1


class TestExportEmbeddings:
    @pytest.mark.asyncio
    async def test_export_with_embeddings(self, user_id, sample_memories):
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=sample_memories)
        
        with patch("src.tools.export.get_database", AsyncMock()), \
             patch("src.tools.export.MemoryRepository", return_value=mock_repo):
            
            result = await export_memories(user_id=user_id, format="json", include_embeddings=True)
        
        assert result.count == 2
        # With embeddings, size should be larger
        assert result.file_size_bytes > 0


class TestExportEmpty:
    @pytest.mark.asyncio
    async def test_export_empty(self, user_id):
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[])
        
        with patch("src.tools.export.get_database", AsyncMock()), \
             patch("src.tools.export.MemoryRepository", return_value=mock_repo):
            
            result = await export_memories(user_id=user_id, format="json")
        
        assert result.count == 0
        assert result.data == []


class TestExportOutput:
    @pytest.mark.asyncio
    async def test_output_structure(self, user_id, sample_memories):
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=sample_memories)
        
        with patch("src.tools.export.get_database", AsyncMock()), \
             patch("src.tools.export.MemoryRepository", return_value=mock_repo):
            
            result = await export_memories(user_id=user_id)
        
        assert hasattr(result, 'format')
        assert hasattr(result, 'count')
        assert hasattr(result, 'data')
        assert hasattr(result, 'export_date')
        assert hasattr(result, 'file_size_bytes')
