"""
Tests for Knowledge Graph Manager

Tests the KnowledgeGraphManager class including edge creation,
timeline building, contradiction detection, and graph traversal.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.engine.knowledge_graph import KnowledgeGraphManager
from src.models.edge import EdgeType, KnowledgeEdge
from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
from tests.mocks.database import MockDatabase


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def sample_memories(user_id) -> list[Memory]:
    """Create sample memories for graph building."""
    base_time = datetime.utcnow()
    
    return [
        Memory(
            id=uuid4(),
            user_id=user_id,
            content="User likes Python",
            memory_type=MemoryType.PREFERENCE,
            embedding=[0.1] * 1408,
            entities=["Python"],
            importance=8,
            confidence=0.9,
            status=MemoryStatus.ACTIVE,
            source=MemorySource.MANUAL,
            access_count=0,
            created_at=base_time - timedelta(days=10),
            updated_at=base_time - timedelta(days=10),
        ),
        Memory(
            id=uuid4(),
            user_id=user_id,
            content="User uses FastAPI with Python",
            memory_type=MemoryType.SEMANTIC,
            embedding=[0.2] * 1408,
            entities=["FastAPI", "Python"],
            importance=7,
            confidence=0.85,
            status=MemoryStatus.ACTIVE,
            source=MemorySource.CONVERSATION,
            access_count=0,
            created_at=base_time - timedelta(days=5),
            updated_at=base_time - timedelta(days=5),
        ),
        Memory(
            id=uuid4(),
            user_id=user_id,
            content="User prefers async/await patterns",
            memory_type=MemoryType.PREFERENCE,
            embedding=[0.3] * 1408,
            entities=["async/await"],
            importance=8,
            confidence=0.9,
            status=MemoryStatus.ACTIVE,
            source=MemorySource.MANUAL,
            access_count=0,
            created_at=base_time - timedelta(days=2),
            updated_at=base_time - timedelta(days=2),
        ),
    ]


@pytest_asyncio.fixture
async def mock_db() -> MockDatabase:
    """Create a connected mock database."""
    db = MockDatabase()
    await db.connect()
    return db


@pytest.fixture
def mock_edge_repo():
    """Create a mock edge repository."""
    repo = MagicMock()
    repo.create = AsyncMock(return_value=KnowledgeEdge(
        id=uuid4(),
        user_id=uuid4(),
        from_node_id=uuid4(),
        to_node_id=uuid4(),
        edge_type=EdgeType.RELATED_TO,
        strength=0.8,
        confidence=0.9,
        reason="Related content",
        causality=False,
        bidirectional=False,
        created_at=datetime.utcnow(),
    ))
    repo.create_many = AsyncMock(return_value=[])
    repo.get_edges_from_memory = AsyncMock(return_value=[])
    repo.get_edges_to_memory = AsyncMock(return_value=[])
    repo.get_related_memories = AsyncMock(return_value=[])
    repo.delete_for_memory = AsyncMock(return_value=2)
    return repo


# =============================================================================
# Edge Creation Tests
# =============================================================================

class TestEdgeCreation:
    """Tests for edge creation."""

    @pytest.mark.asyncio
    async def test_create_edge_related_to(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test creating a RELATED_TO edge."""
        mem1, mem2 = sample_memories[0], sample_memories[1]
        
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        edge = await kg.create_edge(
            user_id=user_id,
            from_memory_id=mem1.id,
            to_memory_id=mem2.id,
            edge_type=EdgeType.RELATED_TO,
            strength=0.8,
            reason="Both mention Python",
        )
        
        mock_edge_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_edge_all_types(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test creating edges with all edge types."""
        mem1, mem2 = sample_memories[0], sample_memories[1]
        
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        edge_types = [
            EdgeType.RELATED_TO,
            EdgeType.LEADS_TO,
            EdgeType.DEPENDS_ON,
            EdgeType.CONTRADICTS,
            EdgeType.SUPPORTS,
            EdgeType.EVOLVES_INTO,
        ]
        
        for edge_type in edge_types:
            await kg.create_edge(
                user_id=user_id,
                from_memory_id=mem1.id,
                to_memory_id=mem2.id,
                edge_type=edge_type,
                strength=0.7,
            )
        
        assert mock_edge_repo.create.call_count == len(edge_types)


# =============================================================================
# Timeline Tests
# =============================================================================

class TestTimeline:
    """Tests for timeline building."""

    @pytest.mark.asyncio
    async def test_build_timeline_for_entity(
        self,
        mock_db,
        user_id,
        sample_memories,
    ):
        """Test building timeline for an entity."""
        kg = KnowledgeGraphManager(db=mock_db)
        
        # Setup mock memory repo
        mock_memory_repo = MagicMock()
        mock_memory_repo.list_by_user = AsyncMock(return_value=sample_memories)
        kg._memory_repo = mock_memory_repo
        
        # Setup mock edge repo
        mock_edge_repo = MagicMock()
        mock_edge_repo.get_edges_from_memory = AsyncMock(return_value=[])
        kg._edge_repo = mock_edge_repo
        
        timeline = await kg.get_evolution_timeline(
            user_id=user_id,
            entity_name="Python",
        )
        
        # Timeline should contain entries for memories with Python
        assert len(timeline) >= 1


# =============================================================================
# Contradiction Detection Tests
# =============================================================================

class TestContradictionDetection:
    """Tests for contradiction detection."""

    @pytest.mark.asyncio
    async def test_find_contradictions(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test finding contradicting memories."""
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        memory = sample_memories[0]
        
        contradictions = await kg.find_contradictions(
            user_id=user_id,
            memory_id=memory.id,
        )
        
        # Should have called edge repo for both directions
        assert mock_edge_repo.get_edges_from_memory.called
        assert mock_edge_repo.get_edges_to_memory.called


# =============================================================================
# Graph Traversal Tests
# =============================================================================

class TestGraphTraversal:
    """Tests for graph traversal."""

    @pytest.mark.asyncio
    async def test_get_related_memories(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test getting related memories through edges."""
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        memory = sample_memories[0]
        
        related = await kg.get_related_memories(
            user_id=user_id,
            memory_id=memory.id,
            depth=2,
        )
        
        mock_edge_repo.get_related_memories.assert_called_once()


# =============================================================================
# Link Related Memories Tests
# =============================================================================

class TestLinkRelatedMemories:
    """Tests for linking related memories."""

    @pytest.mark.asyncio
    async def test_link_related_memories(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test linking a new memory to related existing memories."""
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        new_memory = sample_memories[0]
        existing_memories = sample_memories[1:]
        
        edges = await kg.link_related_memories(
            user_id=user_id,
            new_memory=new_memory,
            existing_memories=existing_memories,
            similarity_threshold=0.7,
        )
        
        # Should create edges to each existing memory
        assert mock_edge_repo.create.call_count == len(existing_memories)


# =============================================================================
# Mark Superseded Tests
# =============================================================================

class TestMarkSuperseded:
    """Tests for marking memories as superseded."""

    @pytest.mark.asyncio
    async def test_mark_superseded(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test marking one memory as superseded by another."""
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        old_memory = sample_memories[0]
        new_memory = sample_memories[1]
        
        edge = await kg.mark_superseded(
            user_id=user_id,
            old_memory_id=old_memory.id,
            new_memory_id=new_memory.id,
            reason="Updated preference",
        )
        
        # Should create EVOLVES_INTO edge
        mock_edge_repo.create.assert_called_once()
        call_args = mock_edge_repo.create.call_args
        edge_create = call_args[0][0]
        assert edge_create.edge_type == EdgeType.EVOLVES_INTO


# =============================================================================
# Edge Deletion Tests
# =============================================================================

class TestEdgeDeletion:
    """Tests for edge deletion."""

    @pytest.mark.asyncio
    async def test_delete_edges_for_memory(
        self,
        mock_db,
        mock_edge_repo,
        user_id,
        sample_memories,
    ):
        """Test deleting all edges for a memory."""
        kg = KnowledgeGraphManager(db=mock_db)
        kg._edge_repo = mock_edge_repo
        
        memory = sample_memories[0]
        
        deleted = await kg.delete_edges_for_memory(
            user_id=user_id,
            memory_id=memory.id,
        )
        
        mock_edge_repo.delete_for_memory.assert_called_once()
        assert deleted == 2  # Mock returns 2