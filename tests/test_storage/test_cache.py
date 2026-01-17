"""
Tests for Redis Cache Service

Tests the CacheService class including basic operations,
JSON handling, embedding caching, and memory caching.
"""

import time

import pytest
import pytest_asyncio

from tests.mocks.cache import MockCacheService


# =============================================================================
# Connection Tests
# =============================================================================

class TestCacheConnection:
    """Tests for cache connection management."""

    @pytest.mark.asyncio
    async def test_connect_ping(self):
        """Test that connect() establishes connection."""
        cache = MockCacheService()
        
        await cache.connect()
        
        assert cache.is_connected
        result = await cache.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_closes_connection(self):
        """Test that disconnect() closes connection."""
        cache = MockCacheService()
        await cache.connect()
        
        await cache.disconnect()
        
        assert not cache.is_connected

    @pytest.mark.asyncio
    async def test_graceful_disconnect(self):
        """Test that operations fail gracefully when disconnected."""
        cache = MockCacheService()
        await cache.connect()
        await cache.disconnect()
        
        # Should return None, not raise
        result = await cache.get("any-key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_operations_return_default_when_disconnected(self):
        """Test that set returns False when disconnected."""
        cache = MockCacheService()
        # Don't connect
        cache._connected = False
        
        result = await cache.set("key", "value")
        
        assert result is False


# =============================================================================
# Basic Operations Tests
# =============================================================================

class TestBasicOperations:
    """Tests for basic cache operations."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache."""
        cache = MockCacheService()
        await cache.connect()
        return cache

    @pytest.mark.asyncio
    async def test_set_get_string(self, cache: MockCacheService):
        """Test setting and getting a string value."""
        await cache.set("test-key", "test-value")
        
        result = await cache.get("test-key")
        
        assert result == "test-value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, cache: MockCacheService):
        """Test that getting a nonexistent key returns None."""
        result = await cache.get("nonexistent-key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_key(self, cache: MockCacheService):
        """Test deleting a key."""
        await cache.set("key-to-delete", "value")
        
        result = await cache.delete("key-to-delete")
        
        assert result is True
        assert await cache.get("key-to-delete") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, cache: MockCacheService):
        """Test deleting a nonexistent key returns False."""
        result = await cache.delete("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_1_for_existing(self, cache: MockCacheService):
        """Test exists() returns 1 for existing keys."""
        await cache.set("existing-key", "value")
        
        result = await cache.exists("existing-key")
        
        assert result == 1

    @pytest.mark.asyncio
    async def test_exists_returns_0_for_nonexistent(self, cache: MockCacheService):
        """Test exists() returns 0 for nonexistent keys."""
        result = await cache.exists("nonexistent-key")
        
        assert result == 0


# =============================================================================
# TTL Tests
# =============================================================================

class TestTTLExpiry:
    """Tests for TTL-based expiration."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache."""
        cache = MockCacheService()
        await cache.connect()
        return cache

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache: MockCacheService):
        """Test that keys expire after TTL."""
        # Set with 1 second TTL
        await cache.set("expiring-key", "value", ttl=1)
        
        # Should exist immediately
        assert await cache.get("expiring-key") == "value"
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be gone
        assert await cache.get("expiring-key") is None

    @pytest.mark.asyncio
    async def test_set_without_ttl_persists(self, cache: MockCacheService):
        """Test that keys without TTL persist."""
        await cache.set("persistent-key", "value")
        
        # Wait a bit
        time.sleep(0.1)
        
        # Should still exist
        assert await cache.get("persistent-key") == "value"

    @pytest.mark.asyncio
    async def test_expire_sets_ttl(self, cache: MockCacheService):
        """Test that expire() sets TTL on existing key."""
        await cache.set("key", "value")
        
        await cache.expire("key", 1)
        
        # Should exist immediately
        assert await cache.get("key") == "value"
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be gone
        assert await cache.get("key") is None


# =============================================================================
# JSON Operations Tests
# =============================================================================

class TestJSONOperations:
    """Tests for JSON serialization/deserialization."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache."""
        cache = MockCacheService()
        await cache.connect()
        return cache

    @pytest.mark.asyncio
    async def test_set_get_json_dict(self, cache: MockCacheService):
        """Test setting and getting a JSON dictionary."""
        data = {"name": "test", "value": 42, "active": True}
        
        await cache.set_json("json-key", data)
        result = await cache.get_json("json-key")
        
        assert result == data

    @pytest.mark.asyncio
    async def test_set_get_json_list(self, cache: MockCacheService):
        """Test setting and getting a JSON list."""
        data = [1, 2, 3, "four", {"five": 5}]
        
        await cache.set_json("list-key", data)
        result = await cache.get_json("list-key")
        
        assert result == data

    @pytest.mark.asyncio
    async def test_get_json_invalid_returns_none(self, cache: MockCacheService):
        """Test that invalid JSON returns None."""
        # Set raw invalid JSON
        await cache.set("invalid-json", "not valid json {")
        
        result = await cache.get_json("invalid-json")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_json_nonexistent_returns_none(self, cache: MockCacheService):
        """Test that nonexistent key returns None."""
        result = await cache.get_json("nonexistent")
        
        assert result is None


# =============================================================================
# Pattern Deletion Tests
# =============================================================================

class TestPatternDeletion:
    """Tests for wildcard pattern deletion."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache with test data."""
        cache = MockCacheService()
        await cache.connect()
        
        # Add test keys
        await cache.set("user:123:preferences", "prefs")
        await cache.set("user:123:memories", "mems")
        await cache.set("user:123:stats", "stats")
        await cache.set("user:456:preferences", "prefs")
        await cache.set("other:key", "value")
        
        return cache

    @pytest.mark.asyncio
    async def test_delete_pattern(self, cache: MockCacheService):
        """Test deleting keys by pattern."""
        deleted = await cache.delete_pattern("user:123:*")
        
        assert deleted == 3
        assert await cache.get("user:123:preferences") is None
        assert await cache.get("user:456:preferences") == "prefs"
        assert await cache.get("other:key") == "value"

    @pytest.mark.asyncio
    async def test_delete_pattern_no_matches(self, cache: MockCacheService):
        """Test delete_pattern with no matches."""
        deleted = await cache.delete_pattern("nonexistent:*")
        
        assert deleted == 0


# =============================================================================
# Embedding Cache Tests
# =============================================================================

class TestEmbeddingCache:
    """Tests for embedding-specific caching."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache."""
        cache = MockCacheService()
        await cache.connect()
        return cache

    @pytest.mark.asyncio
    async def test_embedding_cache_hit(self, cache: MockCacheService):
        """Test caching and retrieving an embedding."""
        embedding = [0.1, 0.2, 0.3] * 469 + [0.1]  # 1408 dimensions
        
        await cache.set_embedding("test text", embedding)
        result = await cache.get_embedding("test text")
        
        assert result == embedding

    @pytest.mark.asyncio
    async def test_embedding_cache_miss(self, cache: MockCacheService):
        """Test that cache miss returns None."""
        result = await cache.get_embedding("uncached text")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_embedding_same_text_same_key(self, cache: MockCacheService):
        """Test that same text produces same cache key."""
        embedding = [0.5] * 1408
        text = "identical text"
        
        await cache.set_embedding(text, embedding)
        
        # Should get same embedding back
        result = await cache.get_embedding(text)
        assert result == embedding

    @pytest.mark.asyncio
    async def test_embedding_different_text_different_key(self, cache: MockCacheService):
        """Test that different text produces different cache keys."""
        embedding1 = [0.1] * 1408
        embedding2 = [0.2] * 1408
        
        await cache.set_embedding("text one", embedding1)
        await cache.set_embedding("text two", embedding2)
        
        assert await cache.get_embedding("text one") == embedding1
        assert await cache.get_embedding("text two") == embedding2


# =============================================================================
# Memory Cache Tests
# =============================================================================

class TestMemoryCache:
    """Tests for memory-specific caching."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache."""
        cache = MockCacheService()
        await cache.connect()
        return cache

    @pytest.mark.asyncio
    async def test_memory_cache(self, cache: MockCacheService):
        """Test caching a memory."""
        memory_data = {
            "id": "test-id",
            "content": "Test content",
            "memory_type": "semantic",
        }
        
        await cache.set_memory("test-id", memory_data)
        result = await cache.get_memory("test-id")
        
        assert result == memory_data

    @pytest.mark.asyncio
    async def test_invalidate_memory(self, cache: MockCacheService):
        """Test invalidating a memory cache entry."""
        await cache.set_memory("mem-id", {"content": "data"})
        
        await cache.invalidate_memory("mem-id")
        
        assert await cache.get_memory("mem-id") is None

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, cache: MockCacheService):
        """Test invalidating all cache entries for a user."""
        user_id = "user-123"
        
        # Set various user-related cache entries
        await cache.set_json(f"user:{user_id}:preferences", [{"pref": 1}])
        await cache.set_json(f"user:{user_id}:memories", [{"mem": 1}])
        await cache.set_json(f"user:{user_id}:stats", {"count": 10})
        
        # Also set an entry for another user
        await cache.set_json("user:other:preferences", [{"pref": 2}])
        
        deleted = await cache.invalidate_user_cache(user_id)
        
        assert deleted == 3
        assert await cache.get_json(f"user:{user_id}:preferences") is None
        assert await cache.get_json("user:other:preferences") is not None


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for cache health check."""

    @pytest.mark.asyncio
    async def test_health_check_when_connected(self):
        """Test health check returns True when connected."""
        cache = MockCacheService()
        await cache.connect()
        
        result = await cache.health_check()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_when_disconnected(self):
        """Test health check returns False when disconnected."""
        cache = MockCacheService()
        # Don't connect
        cache._connected = False
        
        result = await cache.health_check()
        
        assert result is False


# =============================================================================
# Call Tracking Tests
# =============================================================================

class TestCallTracking:
    """Tests for call count tracking."""

    @pytest_asyncio.fixture
    async def cache(self) -> MockCacheService:
        """Create a connected cache."""
        cache = MockCacheService()
        await cache.connect()
        return cache

    @pytest.mark.asyncio
    async def test_call_counts_are_tracked(self, cache: MockCacheService):
        """Test that method calls are counted."""
        await cache.set("key", "value")
        await cache.get("key")
        await cache.get("key")
        await cache.delete("key")
        
        assert cache.set_call_count == 1
        assert cache.get_call_count == 2
        assert cache.delete_call_count == 1

    @pytest.mark.asyncio
    async def test_reset_call_counts(self, cache: MockCacheService):
        """Test that call counts can be reset."""
        await cache.set("key", "value")
        await cache.get("key")
        
        cache.reset_call_counts()
        
        assert cache.set_call_count == 0
        assert cache.get_call_count == 0
