"""
Tests for Consolidate Tool
"""

from datetime import datetime
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.consolidation import Claim, ConsolidationResult, ConsolidationStatus
from src.models.requests import ConsolidateOutput
from src.tools.consolidate import consolidate_session


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_transcript():
    return """
    User: I really prefer using TypeScript over plain JavaScript.
    Assistant: That's a great choice! TypeScript adds type safety.
    User: Yes, and I always use async/await instead of callbacks.
    """


@pytest.fixture
def mock_consolidation_result(user_id):
    return ConsolidationResult(
        user_id=user_id,
        claims_extracted=3,
        new_memories_count=2,
        merged_count=0,
        conflicts_resolved=0,
        edges_created=1,
        patterns_detected=["Technology preferences"],
        processing_time_ms=150,
        status=ConsolidationStatus.COMPLETED,
    )


class TestConsolidateBasic:
    @pytest.mark.asyncio
    async def test_consolidate_basic(self, user_id, sample_transcript, mock_consolidation_result):
        mock_engine = AsyncMock()
        mock_engine.consolidate = AsyncMock(return_value=mock_consolidation_result)
        
        mock_db = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        
        with patch("src.tools.consolidate.get_consolidation_engine", AsyncMock(return_value=mock_engine)), \
             patch("src.tools.consolidate.get_database", AsyncMock(return_value=mock_db)), \
             patch("src.tools.consolidate.MemoryRepository", return_value=mock_repo):
            
            result = await consolidate_session(
                user_id=user_id,
                session_transcript=sample_transcript,
            )
        
        assert isinstance(result, ConsolidateOutput)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_consolidate_returns_memory_count(self, user_id, sample_transcript, mock_consolidation_result):
        mock_engine = AsyncMock()
        mock_engine.consolidate = AsyncMock(return_value=mock_consolidation_result)
        
        with patch("src.tools.consolidate.get_consolidation_engine", AsyncMock(return_value=mock_engine)), \
             patch("src.tools.consolidate.get_database", AsyncMock()), \
             patch("src.tools.consolidate.MemoryRepository"):
            
            result = await consolidate_session(
                user_id=user_id,
                session_transcript=sample_transcript,
            )
        
        assert result.new_memories_count == 2


class TestConsolidateValidation:
    @pytest.mark.asyncio
    async def test_consolidate_min_length(self, user_id):
        with pytest.raises(ValueError) as exc_info:
            await consolidate_session(user_id=user_id, session_transcript="Hi")
        assert "too short" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_consolidate_max_length(self, user_id):
        with pytest.raises(ValueError) as exc_info:
            await consolidate_session(user_id=user_id, session_transcript="A" * 100001)
        assert "too long" in str(exc_info.value).lower()


class TestConflictResolution:
    @pytest.mark.asyncio
    async def test_consolidate_resolves_conflicts(self, user_id):
        result_with_conflicts = ConsolidationResult(
            user_id=user_id,
            claims_extracted=2,
            new_memories_count=1,
            merged_count=0,
            conflicts_resolved=1,
            edges_created=1,
            patterns_detected=["Evolution"],
            processing_time_ms=200,
            status=ConsolidationStatus.COMPLETED,
        )
        
        mock_engine = AsyncMock()
        mock_engine.consolidate = AsyncMock(return_value=result_with_conflicts)
        
        with patch("src.tools.consolidate.get_consolidation_engine", AsyncMock(return_value=mock_engine)), \
             patch("src.tools.consolidate.get_database", AsyncMock()), \
             patch("src.tools.consolidate.MemoryRepository"):
            
            result = await consolidate_session(
                user_id=user_id,
                session_transcript="User: I prefer React. (later) User: Now I use Vue.",
            )
        
        assert result.conflicts_resolved == 1


class TestConsolidateOutput:
    @pytest.mark.asyncio
    async def test_consolidate_output_structure(self, user_id, sample_transcript, mock_consolidation_result):
        mock_engine = AsyncMock()
        mock_engine.consolidate = AsyncMock(return_value=mock_consolidation_result)
        
        with patch("src.tools.consolidate.get_consolidation_engine", AsyncMock(return_value=mock_engine)), \
             patch("src.tools.consolidate.get_database", AsyncMock()), \
             patch("src.tools.consolidate.MemoryRepository"):
            
            result = await consolidate_session(user_id=user_id, session_transcript=sample_transcript)
        
        assert hasattr(result, 'consolidation_id')
        assert hasattr(result, 'new_memories_count')
        assert hasattr(result, 'processing_time_ms')
        assert hasattr(result, 'status')
