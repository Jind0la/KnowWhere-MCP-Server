"""
Tests for Database Connection Manager

Tests the Database class including connection pooling,
vector encoding/decoding, transactions, and health checks.
"""

import pytest
import pytest_asyncio

from tests.mocks.database import MockDatabase


# =============================================================================
# Connection Tests
# =============================================================================

class TestDatabaseConnection:
    """Tests for database connection management."""

    @pytest_asyncio.fixture
    async def db(self) -> MockDatabase:
        """Create a fresh database instance."""
        return MockDatabase()

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, db: MockDatabase):
        """Test that connect() establishes a connection."""
        assert not db._connected
        
        await db.connect()
        
        assert db._connected
        assert db.pool is not None

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self, db: MockDatabase):
        """Test that disconnect() closes the connection."""
        await db.connect()
        assert db._connected
        
        await db.disconnect()
        
        assert not db._connected

    @pytest.mark.asyncio
    async def test_double_connect_is_safe(self, db: MockDatabase):
        """Test that connecting twice doesn't cause issues."""
        await db.connect()
        await db.connect()  # Should not raise
        
        assert db._connected

    @pytest.mark.asyncio
    async def test_double_disconnect_is_safe(self, db: MockDatabase):
        """Test that disconnecting twice doesn't cause issues."""
        await db.connect()
        await db.disconnect()
        await db.disconnect()  # Should not raise
        
        assert not db._connected


# =============================================================================
# Vector Encoding/Decoding Tests
# =============================================================================

class TestVectorEncoding:
    """Tests for pgvector encoding and decoding."""

    def test_vector_encoding_basic(self):
        """Test encoding a vector to pgvector format."""
        vector = [0.1, 0.2, 0.3]
        
        encoded = MockDatabase._encode_vector(vector)
        
        assert encoded == "[0.1,0.2,0.3]"

    def test_vector_encoding_empty(self):
        """Test encoding an empty vector."""
        vector: list[float] = []
        
        encoded = MockDatabase._encode_vector(vector)
        
        assert encoded == "[]"

    def test_vector_encoding_negative(self):
        """Test encoding vectors with negative values."""
        vector = [-0.5, 0.0, 0.5]
        
        encoded = MockDatabase._encode_vector(vector)
        
        assert encoded == "[-0.5,0.0,0.5]"

    def test_vector_decoding_basic(self):
        """Test decoding a pgvector string to list."""
        data = "[0.1,0.2,0.3]"
        
        decoded = MockDatabase._decode_vector(data)
        
        assert decoded == [0.1, 0.2, 0.3]

    def test_vector_decoding_empty(self):
        """Test decoding an empty vector string."""
        data = "[]"
        
        decoded = MockDatabase._decode_vector(data)
        
        assert decoded == []

    def test_vector_roundtrip(self):
        """Test that encoding then decoding preserves the vector."""
        original = [0.1, -0.2, 0.3, 0.0, -0.5]
        
        encoded = MockDatabase._encode_vector(original)
        decoded = MockDatabase._decode_vector(encoded)
        
        assert decoded == original


# =============================================================================
# Transaction Tests
# =============================================================================

