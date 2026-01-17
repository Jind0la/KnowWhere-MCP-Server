"""
Real Database Integration Tests

Tests that run against the actual Supabase database.
These tests verify end-to-end functionality with real infrastructure.

Run with: pytest tests/test_real_database.py -v
"""

import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio

from src.config import Settings
from src.storage.database import Database
from src.storage.repositories.memory_repo import MemoryRepository
from src.storage.repositories.edge_repo import EdgeRepository
from src.models.memory import MemoryCreate, MemoryType, MemorySource
from src.models.edge import EdgeCreate, EdgeType
from src.services.embedding import EmbeddingService


# Skip all tests if not in integration mode
pytestmark = pytest.mark.asyncio


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def real_db():
    """Create a real database connection using actual .env settings."""
    # Load settings directly from .env, bypassing conftest mocks
    settings = Settings()
    db = Database(settings)
    await db.connect()
    yield db
    await db.disconnect()


@pytest_asyncio.fixture
async def embedding_service():
    """Create a real embedding service with actual API key."""
    settings = Settings()
    service = EmbeddingService(settings=settings)
    yield service


@pytest.fixture
def test_user_id():
    """Generate a unique test user ID."""
    return uuid4()


# =============================================================================
# Database Connection Tests
# =============================================================================

class TestRealDatabaseConnection:
    """Tests for real database connection."""

    async def test_database_health_check(self, real_db: Database):
        """Test that database is healthy."""
        is_healthy = await real_db.health_check()
        assert is_healthy is True

    async def test_database_can_query(self, real_db: Database):
        """Test that we can run queries."""
        result = await real_db.fetchval("SELECT 1")
        assert result == 1

    async def test_pgvector_extension_available(self, real_db: Database):
        """Test that pgvector extension is available."""
        result = await real_db.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
        )
        assert result >= 1


# =============================================================================
# Memory Repository Real Tests
# =============================================================================

class TestRealMemoryRepository:
    """Tests for memory repository with real database."""

    async def test_create_and_retrieve_memory(
        self,
        real_db: Database,
        embedding_service: EmbeddingService,
        test_user_id,
    ):
        """Test creating and retrieving a memory."""
        # First, create a test user
        await real_db.execute(
            """
            INSERT INTO users (id, email, tier)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
            """,
            test_user_id,
            f"test-{test_user_id}@example.com",
            "pro",
        )
        
        repo = MemoryRepository(real_db)
        
        # Generate real embedding
        embedding = await embedding_service.embed("User prefers Python for backend development")
        
        # Create memory
        memory_create = MemoryCreate(
            user_id=test_user_id,
            content="User prefers Python for backend development",
            memory_type=MemoryType.PREFERENCE,
            embedding=embedding,
            entities=["Python"],
            importance=8,
            confidence=0.9,
        )
        
        created_memory = await repo.create(memory_create)
        
        assert created_memory.id is not None
        assert created_memory.content == "User prefers Python for backend development"
        assert created_memory.memory_type == MemoryType.PREFERENCE
        
        # Retrieve by ID
        retrieved = await repo.get_by_id(created_memory.id, test_user_id)
        
        assert retrieved is not None
        assert retrieved.id == created_memory.id
        assert retrieved.content == created_memory.content
        
        # Cleanup
        await real_db.execute(
            "DELETE FROM memories WHERE id = $1",
            created_memory.id,
        )
        await real_db.execute(
            "DELETE FROM users WHERE id = $1",
            test_user_id,
        )

    async def test_vector_similarity_search(
        self,
        real_db: Database,
        embedding_service: EmbeddingService,
        test_user_id,
    ):
        """Test vector similarity search."""
        # Create test user
        await real_db.execute(
            """
            INSERT INTO users (id, email, tier)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
            """,
            test_user_id,
            f"test-{test_user_id}@example.com",
            "pro",
        )
        
        repo = MemoryRepository(real_db)
        
        # Create some memories with real embeddings
        memories_to_create = [
            ("User loves Python programming", ["Python"], 9),
            ("User prefers React for frontend", ["React"], 8),
            ("User uses PostgreSQL for databases", ["PostgreSQL"], 7),
        ]
        
        created_ids = []
        for content, entities, importance in memories_to_create:
            embedding = await embedding_service.embed(content)
            memory = await repo.create(MemoryCreate(
                user_id=test_user_id,
                content=content,
                memory_type=MemoryType.PREFERENCE,
                embedding=embedding,
                entities=entities,
                importance=importance,
            ))
            created_ids.append(memory.id)
        
        # Search for Python-related content
        search_embedding = await embedding_service.embed("What programming language does the user like?")
        
        results = await repo.search_similar(
            embedding=search_embedding,
            user_id=test_user_id,
            limit=3,
        )
        
        assert len(results) > 0
        # Python-related memory should be most similar
        assert "Python" in results[0].content
        
        # Cleanup
        for memory_id in created_ids:
            await real_db.execute("DELETE FROM memories WHERE id = $1", memory_id)
        await real_db.execute("DELETE FROM users WHERE id = $1", test_user_id)

    async def test_soft_delete_memory(
        self,
        real_db: Database,
        embedding_service: EmbeddingService,
        test_user_id,
    ):
        """Test soft deleting a memory."""
        # Create test user
        await real_db.execute(
            """
            INSERT INTO users (id, email, tier)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
            """,
            test_user_id,
            f"test-{test_user_id}@example.com",
            "pro",
        )
        
        repo = MemoryRepository(real_db)
        
        # Create memory
        embedding = await embedding_service.embed("Test memory to delete")
        memory = await repo.create(MemoryCreate(
            user_id=test_user_id,
            content="Test memory to delete",
            memory_type=MemoryType.SEMANTIC,
            embedding=embedding,
        ))
        
        # Soft delete
        deleted = await repo.soft_delete(memory.id, test_user_id)
        assert deleted is True
        
        # Should not be retrievable anymore (status = deleted)
        retrieved = await repo.get_by_id(memory.id, test_user_id)
        assert retrieved is None
        
        # Cleanup (hard delete)
        await real_db.execute("DELETE FROM memories WHERE id = $1", memory.id)
        await real_db.execute("DELETE FROM users WHERE id = $1", test_user_id)


