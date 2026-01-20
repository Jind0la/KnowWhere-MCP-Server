import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from src.engine.memory_processor import MemoryProcessor
from src.models.memory import Memory, MemoryType, MemoryStatus, MemorySource
from src.models.edge import KnowledgeEdge, EdgeType
from tests.mocks.llm import MockLLMService
from tests.mocks.embedding import MockEmbeddingService

@pytest.fixture
def user_id():
    return uuid4()

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.update = AsyncMock()
    repo.create = AsyncMock()
    repo.search_similar = AsyncMock()
    return repo

@pytest.fixture
def mock_llm():
    return MockLLMService()

@pytest.fixture
def mock_embedding():
    return MockEmbeddingService()

@pytest.fixture
def processor(mock_repo, mock_llm, mock_embedding):
    # Initialize with mocks to avoid real service creation
    processor = MemoryProcessor(
        db=MagicMock(),
        embedding_service=mock_embedding
    )
    processor._memory_repo = mock_repo
    processor._cache = AsyncMock()
    # Mock the internal dependency getters to return our mocks
    processor._get_memory_repo = AsyncMock(return_value=mock_repo)
    processor._get_embedding_service = AsyncMock(return_value=mock_embedding)
    processor._get_db = AsyncMock()
    return processor

@pytest.mark.asyncio
@patch("src.engine.memory_processor.get_llm_service")
async def test_deduplication_high_similarity(mock_get_llm, processor, mock_repo, mock_llm, user_id):
    mock_get_llm.return_value = mock_llm
    
    # Setup: existing memory with high similarity
    mock_sim = MagicMock()
    mock_sim.id = uuid4()
    mock_sim.similarity = 0.98
    mock_sim.access_count = 1
    mock_sim.content = "Old content"
    
    mock_repo.search_similar.return_value = [mock_sim]
    mock_repo.update.return_value = MagicMock(id=mock_sim.id)
    
    # Action
    result = await processor.process_memory(
        user_id=user_id,
        content="Old content", # Duplicate
        memory_type=MemoryType.SEMANTIC
    )
    
    # Assert
    assert result.id == mock_sim.id
    mock_repo.update.assert_called_once()
    mock_repo.create.assert_not_called()

@pytest.mark.asyncio
@patch("src.engine.memory_processor.get_llm_service")
@patch("src.engine.memory_processor.EdgeRepository")
@patch("src.engine.memory_processor.get_entity_hub_service")
async def test_conflict_resolution_contradiction(
    mock_get_entity, 
    mock_edge_repo_class, 
    mock_get_llm, 
    processor, 
    mock_repo, 
    mock_llm,
    user_id
):
    mock_get_llm.return_value = mock_llm
    
    # Setup old memory
    old_id = uuid4()
    old_mem = Memory(
        id=old_id, user_id=user_id, content="I use Cursor",
        memory_type=MemoryType.PREFERENCE, embedding=[0.1]*1408,
        entities=[], importance=8, confidence=0.8,
        status=MemoryStatus.ACTIVE, source=MemorySource.CONVERSATION,
        access_count=1, created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    )
    
    mock_sim = MagicMock()
    mock_sim.id = old_id
    mock_sim.similarity = 0.85 
    mock_sim.content = old_mem.content
    mock_sim.domain = "IDE"
    mock_sim.category = "Tools"
    
    mock_repo.search_similar.return_value = [mock_sim]
    mock_repo.get_by_id = AsyncMock(return_value=old_mem)
    
    # Configure mock LLM to detect contradiction
    # "contradict" keyword is handled by our MockLLMService.check_for_contradiction
    
    # Mock Entity Hub Service
    mock_entity_hub = AsyncMock()
    mock_entity_hub.extract_and_learn.return_value = MagicMock(entities=[])
    mock_get_entity.return_value = mock_entity_hub

    # Mock New Memory Creation
    new_id = uuid4()
    new_mem = Memory(
        id=new_id, user_id=user_id, content="I use Antigravity (contradict)",
        memory_type=MemoryType.PREFERENCE, embedding=[0.1]*1408,
        entities=[], importance=8, confidence=1.0,
        status=MemoryStatus.ACTIVE, source=MemorySource.CONVERSATION,
        access_count=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    )
    mock_repo.create.return_value = new_mem
    mock_repo.update.return_value = old_mem
    
    # Mock Edge Repo
    mock_edge_instance = MagicMock()
    mock_edge_instance.create = AsyncMock()
    mock_edge_repo_class.return_value = mock_edge_instance
    
    # Action
    result = await processor.process_memory(
        user_id=user_id,
        content="I use Antigravity (contradict)",
        memory_type=MemoryType.PREFERENCE
    )
    
    # Assert
    assert result.id == new_id
    mock_repo.update.assert_called_once() # Old memory should be updated to SUPERSEDED
    mock_edge_instance.create.assert_called_once() # EVOLVES_INTO edge
