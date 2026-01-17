"""
Mock Cache Service

In-memory cache implementation for testing without Redis.
"""

import hashlib
import json
import time
from typing import Any


class MockCacheService:
    """
    In-memory cache service for testing.
    
    Simulates Redis behavior with a Python dictionary.
    Supports TTL expiration and all cache operations.
    """
    
    def __init__(self, default_ttl: int = 3600):
        self._store: dict[str, tuple[Any, float | None]] = {}  # key -> (value, expires_at)
        self._connected = True
        self.default_ttl = default_ttl
        
        # Call tracking
        self._get_call_count = 0
        self._set_call_count = 0
        self._delete_call_count = 0
    
    async def connect(self) -> None:
        """Simulate connection."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    @property
    def client(self) -> "MockCacheService":
        """Return self as client for compatibility."""
        return self
    
    def pipeline(self):
        """Return self as pipeline for compatibility (no-op in mock)."""
        return self
    
    # =========================================================================
    # Basic Operations
    # =========================================================================
    
    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        self._get_call_count += 1
        
        if not self._connected:
            return None
        
        self._cleanup_expired()
        
        if key in self._store:
            value, expires_at = self._store[key]
            if expires_at is None or expires_at > time.time():
                return value
            else:
                # Expired
                del self._store[key]
        
        return None
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
        ex: int | None = None,  # Redis compatibility
    ) -> bool:
        """Set a value in cache."""
        self._set_call_count += 1
        
        if not self._connected:
            return False
        
        # Use ex if provided (Redis compatibility)
        actual_ttl = ex or ttl
        
        expires_at = None
        if actual_ttl:
            expires_at = time.time() + actual_ttl
        
        self._store[key] = (value, expires_at)
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        self._delete_call_count += 1
        
        if not self._connected:
            return False
        
        if key in self._store:
            del self._store[key]
            return True
        return False
    
    async def exists(self, key: str) -> int:
        """Check if key exists (returns count for Redis compatibility)."""
        if not self._connected:
            return 0
        
        self._cleanup_expired()
        return 1 if key in self._store else 0
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self._connected:
            return 0
        
        # Simple pattern matching (supports * as wildcard)
        import fnmatch
        
        keys_to_delete = [
            k for k in self._store.keys()
            if fnmatch.fnmatch(k, pattern)
        ]
        
        for key in keys_to_delete:
            del self._store[key]
        
        return len(keys_to_delete)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key."""
        if key in self._store:
            value, _ = self._store[key]
            self._store[key] = (value, time.time() + seconds)
            return True
        return False
    
    async def ping(self) -> bool:
        """Ping the cache."""
        return self._connected
    
    # =========================================================================
    # Redis Sorted Set Operations (for rate limiting)
    # =========================================================================
    
    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        """Add to sorted set."""
        if not self._connected:
            return 0
        
        if key not in self._store:
            self._store[key] = ({}, None)
        
        zset, expires_at = self._store[key]
        if not isinstance(zset, dict):
            zset = {}
        
        added = 0
        for member, score in mapping.items():
            if member not in zset:
                added += 1
            zset[member] = score
        
        self._store[key] = (zset, expires_at)
        return added
    
    async def zremrangebyscore(
        self,
        key: str,
        min_score: float,
        max_score: float,
    ) -> int:
        """Remove members from sorted set by score range."""
        if not self._connected or key not in self._store:
            return 0
        
        zset, expires_at = self._store[key]
        if not isinstance(zset, dict):
            return 0
        
        to_remove = [
            member for member, score in zset.items()
            if min_score <= score <= max_score
        ]
        
        for member in to_remove:
            del zset[member]
        
        self._store[key] = (zset, expires_at)
        return len(to_remove)
    
    async def zcard(self, key: str) -> int:
        """Get cardinality of sorted set."""
        if not self._connected or key not in self._store:
            return 0
        
        zset, _ = self._store[key]
        if isinstance(zset, dict):
            return len(zset)
        return 0
    
    async def zrange(
        self,
        key: str,
        start: int,
        stop: int,
        withscores: bool = False,
    ) -> list:
        """Get range from sorted set."""
        if not self._connected or key not in self._store:
            return []
        
        zset, _ = self._store[key]
        if not isinstance(zset, dict):
            return []
        
        # Sort by score
        sorted_items = sorted(zset.items(), key=lambda x: x[1])
        
        # Handle negative indices
        if stop == -1:
            stop = len(sorted_items)
        else:
            stop += 1
        
        sliced = sorted_items[start:stop]
        
        if withscores:
            return sliced
        return [member for member, _ in sliced]
    
    async def scan_iter(self, match: str = "*"):
        """Iterate over keys matching pattern."""
        import fnmatch
        
        for key in self._store.keys():
            if fnmatch.fnmatch(key, match):
                yield key
    
    # =========================================================================
    # JSON Operations
    # =========================================================================
    
    async def get_json(self, key: str) -> dict | list | None:
        """Get and deserialize JSON value."""
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    async def set_json(
        self,
        key: str,
        value: dict | list,
        ttl: int | None = None,
    ) -> bool:
        """Serialize and set JSON value."""
        try:
            serialized = json.dumps(value)
            return await self.set(key, serialized, ttl=ttl)
        except (TypeError, ValueError):
            return False
    
    # =========================================================================
    # Memory Caching
    # =========================================================================
    
    def _memory_key(self, memory_id: str) -> str:
        return f"memory:{memory_id}"
    
    def _user_memories_key(self, user_id: str) -> str:
        return f"user:{user_id}:memories"
    
    def _user_preferences_key(self, user_id: str) -> str:
        return f"user:{user_id}:preferences"
    
    async def get_memory(self, memory_id: str) -> dict | None:
        return await self.get_json(self._memory_key(memory_id))
    
    async def set_memory(
        self,
        memory_id: str,
        memory_data: dict,
        ttl: int | None = None,
    ) -> bool:
        return await self.set_json(
            self._memory_key(memory_id),
            memory_data,
            ttl=ttl or self.default_ttl,
        )
    
    async def invalidate_memory(self, memory_id: str) -> bool:
        return await self.delete(self._memory_key(memory_id))
    
    async def get_user_preferences(self, user_id: str) -> list[dict] | None:
        return await self.get_json(self._user_preferences_key(user_id))
    
    async def set_user_preferences(
        self,
        user_id: str,
        preferences: list[dict],
    ) -> bool:
        return await self.set_json(
            self._user_preferences_key(user_id),
            preferences,
            ttl=86400,  # 24 hours
        )
    
    async def invalidate_user_cache(self, user_id: str) -> int:
        return await self.delete_pattern(f"user:{user_id}:*")
    
    # =========================================================================
    # Embedding Caching
    # =========================================================================
    
    def _embedding_key(self, text: str) -> str:
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"embedding:{text_hash}"
    
    async def get_embedding(self, text: str) -> list[float] | None:
        result = await self.get_json(self._embedding_key(text))
        return result if isinstance(result, list) else None
    
    async def set_embedding(
        self,
        text: str,
        embedding: list[float],
        ttl: int = 86400 * 7,
    ) -> bool:
        return await self.set_json(self._embedding_key(text), embedding, ttl=ttl)
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> bool:
        return self._connected
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _cleanup_expired(self) -> None:
        """Remove expired keys."""
        now = time.time()
        expired_keys = [
            key for key, (_, expires_at) in self._store.items()
            if expires_at is not None and expires_at <= now
        ]
        for key in expired_keys:
            del self._store[key]
    
    def reset_call_counts(self) -> None:
        """Reset call counters."""
        self._get_call_count = 0
        self._set_call_count = 0
        self._delete_call_count = 0
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._store.clear()
    
    @property
    def get_call_count(self) -> int:
        return self._get_call_count
    
    @property
    def set_call_count(self) -> int:
        return self._set_call_count
    
    @property
    def delete_call_count(self) -> int:
        return self._delete_call_count
    
    def get_all_keys(self) -> list[str]:
        """Get all keys in cache (for testing)."""
        self._cleanup_expired()
        return list(self._store.keys())
    
    def get_raw(self, key: str) -> tuple[Any, float | None] | None:
        """Get raw value with expiration (for testing)."""
        return self._store.get(key)


# Convenience function to match the real cache pattern
async def get_mock_cache() -> MockCacheService:
    """Get a mock cache instance."""
    cache = MockCacheService()
    await cache.connect()
    return cache
