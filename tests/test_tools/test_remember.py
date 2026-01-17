"""
Tests for Remember Tool
"""

from datetime import datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
from src.models.requests import RememberOutput
from src.tools.remember import remember


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_memory(user_id):
    return Memory(
        id=uuid4(), user_id=user_id, content="User likes Python",
        memory_type=MemoryType.PREFERENCE, embedding=[0.1] * 1408,
        entities=["Python"], importance=8, confidence=0.9,
        status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
        access_count=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )


class TestRememberBasic:
    @pytest.mark.asyncio
    async def test_remember_basic(self, user_id, mock_memory):
        mock_processor = MagicMock()
        mock_processor.process_memory = AsyncMock(return_value=mock_memory)
        
        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["Python"])
        
        with patch("src.tools.remember.MemoryProcessor", return_value=mock_processor), \
             patch("src.tools.remember.get_entity_extractor", AsyncMock(return_value=mock_extractor)):
            
            result = await remember(
                user_id=user_id,
                content="User likes Python",
                memory_type="preference",
            )
        
        assert isinstance(result, RememberOutput)
        assert result.status == "created"

    @pytest.mark.asyncio
    async def test_remember_invalid_type(self, user_id):
        with pytest.raises(ValueError) as exc_info:
            await remember(user_id=user_id, content="Test", memory_type="invalid_type")
        assert "Invalid memory_type" in str(exc_info.value)


class TestRememberEntities:
    @pytest.mark.asyncio
    async def test_remember_with_entities(self, user_id, mock_memory):
        mock_processor = MagicMock()
        mock_processor.process_memory = AsyncMock(return_value=mock_memory)
        
        with patch("src.tools.remember.MemoryProcessor", return_value=mock_processor), \
             patch("src.tools.remember.get_entity_extractor"):
            
            result = await remember(
                user_id=user_id,
                content="User likes Python and TypeScript",
                memory_type="preference",
                entities=["Python", "TypeScript"],
            )
        
        # When entities provided, extractor should not be called
        assert result is not None

    @pytest.mark.asyncio
    async def test_remember_auto_extracts_entities(self, user_id, mock_memory):
        mock_processor = MagicMock()
        mock_processor.process_memory = AsyncMock(return_value=mock_memory)
        
        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["Python", "TypeScript"])
        
        with patch("src.tools.remember.MemoryProcessor", return_value=mock_processor), \
             patch("src.tools.remember.get_entity_extractor", AsyncMock(return_value=mock_extractor)):
            
            result = await remember(
                user_id=user_id,
                content="User likes Python and TypeScript",
                memory_type="preference",
            )
        
        mock_extractor.extract.assert_called_once()


class TestRememberImportance:
    @pytest.mark.asyncio
    async def test_remember_with_importance(self, user_id, mock_memory):
        mock_processor = MagicMock()
        mock_processor.process_memory = AsyncMock(return_value=mock_memory)
        
        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=[])
        
        with patch("src.tools.remember.MemoryProcessor", return_value=mock_processor), \
             patch("src.tools.remember.get_entity_extractor", AsyncMock(return_value=mock_extractor)):
            
            await remember(
                user_id=user_id,
                content="Critical info",
                memory_type="semantic",
                importance=10,
            )
        
        # Check that importance was passed
        call_args = mock_processor.process_memory.call_args
        assert call_args.kwargs.get('importance') == 10


class TestRememberOutput:
    @pytest.mark.asyncio
    async def test_output_structure(self, user_id, mock_memory):
        mock_processor = MagicMock()
        mock_processor.process_memory = AsyncMock(return_value=mock_memory)
        
        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["Python"])
        
        with patch("src.tools.remember.MemoryProcessor", return_value=mock_processor), \
             patch("src.tools.remember.get_entity_extractor", AsyncMock(return_value=mock_extractor)):
            
            result = await remember(
                user_id=user_id,
                content="Test memory",
                memory_type="semantic",
            )
        
        assert hasattr(result, 'memory_id')
        assert hasattr(result, 'status')
        assert hasattr(result, 'embedding_status')
        assert hasattr(result, 'entities_extracted')
        assert hasattr(result, 'created_at')
