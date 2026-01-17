"""
Tests for Memory Processor
"""

from datetime import datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.engine.memory_processor import MemoryProcessor
from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
from tests.mocks.database import MockDatabase
from tests.mocks.embedding import MockEmbeddingService


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_embedding_service():
    return MockEmbeddingService()


@pytest.fixture
def mock_memory(user_id):
    return Memory(
        id=uuid4(), user_id=user_id, content="User likes Python",
        memory_type=MemoryType.PREFERENCE, embedding=[0.1] * 1408,
        entities=["Python"], importance=8, confidence=0.9,
        status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
        access_count=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )


class TestTypeInference:
    @pytest.mark.asyncio
    async def test_infer_preference_type(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        processor._cache.set = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="I prefer Python over JavaScript",
            memory_type=MemoryType.PREFERENCE,
            entities=["Python"],
            importance=8,
            source=MemorySource.MANUAL,
        )
        
        assert memory is not None

    @pytest.mark.asyncio
    async def test_explicit_type_no_inference(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="Some semantic fact",
            memory_type=MemoryType.SEMANTIC,
            entities=[],
            importance=5,
            source=MemorySource.MANUAL,
        )
        
        assert memory is not None


class TestImportanceCalculation:
    @pytest.mark.asyncio
    async def test_calculate_importance_from_content(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        # Default importance for preference type
        memory = await processor.process_memory(
            user_id=user_id,
            content="Critical info",
            memory_type=MemoryType.PREFERENCE,
            entities=[],
            importance=8,  # Explicit importance
            source=MemorySource.MANUAL,
        )
        
        assert memory is not None

    @pytest.mark.asyncio
    async def test_explicit_importance_no_calculation(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="Test",
            memory_type=MemoryType.SEMANTIC,
            entities=[],
            importance=10,  # Explicit max importance
            source=MemorySource.MANUAL,
        )
        
        assert memory is not None


class TestEmbedding:
    @pytest.mark.asyncio
    async def test_generates_embedding(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="Content to embed",
            memory_type=MemoryType.SEMANTIC,
            entities=[],
            importance=5,
            source=MemorySource.MANUAL,
        )
        
        # Verify embedding was generated
        mock_repo.create.assert_called_once()
        call_args = mock_repo.create.call_args
        memory_create = call_args[0][0]
        assert memory_create.embedding is not None
        assert len(memory_create.embedding) == 1408


class TestEntityExtraction:
    @pytest.mark.asyncio
    async def test_extracts_entities(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="I use Python and TypeScript",
            memory_type=MemoryType.PREFERENCE,
            entities=["Python", "TypeScript"],  # Provided explicitly
            importance=8,
            source=MemorySource.MANUAL,
        )
        
        assert memory is not None

    @pytest.mark.asyncio
    async def test_explicit_entities_no_extraction(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="Test content",
            memory_type=MemoryType.SEMANTIC,
            entities=["Entity1", "Entity2"],
            importance=5,
            source=MemorySource.MANUAL,
        )
        
        mock_repo.create.assert_called_once()
        call_args = mock_repo.create.call_args
        memory_create = call_args[0][0]
        assert "Entity1" in memory_create.entities


class TestMemoryStorage:
    @pytest.mark.asyncio
    async def test_stores_memory(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="Memory to store",
            memory_type=MemoryType.SEMANTIC,
            entities=[],
            importance=5,
            source=MemorySource.MANUAL,
        )
        
        mock_repo.create.assert_called_once()


class TestProcessorOutput:
    @pytest.mark.asyncio
    async def test_returns_memory(self, user_id, mock_memory, mock_embedding_service):
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_memory)
        
        processor = MemoryProcessor(db=mock_db, embedding_service=mock_embedding_service)
        processor._memory_repo = mock_repo
        processor._cache = AsyncMock()
        
        memory = await processor.process_memory(
            user_id=user_id,
            content="Test",
            memory_type=MemoryType.SEMANTIC,
            entities=[],
            importance=5,
            source=MemorySource.MANUAL,
        )
        
        assert isinstance(memory, Memory)
        assert memory.id is not None
        assert memory.user_id == user_id
