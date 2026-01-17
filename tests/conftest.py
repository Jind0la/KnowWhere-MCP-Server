"""
Pytest Configuration and Fixtures

Provides comprehensive test fixtures including mock services,
test data factories, and utility helpers.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

# Set environment variables BEFORE importing Settings
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai-key-for-testing-1234567890")
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-for-testing")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-minimum-32-chars")

from src.config import Settings
from src.models.memory import Memory, MemorySource, MemoryStatus, MemoryType
from src.models.user import User, UserTier
from src.models.consolidation import Claim
from src.models.edge import EdgeType, KnowledgeEdge

from tests.mocks.embedding import MockEmbeddingService
from tests.mocks.llm import MockLLMService
from tests.mocks.database import MockDatabase
from tests.mocks.cache import MockCacheService


# =============================================================================
# Event Loop Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Settings Fixtures
# =============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with mock values."""
    return Settings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        database_url="postgresql://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379",
        openai_api_key="sk-test-key",
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test-key",
        rate_limit_enabled=False,
        jwt_secret_key="test-secret-key-for-testing-minimum-32-chars",
    )


# =============================================================================
# Mock Service Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def mock_embedding_service() -> MockEmbeddingService:
    """Create a mock embedding service."""
    return MockEmbeddingService(dimensions=1408)


@pytest_asyncio.fixture
async def mock_llm_service() -> MockLLMService:
    """Create a mock LLM service."""
    return MockLLMService()


@pytest_asyncio.fixture
async def mock_database() -> AsyncGenerator[MockDatabase, None]:
    """Create a mock database with connection."""
    db = MockDatabase()
    await db.connect()
    yield db
    await db.disconnect()


@pytest_asyncio.fixture
async def mock_cache() -> AsyncGenerator[MockCacheService, None]:
    """Create a mock cache service."""
    cache = MockCacheService()
    await cache.connect()
    yield cache
    await cache.disconnect()


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture
def test_user_id() -> UUID:
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def test_user(test_user_id: UUID) -> User:
    """Create a test user."""
    return User(
        id=test_user_id,
        email="test@knowwhere.ai",
        email_verified=True,
        tier=UserTier.PRO,
    )


@pytest.fixture
def test_user_free() -> User:
    """Create a test user with free tier."""
    return User(
        id=uuid4(),
        email="free@knowwhere.ai",
        email_verified=True,
        tier=UserTier.FREE,
    )


@pytest.fixture
def test_user_enterprise() -> User:
    """Create a test user with enterprise tier."""
    return User(
        id=uuid4(),
        email="enterprise@knowwhere.ai",
        email_verified=True,
        tier=UserTier.ENTERPRISE,
    )


# =============================================================================
# Memory Fixtures
# =============================================================================

@pytest.fixture
def test_memory_id() -> UUID:
    """Generate a test memory ID."""
    return uuid4()


