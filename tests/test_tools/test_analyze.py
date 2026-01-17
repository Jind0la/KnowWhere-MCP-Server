"""
Tests for Analyze Tool
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.requests import AnalyzeOutput, TimeWindow
from src.tools.analyze import analyze_evolution


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_timeline_data():
    return [
        {
            "date": datetime.utcnow().isoformat(),
            "memory_id": str(uuid4()),
            "content_summary": "User likes Python",
            "change_type": "introduced",
        }
    ]


@pytest.fixture
def mock_memory():
    from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
    return Memory(
        id=uuid4(), user_id=uuid4(), content="User likes Python",
        memory_type=MemoryType.PREFERENCE, embedding=[0.1] * 1408,
        entities=["Python"], importance=8, confidence=0.9,
        status=MemoryStatus.ACTIVE, source=MemorySource.MANUAL,
        access_count=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )


class TestAnalyzeBasic:
    @pytest.mark.asyncio
    async def test_analyze_requires_entity(self, user_id):
        with pytest.raises(ValueError) as exc_info:
            await analyze_evolution(user_id=user_id)
        assert "entity_id or entity_name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_by_entity_name(self, user_id, mock_timeline_data, mock_memory):
        mock_kg = AsyncMock()
        mock_kg.get_evolution_timeline = AsyncMock(return_value=mock_timeline_data)
        
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_memory])
        
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value='{"patterns":[],"insights":[]}')
        
        with patch("src.tools.analyze.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.analyze.get_database", AsyncMock()), \
             patch("src.tools.analyze.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.analyze.get_llm_service", AsyncMock(return_value=mock_llm)):
            
            result = await analyze_evolution(user_id=user_id, entity_name="Python")
        
        assert isinstance(result, AnalyzeOutput)
        assert result.entity_name == "Python"


class TestTimeWindow:
    @pytest.mark.asyncio
    async def test_analyze_time_windows(self, user_id, mock_timeline_data, mock_memory):
        mock_kg = AsyncMock()
        mock_kg.get_evolution_timeline = AsyncMock(return_value=mock_timeline_data)
        
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_memory])
        
        with patch("src.tools.analyze.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.analyze.get_database", AsyncMock()), \
             patch("src.tools.analyze.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.analyze.get_llm_service", AsyncMock()):
            
            for tw in ["last_7_days", "last_30_days", "last_year", "all_time"]:
                result = await analyze_evolution(user_id=user_id, entity_name="Python", time_window=tw)
                assert result is not None


class TestAnalyzeOutput:
    @pytest.mark.asyncio
    async def test_output_structure(self, user_id, mock_timeline_data, mock_memory):
        mock_kg = AsyncMock()
        mock_kg.get_evolution_timeline = AsyncMock(return_value=mock_timeline_data)
        
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_memory])
        
        with patch("src.tools.analyze.get_knowledge_graph", AsyncMock(return_value=mock_kg)), \
             patch("src.tools.analyze.get_database", AsyncMock()), \
             patch("src.tools.analyze.MemoryRepository", return_value=mock_repo), \
             patch("src.tools.analyze.get_llm_service", AsyncMock()):
            
            result = await analyze_evolution(user_id=user_id, entity_name="Python")
        
        assert hasattr(result, 'entity_name')
        assert hasattr(result, 'evolution_timeline')
        assert hasattr(result, 'patterns')
        assert hasattr(result, 'total_mentions')