# =============================================================================
# Edge Repository Real Tests
# =============================================================================

class TestRealEdgeRepository:
    """Tests for edge repository with real database."""

    async def test_create_and_retrieve_edge(
        self,
        real_db: Database,
        embedding_service: EmbeddingService,
        test_user_id,
    ):
        """Test creating and retrieving knowledge graph edges."""
        # Create test user
        await real_db.execute(
            """
            INSERT INTO users (id, email, tier)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
            """,
            test_user_id,
            f"test-{test_user_id}@example.com",
            "pro",
        )
        
        memory_repo = MemoryRepository(real_db)
        edge_repo = EdgeRepository(real_db)
        
        # Create two memories
        embedding1 = await embedding_service.embed("User likes Python")
        memory1 = await memory_repo.create(MemoryCreate(
            user_id=test_user_id,
            content="User likes Python",
            memory_type=MemoryType.PREFERENCE,
            embedding=embedding1,
        ))
        
        embedding2 = await embedding_service.embed("User uses FastAPI framework")
        memory2 = await memory_repo.create(MemoryCreate(
            user_id=test_user_id,
            content="User uses FastAPI framework",
            memory_type=MemoryType.PREFERENCE,
            embedding=embedding2,
        ))
        
        # Create edge
        edge = await edge_repo.create(EdgeCreate(
            user_id=test_user_id,
            from_node_id=memory1.id,
            to_node_id=memory2.id,
            edge_type=EdgeType.RELATED_TO,
            strength=0.8,
        ))
        
        assert edge.id is not None
        assert edge.from_node_id == memory1.id
        assert edge.to_node_id == memory2.id
        
        # Get edges from memory1
        edges = await edge_repo.get_edges_from(memory1.id, test_user_id)
        assert len(edges) >= 1
        
        # Cleanup
        await real_db.execute("DELETE FROM knowledge_edges WHERE id = $1", edge.id)
        await real_db.execute("DELETE FROM memories WHERE id = $1", memory1.id)
        await real_db.execute("DELETE FROM memories WHERE id = $1", memory2.id)
        await real_db.execute("DELETE FROM users WHERE id = $1", test_user_id)


# =============================================================================
# Embedding Service Real Tests
# =============================================================================

class TestRealEmbeddingService:
    """Tests for embedding service with real OpenAI API."""

    async def test_generate_embedding(self, embedding_service: EmbeddingService):
        """Test generating a real embedding."""
        text = "User prefers TypeScript for frontend development"
        
        embedding = await embedding_service.embed(text)
        
        assert embedding is not None
        assert len(embedding) == 1408  # text-embedding-3-large dimension
        assert all(isinstance(x, float) for x in embedding)

    async def test_embedding_similarity(self, embedding_service: EmbeddingService):
        """Test that similar texts have similar embeddings."""
        text1 = "I love programming in Python"
        text2 = "Python is my favorite programming language"
        text3 = "I enjoy cooking Italian food"
        
        emb1 = await embedding_service.embed(text1)
        emb2 = await embedding_service.embed(text2)
        emb3 = await embedding_service.embed(text3)
        
        # Calculate cosine similarity
        def cosine_similarity(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            return dot / (norm_a * norm_b)
        
        sim_1_2 = cosine_similarity(emb1, emb2)
        sim_1_3 = cosine_similarity(emb1, emb3)
        
        # Python texts should be more similar than Python vs cooking
        assert sim_1_2 > sim_1_3
        print(f"Python similarity: {sim_1_2:.4f}")
        print(f"Python vs cooking: {sim_1_3:.4f}")