@pytest.fixture
def test_memory(test_user: User, test_memory_id: UUID) -> Memory:
    """Create a test memory."""
    return Memory(
        id=test_memory_id,
        user_id=test_user.id,
        content="User prefers async/await over callbacks in Python",
        memory_type=MemoryType.PREFERENCE,
        embedding=[0.1] * 1408,
        entities=["async/await", "callbacks", "Python"],
        importance=8,
        confidence=0.95,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.MANUAL,
        access_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def test_memory_episodic(test_user: User) -> Memory:
    """Create a test episodic memory."""
    return Memory(
        id=uuid4(),
        user_id=test_user.id,
        content="In session #42, user mentioned they are learning FastAPI",
        memory_type=MemoryType.EPISODIC,
        embedding=[0.2] * 1408,
        entities=["FastAPI", "learning"],
        importance=5,
        confidence=0.9,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.CONVERSATION,
        access_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def test_memory_semantic(test_user: User) -> Memory:
    """Create a test semantic memory."""
    return Memory(
        id=uuid4(),
        user_id=test_user.id,
        content="TypeScript is a superset of JavaScript with static typing",
        memory_type=MemoryType.SEMANTIC,
        embedding=[0.3] * 1408,
        entities=["TypeScript", "JavaScript"],
        importance=6,
        confidence=0.99,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.MANUAL,
        access_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def test_memory_procedural(test_user: User) -> Memory:
    """Create a test procedural memory."""
    return Memory(
        id=uuid4(),
        user_id=test_user.id,
        content="To setup a React project with TypeScript: npx create-react-app myapp --template typescript",
        memory_type=MemoryType.PROCEDURAL,
        embedding=[0.4] * 1408,
        entities=["React", "TypeScript", "create-react-app"],
        importance=7,
        confidence=0.95,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.MANUAL,
        access_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def test_memory_meta(test_user: User) -> Memory:
    """Create a test meta memory."""
    return Memory(
        id=uuid4(),
        user_id=test_user.id,
        content="User is struggling with understanding async/await concepts",
        memory_type=MemoryType.META,
        embedding=[0.5] * 1408,
        entities=["async/await", "learning"],
        importance=7,
        confidence=0.85,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.CONSOLIDATION,
        access_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def test_memories_batch(test_user: User) -> list[Memory]:
    """Create a batch of test memories."""
    base_time = datetime.utcnow()
    return [
        Memory(
            id=uuid4(),
            user_id=test_user.id,
            content=f"Test memory content {i}",
            memory_type=MemoryType.SEMANTIC,
            embedding=[0.1 * (i + 1)] * 1408,
            entities=[f"entity_{i}"],
            importance=5 + (i % 5),
            confidence=0.8,
            status=MemoryStatus.ACTIVE,
            source=MemorySource.MANUAL,
            access_count=i,
            created_at=base_time - timedelta(days=i),
            updated_at=base_time - timedelta(days=i),
        )
        for i in range(10)
    ]


# =============================================================================
# Embedding Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def mock_embedding() -> list[float]:
    """Generate a mock embedding vector."""
    import random
    random.seed(42)  # Reproducible
    return [random.uniform(-1, 1) for _ in range(1408)]


@pytest.fixture
def sample_embeddings() -> list[list[float]]:
    """Generate sample embedding vectors for testing."""
    import random
    random.seed(42)
    return [
        [random.uniform(-1, 1) for _ in range(1408)]
        for _ in range(5)
    ]


# =============================================================================
# Transcript Fixtures
# =============================================================================

@pytest.fixture
def sample_transcript() -> str:
    """Sample conversation transcript for consolidation testing."""
    return """
    User: I really prefer using TypeScript over plain JavaScript.
    Assistant: That's a great choice! TypeScript adds type safety.
    User: Yes, and I always use async/await instead of callbacks.
    Assistant: Async/await makes code much more readable.
    User: I'm currently working on a FastAPI project.
    Assistant: FastAPI is excellent for building APIs with Python.
    User: I like how it handles async operations natively.
    """


@pytest.fixture
def sample_transcript_short() -> str:
    """Short transcript for edge case testing."""
    return "User: Hello"


@pytest.fixture
def sample_transcript_with_preferences() -> str:
    """Transcript with multiple preferences."""
    return """
    User: I prefer dark mode in all my IDEs.
    Assistant: Dark mode is easier on the eyes.
    User: I also like using Vim keybindings in VS Code.
    Assistant: That's a productive combination.
    User: For databases, I always choose PostgreSQL over MySQL.
    Assistant: PostgreSQL has great features for complex queries.
    """


@pytest.fixture
def sample_transcript_with_conflicts() -> str:
    """Transcript with potentially conflicting statements."""
    return """
    User: I prefer using React for frontend projects.
    Assistant: React is very popular.
    User: Actually, I've started to prefer Vue.js recently.
    Assistant: Vue.js has a gentler learning curve.
    User: Yes, I think Vue.js is better for my needs now.
    """


# =============================================================================
# Claim Fixtures
# =============================================================================

@pytest.fixture
def test_claims() -> list[Claim]:
    """Create test claims for consolidation."""
    return [
        Claim(
            claim="User prefers TypeScript over JavaScript",
            source="User statement",
            confidence=0.95,
            claim_type="preference",
            entities=["TypeScript", "JavaScript"],
        ),
        Claim(
            claim="User uses async/await instead of callbacks",
            source="User statement",
            confidence=0.9,
            claim_type="preference",
            entities=["async/await", "callbacks"],
        ),
        Claim(
            claim="User is working on a FastAPI project",
            source="User statement",
            confidence=0.85,
            claim_type="fact",
            entities=["FastAPI"],
        ),
    ]


# =============================================================================
# Edge Fixtures
# =============================================================================

@pytest.fixture
def test_edge(test_user: User, test_memory: Memory, test_memory_semantic: Memory) -> KnowledgeEdge:
    """Create a test knowledge edge."""
    return KnowledgeEdge(
        id=uuid4(),
        user_id=test_user.id,
        from_node_id=test_memory.id,
        to_node_id=test_memory_semantic.id,
        edge_type=EdgeType.RELATED_TO,
        strength=0.8,
        confidence=0.9,
        reason="Both memories mention programming concepts",
        causality=False,
        bidirectional=False,
        created_at=datetime.utcnow(),
    )


# =============================================================================
# Database Fixtures with Pre-populated Data
# =============================================================================

@pytest_asyncio.fixture
async def mock_database_with_user(
    mock_database: MockDatabase,
    test_user: User,
) -> MockDatabase:
    """Create a mock database with a test user."""
    mock_database.add_user(test_user.id, test_user.email, test_user.tier.value)
    return mock_database


@pytest_asyncio.fixture
async def mock_database_with_memories(
    mock_database_with_user: MockDatabase,
    test_user: User,
    test_memory: Memory,
) -> MockDatabase:
    """Create a mock database with user and memories."""
    mock_database_with_user.add_memory({
        "id": test_memory.id,
        "user_id": test_memory.user_id,
        "content": test_memory.content,
        "memory_type": test_memory.memory_type.value,
        "embedding": test_memory.embedding,
        "entities": test_memory.entities,
        "importance": test_memory.importance,
        "confidence": test_memory.confidence,
        "source": test_memory.source.value,
        "source_id": None,
        "metadata": {},
    })
    return mock_database_with_user


# =============================================================================
# API Key Fixtures
# =============================================================================

@pytest.fixture
def test_api_key() -> str:
    """Generate a test API key."""
    return "kw_prod_test1234567890abcdefghijklmnop"


@pytest.fixture
def test_api_key_hash() -> str:
    """Hash of the test API key."""
    import hashlib
    return hashlib.sha256("kw_prod_test1234567890abcdefghijklmnop".encode()).hexdigest()


# =============================================================================
# JWT Fixtures
# =============================================================================

@pytest.fixture
def test_jwt_secret() -> str:
    """JWT secret for testing."""
    return "test-secret-key-for-testing-minimum-32-chars"


# =============================================================================
# Utility Functions
# =============================================================================

def create_test_memory(
    user_id: UUID,
    content: str = "Test memory content",
    memory_type: MemoryType = MemoryType.SEMANTIC,
    importance: int = 5,
    entities: list[str] | None = None,
) -> Memory:
    """Factory function to create test memories."""
    return Memory(
        id=uuid4(),
        user_id=user_id,
        content=content,
        memory_type=memory_type,
        embedding=[0.1] * 1408,
        entities=entities or [],
        importance=importance,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.MANUAL,
        access_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def create_test_embedding(seed: int = 42) -> list[float]:
    """Factory function to create test embeddings."""
    import random
    random.seed(seed)
    return [random.uniform(-1, 1) for _ in range(1408)]