class TestTransactions:
    """Tests for transaction support."""

    @pytest_asyncio.fixture
    async def db(self) -> MockDatabase:
        """Create a connected database."""
        db = MockDatabase()
        await db.connect()
        return db

    @pytest.mark.asyncio
    async def test_transaction_commit(self, db: MockDatabase):
        """Test that data persists after transaction commit."""
        async with db.transaction() as conn:
            await conn.execute(
                "INSERT INTO memories (user_id, content) VALUES ($1, $2)",
                "test-user-id",
                "Test content",
            )
        
        # Data should be persisted
        rows = await db.fetch("SELECT * FROM memories")
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, db: MockDatabase):
        """Test that data is rolled back on exception."""
        # Add initial data
        db.add_memory({
            "user_id": "test-user",
            "content": "Initial memory",
            "memory_type": "semantic",
        })
        
        initial_count = len(db.get_table("memories"))
        
        try:
            async with db.transaction() as conn:
                await conn.execute(
                    "INSERT INTO memories (user_id, content) VALUES ($1, $2)",
                    "test-user-id",
                    "Transaction content",
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        # Data should be rolled back (count should be same as initial)
        final_count = len(db.get_table("memories"))
        assert final_count == initial_count


# =============================================================================
# Query Tests
# =============================================================================

class TestQueries:
    """Tests for query execution methods."""

    @pytest_asyncio.fixture
    async def db(self) -> MockDatabase:
        """Create a connected database with test data."""
        db = MockDatabase()
        await db.connect()
        
        # Add test data
        from uuid import uuid4
        user_id = uuid4()
        db.add_user(user_id, "test@example.com")
        db.add_memory({
            "user_id": user_id,
            "content": "Test memory 1",
            "memory_type": "semantic",
            "importance": 5,
        })
        db.add_memory({
            "user_id": user_id,
            "content": "Test memory 2",
            "memory_type": "preference",
            "importance": 8,
        })
        
        return db

    @pytest.mark.asyncio
    async def test_fetch_returns_records(self, db: MockDatabase):
        """Test that fetch() returns multiple records."""
        rows = await db.fetch("SELECT * FROM memories")
        
        assert len(rows) == 2
        assert rows[0]["content"] in ["Test memory 1", "Test memory 2"]

    @pytest.mark.asyncio
    async def test_fetchrow_returns_single(self, db: MockDatabase):
        """Test that fetchrow() returns a single record."""
        row = await db.fetchrow("SELECT * FROM memories LIMIT 1")
        
        assert row is not None
        assert "content" in row.keys()

    @pytest.mark.asyncio
    async def test_fetchrow_returns_none_when_empty(self, db: MockDatabase):
        """Test that fetchrow() returns None when no results."""
        db.clear_table("memories")
        
        row = await db.fetchrow("SELECT * FROM memories")
        
        assert row is None

    @pytest.mark.asyncio
    async def test_fetchval_returns_scalar(self, db: MockDatabase):
        """Test that fetchval() returns a single value."""
        count = await db.fetchval("SELECT COUNT(*) FROM memories")
        
        assert count == 2

    @pytest.mark.asyncio
    async def test_fetchval_column_parameter(self, db: MockDatabase):
        """Test that fetchval() respects column parameter."""
        # SELECT 1 always returns 1
        value = await db.fetchval("SELECT 1", column=0)
        
        assert value == 1


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for database health check."""

    @pytest.mark.asyncio
    async def test_health_check_success_when_connected(self):
        """Test health check returns True when connected."""
        db = MockDatabase()
        await db.connect()
        
        result = await db.health_check()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure_when_disconnected(self):
        """Test health check returns False when disconnected."""
        db = MockDatabase()
        # Don't connect
        
        result = await db.health_check()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_after_disconnect(self):
        """Test health check returns False after disconnect."""
        db = MockDatabase()
        await db.connect()
        await db.disconnect()
        
        result = await db.health_check()
        
        assert result is False


# =============================================================================
# Acquire Context Manager Tests
# =============================================================================

class TestAcquireContextManager:
    """Tests for connection acquisition."""

    @pytest.mark.asyncio
    async def test_acquire_provides_connection(self):
        """Test that acquire() provides a working connection."""
        db = MockDatabase()
        await db.connect()
        
        async with db.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
        
        assert result == 1

    @pytest.mark.asyncio
    async def test_acquire_multiple_times(self):
        """Test that multiple acquire() calls work correctly."""
        db = MockDatabase()
        await db.connect()
        
        async with db.acquire() as conn1:
            async with db.acquire() as conn2:
                result1 = await conn1.fetchval("SELECT 1")
                result2 = await conn2.fetchval("SELECT 1")
        
        assert result1 == 1
        assert result2 == 1
