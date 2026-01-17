"""
Tests for Edge Repository

Tests the EdgeRepository class including CRUD operations,
graph traversal, and edge management.
"""

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from src.models.edge import EdgeCreate, EdgeType, KnowledgeEdge
from src.storage.repositories.edge_repo import EdgeRepository
from tests.mocks.database import MockDatabase


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def db() -> MockDatabase:
    """Create a connected mock database."""
    db = MockDatabase()
    await db.connect()
    return db


@pytest_asyncio.fixture
async def repo(db: MockDatabase) -> EdgeRepository:
    """Create an edge repository with mock database."""
    return EdgeRepository(db)


@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def memory_id_1():
    """Generate first memory ID."""
    return uuid4()


@pytest.fixture
def memory_id_2():
    """Generate second memory ID."""
    return uuid4()


@pytest.fixture
def memory_id_3():
    """Generate third memory ID."""
    return uuid4()


def add_edge_to_db(
    db: MockDatabase,
    user_id,
    from_node_id,
    to_node_id,
    edge_type: str = "related_to",
    strength: float = 0.8,
) -> dict:
    """Helper to add an edge directly to the mock database."""
    edge = {
        "id": uuid4(),
        "user_id": user_id,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "edge_type": edge_type,
        "strength": strength,
        "confidence": 0.9,
        "causality": False,
        "bidirectional": False,
        "reason": "Test edge",
        "metadata": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    db._tables["knowledge_edges"].append(edge)
    return edge


# =============================================================================
# Create Tests
# =============================================================================

class TestEdgeCreate:
    """Tests for edge creation."""

    @pytest.mark.asyncio
    async def test_create_edge(self, repo: EdgeRepository, user_id, memory_id_1, memory_id_2):
        """Test creating a basic edge."""
        edge_create = EdgeCreate(
            user_id=user_id,
            from_node_id=memory_id_1,
            to_node_id=memory_id_2,
            edge_type=EdgeType.RELATED_TO,
            strength=0.8,
            confidence=0.9,
        )
        
        edge = await repo.create(edge_create)
        
        assert edge.id is not None
        assert edge.user_id == user_id
        assert edge.from_node_id == memory_id_1
        assert edge.to_node_id == memory_id_2
        assert edge.edge_type == EdgeType.RELATED_TO
        assert edge.strength == 0.8

    @pytest.mark.asyncio
    async def test_create_edge_with_causality(
        self,
        repo: EdgeRepository,
        user_id,
        memory_id_1,
        memory_id_2,
    ):
        """Test creating a causal edge."""
        edge_create = EdgeCreate(
            user_id=user_id,
            from_node_id=memory_id_1,
            to_node_id=memory_id_2,
            edge_type=EdgeType.LEADS_TO,
            strength=0.9,
            confidence=0.85,
            causality=True,
        )
        
        edge = await repo.create(edge_create)
        
        assert edge.edge_type == EdgeType.LEADS_TO
        assert edge.causality is True

    @pytest.mark.asyncio
    async def test_create_bidirectional_edge(
        self,
        repo: EdgeRepository,
        user_id,
        memory_id_1,
        memory_id_2,
    ):
        """Test creating a bidirectional edge."""
        edge_create = EdgeCreate(
            user_id=user_id,
            from_node_id=memory_id_1,
            to_node_id=memory_id_2,
            edge_type=EdgeType.RELATED_TO,
            strength=0.7,
            confidence=0.8,
            bidirectional=True,
        )
        
        edge = await repo.create(edge_create)
        
        assert edge.bidirectional is True


# =============================================================================
# Batch Create Tests
# =============================================================================

class TestEdgeCreateMany:
    """Tests for batch edge creation."""

    @pytest.mark.asyncio
    async def test_create_many_edges(
        self,
        repo: EdgeRepository,
        user_id,
        memory_id_1,
        memory_id_2,
        memory_id_3,
    ):
        """Test creating multiple edges in a batch."""
        edges_to_create = [
            EdgeCreate(
                user_id=user_id,
                from_node_id=memory_id_1,
                to_node_id=memory_id_2,
                edge_type=EdgeType.RELATED_TO,
                strength=0.8,
                confidence=0.9,
            ),
            EdgeCreate(
                user_id=user_id,
                from_node_id=memory_id_2,
                to_node_id=memory_id_3,
                edge_type=EdgeType.LEADS_TO,
                strength=0.7,
                confidence=0.85,
            ),
        ]
        
        edges = await repo.create_many(edges_to_create)
        
        assert len(edges) == 2
        assert edges[0].from_node_id == memory_id_1
        assert edges[1].from_node_id == memory_id_2

    @pytest.mark.asyncio
    async def test_create_many_empty_list(self, repo: EdgeRepository):
        """Test creating empty list returns empty list."""
        edges = await repo.create_many([])
        
        assert edges == []


# =============================================================================
# Read Tests
# =============================================================================

class TestEdgeRead:
    """Tests for reading edges."""

    @pytest.mark.asyncio
    async def test_get_edges_from_memory(
        self,
        repo: EdgeRepository,
        db: MockDatabase,
        user_id,
        memory_id_1,
        memory_id_2,
        memory_id_3,
    ):
        """Test getting all outgoing edges from a memory."""
        # Add edges from memory_id_1
        add_edge_to_db(db, user_id, memory_id_1, memory_id_2, "related_to")
        add_edge_to_db(db, user_id, memory_id_1, memory_id_3, "leads_to")
        # Add an edge from different memory (should not be returned)
        add_edge_to_db(db, user_id, memory_id_2, memory_id_3, "related_to")
        
        edges = await repo.get_edges_from_memory(memory_id_1, user_id)
        
        assert len(edges) == 2
        assert all(e.from_node_id == memory_id_1 for e in edges)

    @pytest.mark.asyncio
    async def test_get_edges_to_memory(
        self,
        repo: EdgeRepository,
        db: MockDatabase,
        user_id,
        memory_id_1,
        memory_id_2,
        memory_id_3,
    ):
        """Test getting all incoming edges to a memory."""
        # Add edges pointing to memory_id_3
        add_edge_to_db(db, user_id, memory_id_1, memory_id_3, "related_to")
        add_edge_to_db(db, user_id, memory_id_2, memory_id_3, "leads_to")
        # Add an edge to different memory
        add_edge_to_db(db, user_id, memory_id_1, memory_id_2, "related_to")
        
        edges = await repo.get_edges_to_memory(memory_id_3, user_id)
        
        assert len(edges) == 2
        assert all(e.to_node_id == memory_id_3 for e in edges)


# =============================================================================
# Delete Tests
# =============================================================================

class TestEdgeDelete:
    """Tests for deleting edges."""

    @pytest.mark.asyncio
    async def test_delete_for_memory(
        self,
        repo: EdgeRepository,
        db: MockDatabase,
        user_id,
        memory_id_1,
        memory_id_2,
        memory_id_3,
    ):
        """Test deleting all edges connected to a memory."""
        # Add edges connected to memory_id_1
        add_edge_to_db(db, user_id, memory_id_1, memory_id_2, "related_to")
        add_edge_to_db(db, user_id, memory_id_2, memory_id_1, "leads_to")
        # Add edge not connected to memory_id_1
        add_edge_to_db(db, user_id, memory_id_2, memory_id_3, "related_to")
        
        initial_count = len(db.get_table("knowledge_edges"))
        assert initial_count == 3
        
        deleted_count = await repo.delete_for_memory(memory_id_1, user_id)
        
        # Should have deleted 2 edges
        assert deleted_count == 2
        
        # Only 1 edge should remain
        remaining_edges = db.get_table("knowledge_edges")
        assert len(remaining_edges) == 1
        assert remaining_edges[0]["from_node_id"] == memory_id_2
        assert remaining_edges[0]["to_node_id"] == memory_id_3


# =============================================================================
# Edge Type Tests
# =============================================================================

class TestEdgeTypes:
    """Tests for different edge types."""

    @pytest.mark.asyncio
    async def test_all_edge_types(self, repo: EdgeRepository, user_id, memory_id_1, memory_id_2):
        """Test creating edges with all available types."""
        edge_types = [
            EdgeType.RELATED_TO,
            EdgeType.LEADS_TO,
            EdgeType.DEPENDS_ON,
            EdgeType.CONTRADICTS,
            EdgeType.SUPPORTS,
            EdgeType.EVOLVES_INTO,
            EdgeType.LIKES,
            EdgeType.DISLIKES,
        ]
        
        for edge_type in edge_types:
            edge_create = EdgeCreate(
                user_id=user_id,
                from_node_id=memory_id_1,
                to_node_id=memory_id_2,
                edge_type=edge_type,
                strength=0.8,
                confidence=0.9,
            )
            
            edge = await repo.create(edge_create)
            
            assert edge.edge_type == edge_type


# =============================================================================
# Count Tests
# =============================================================================

class TestEdgeCount:
    """Tests for counting edges."""

    @pytest.mark.asyncio
    async def test_count_by_user(
        self,
        repo: EdgeRepository,
        db: MockDatabase,
        user_id,
        memory_id_1,
        memory_id_2,
        memory_id_3,
    ):
        """Test counting edges for a user."""
        # Add some edges
        add_edge_to_db(db, user_id, memory_id_1, memory_id_2, "related_to")
        add_edge_to_db(db, user_id, memory_id_2, memory_id_3, "leads_to")
        
        count = await repo.count_by_user(user_id)
        
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_by_user_empty(self, repo: EdgeRepository, user_id):
        """Test counting when no edges exist."""
        count = await repo.count_by_user(user_id)
        
        assert count == 0


# =============================================================================
# User Isolation Tests
# =============================================================================

class TestUserIsolation:
    """Tests for user data isolation in edges."""

    @pytest.mark.asyncio
    async def test_edges_isolated_by_user(
        self,
        repo: EdgeRepository,
        db: MockDatabase,
        memory_id_1,
        memory_id_2,
    ):
        """Test that edges are isolated by user."""
        user_1 = uuid4()
        user_2 = uuid4()
        
        # Add edges for both users
        add_edge_to_db(db, user_1, memory_id_1, memory_id_2, "related_to")
        add_edge_to_db(db, user_2, memory_id_1, memory_id_2, "leads_to")
        
        # Get edges for user_1
        user_1_edges = await repo.get_edges_from_memory(memory_id_1, user_1)
        
        assert len(user_1_edges) == 1
        assert user_1_edges[0].edge_type == EdgeType.RELATED_TO
        
        # Get edges for user_2
        user_2_edges = await repo.get_edges_from_memory(memory_id_1, user_2)
        
        assert len(user_2_edges) == 1
        assert user_2_edges[0].edge_type == EdgeType.LEADS_TO
