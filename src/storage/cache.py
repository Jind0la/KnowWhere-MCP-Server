"""
Redis Cache Service

Provides caching for:
- Frequently accessed memories
- User preferences
- Embeddings (to avoid re-computation)
- Session state
"""

import hashlib
import json
from typing import Any

import redis.asyncio as redis
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class CacheService:
    """
    Async Redis cache service.
    
    Provides:
    - Key-value caching with TTL
    - JSON serialization
    - Embedding caching
    - Memory caching
    - Cache invalidation
    """
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: redis.Redis | None = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is not None:
            logger.warning("Redis client already initialized")
            return
        
        logger.info("Connecting to Redis", url=self.settings.redis_url)
        
        try:
            self._client = redis.from_url(
                self.settings.redis_url,
                password=self.settings.redis_password or None,
                db=self.settings.redis_db,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info("Redis connection established")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            # Don't fail - cache is optional
            self._client = None
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._connected = False
            logger.info("Redis connection closed")
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected and self._client is not None
    
    # =========================================================================
    # Basic Operations
    # =========================================================================
    
    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        if not self.is_connected:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (None = no expiry)
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        try:
            await self.client.set(key, value, ex=ttl)
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.is_connected:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.is_connected:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception:
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self.is_connected:
            return 0
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning("Cache delete_pattern failed", pattern=pattern, error=str(e))
            return 0
    
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
        except (TypeError, ValueError) as e:
            logger.warning("JSON serialization failed", key=key, error=str(e))
            return False
    
    # =========================================================================
    # Memory Caching
    # =========================================================================
    
    def _memory_key(self, memory_id: str) -> str:
        """Generate cache key for a memory."""
        return f"memory:{memory_id}"
    
    def _user_memories_key(self, user_id: str) -> str:
        """Generate cache key for user's memory list."""
        return f"user:{user_id}:memories"
    
    def _user_preferences_key(self, user_id: str) -> str:
        """Generate cache key for user's preferences."""
        return f"user:{user_id}:preferences"
    
    async def get_memory(self, memory_id: str) -> dict | None:
        """Get a cached memory."""
        return await self.get_json(self._memory_key(memory_id))
    
    async def set_memory(
        self,
        memory_id: str,
        memory_data: dict,
        ttl: int | None = None,
    ) -> bool:
        """Cache a memory."""
        ttl = ttl or self.settings.cache_ttl_memories
        return await self.set_json(self._memory_key(memory_id), memory_data, ttl=ttl)
    
    async def invalidate_memory(self, memory_id: str) -> bool:
        """Invalidate a cached memory."""
        return await self.delete(self._memory_key(memory_id))
    
    async def get_user_preferences(self, user_id: str) -> list[dict] | None:
        """Get cached user preferences."""
        return await self.get_json(self._user_preferences_key(user_id))
    
    async def set_user_preferences(
        self,
        user_id: str,
        preferences: list[dict],
    ) -> bool:
        """Cache user preferences."""
        return await self.set_json(
            self._user_preferences_key(user_id),
            preferences,
            ttl=self.settings.cache_ttl_preferences,
        )
    
    async def invalidate_user_cache(self, user_id: str) -> int:
        """Invalidate all cache entries for a user."""
        return await self.delete_pattern(f"user:{user_id}:*")
    
    # =========================================================================
    # Embedding Caching
    # =========================================================================
    
    def _embedding_key(self, text: str) -> str:
        """Generate cache key for an embedding based on text hash."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"embedding:{text_hash}"
    
    async def get_embedding(self, text: str) -> list[float] | None:
        """Get a cached embedding."""
        result = await self.get_json(self._embedding_key(text))
        return result if isinstance(result, list) else None
    
    async def set_embedding(
        self,
        text: str,
        embedding: list[float],
        ttl: int = 86400 * 7,  # 7 days
    ) -> bool:
        """Cache an embedding."""
        return await self.set_json(self._embedding_key(text), embedding, ttl=ttl)
    
    # =========================================================================
    # Hot Memories Cache (Optimized for frequent access)
    # =========================================================================
    
    def _hot_memories_key(self, user_id: str) -> str:
        """Generate cache key for user's hot (frequently accessed) memories."""
        return f"user:{user_id}:hot_memories"
    
    async def get_hot_memories(self, user_id: str) -> list[dict] | None:
        """Get frequently accessed memories from cache."""
        return await self.get_json(self._hot_memories_key(user_id))
    
    async def set_hot_memories(
        self,
        user_id: str,
        memories: list[dict],
        ttl: int = 3600,  # 1 hour
    ) -> bool:
        """Cache hot memories with shorter TTL for freshness."""
        return await self.set_json(
            self._hot_memories_key(user_id),
            memories,
            ttl=ttl,
        )
    
    async def invalidate_hot_memories(self, user_id: str) -> bool:
        """Invalidate hot memories cache."""
        return await self.delete(self._hot_memories_key(user_id))
    
    # =========================================================================
    # Entity Relationships Cache
    # =========================================================================
    
    def _entity_relations_key(self, user_id: str, entity: str) -> str:
        """Generate cache key for entity relationships."""
        return f"user:{user_id}:entity:{entity}:relations"
    
    async def get_entity_relations(
        self,
        user_id: str,
        entity: str,
    ) -> dict | None:
        """Get cached entity relationships."""
        return await self.get_json(self._entity_relations_key(user_id, entity))
    
    async def set_entity_relations(
        self,
        user_id: str,
        entity: str,
        relations: dict,
        ttl: int = 1800,  # 30 minutes
    ) -> bool:
        """Cache entity relationships."""
        return await self.set_json(
            self._entity_relations_key(user_id, entity),
            relations,
            ttl=ttl,
        )
    
    # =========================================================================
    # Search Results Cache
    # =========================================================================
    
    def _search_cache_key(self, user_id: str, query_hash: str) -> str:
        """Generate cache key for search results."""
        return f"user:{user_id}:search:{query_hash}"
    
    async def get_search_results(
        self,
        user_id: str,
        query: str,
    ) -> list[dict] | None:
        """Get cached search results."""
        import hashlib
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return await self.get_json(self._search_cache_key(user_id, query_hash))
    
    async def set_search_results(
        self,
        user_id: str,
        query: str,
        results: list[dict],
        ttl: int = 300,  # 5 minutes - short TTL as memories change
    ) -> bool:
        """Cache search results."""
        import hashlib
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return await self.set_json(
            self._search_cache_key(user_id, query_hash),
            results,
            ttl=ttl,
        )
    
    # =========================================================================
    # Session State Cache (for consolidation)
    # =========================================================================
    
    def _session_key(self, session_id: str) -> str:
        """Generate cache key for session state."""
        return f"session:{session_id}"
    
    async def get_session_state(self, session_id: str) -> dict | None:
        """Get session state from cache."""
        return await self.get_json(self._session_key(session_id))
    
    async def set_session_state(
        self,
        session_id: str,
        state: dict,
        ttl: int = 86400,  # 24 hours
    ) -> bool:
        """Cache session state."""
        return await self.set_json(self._session_key(session_id), state, ttl=ttl)
    
    async def delete_session_state(self, session_id: str) -> bool:
        """Delete session state."""
        return await self.delete(self._session_key(session_id))
    
    # =========================================================================
    # User Stats Cache
    # =========================================================================
    
    def _user_stats_key(self, user_id: str) -> str:
        """Generate cache key for user stats."""
        return f"user:{user_id}:stats"
    
    async def get_user_stats(self, user_id: str) -> dict | None:
        """Get cached user stats."""
        return await self.get_json(self._user_stats_key(user_id))
    
    async def set_user_stats(
        self,
        user_id: str,
        stats: dict,
        ttl: int = 900,  # 15 minutes
    ) -> bool:
        """Cache user stats."""
        return await self.set_json(self._user_stats_key(user_id), stats, ttl=ttl)
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        if not self.is_connected:
            return False
        try:
            await self.client.ping()
            return True
        except Exception:
            return False


# Global cache instance
_cache: CacheService | None = None


async def get_cache() -> CacheService:
    """
    Get the global cache instance.
    
    Creates and connects if not already done.
    """
    global _cache
    
    if _cache is None:
        _cache = CacheService()
        await _cache.connect()
    
    return _cache


async def close_cache() -> None:
    """Close the global cache connection."""
    global _cache
    
    if _cache is not None:
        await _cache.disconnect()
        _cache = None
