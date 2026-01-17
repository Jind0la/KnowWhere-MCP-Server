"""
Rate Limiting Middleware

Implements request rate limiting using Redis.
"""

import asyncio
import time
from typing import Optional

import structlog

from src.config import Settings, get_settings
from src.storage.cache import CacheService, get_cache

logger = structlog.get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    
    Features:
    - Per-user rate limiting
    - Configurable requests per minute
    - Burst allowance
    - Redis-backed for distributed deployments
    """
    
    def __init__(
        self,
        settings: Settings | None = None,
        cache: CacheService | None = None,
    ):
        self.settings = settings or get_settings()
        self._cache = cache
        self._enabled = self.settings.rate_limit_enabled
        self._default_rpm = self.settings.rate_limit_requests_per_minute
    
    async def _get_cache(self) -> CacheService:
        """Get cache service."""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache
    
    async def is_allowed(
        self,
        identifier: str,
        requests_per_minute: int | None = None,
    ) -> tuple[bool, dict]:
        """
        Check if a request is allowed under rate limits.
        
        Uses sliding window algorithm for smooth rate limiting.
        
        Args:
            identifier: User ID or IP address
            requests_per_minute: Override default rate limit
            
        Returns:
            Tuple of (is_allowed, rate_info)
            rate_info contains: remaining, reset_at, limit
        """
        if not self._enabled:
            return True, {"remaining": -1, "reset_at": 0, "limit": -1}
        
        rpm = requests_per_minute or self._default_rpm
        cache = await self._get_cache()
        
        if not cache.is_connected:
            # If Redis unavailable, allow request (fail open)
            logger.warning("Rate limiter: Redis unavailable, allowing request")
            return True, {"remaining": rpm, "reset_at": 0, "limit": rpm}
        
        key = f"ratelimit:{identifier}"
        now = time.time()
        window_start = now - 60  # 1 minute sliding window
        
        try:
            # Use Redis sorted set for sliding window
            pipe = cache.client.pipeline()
            
            # Remove old entries outside window
            await cache.client.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            current_count = await cache.client.zcard(key)
            
            if current_count >= rpm:
                # Rate limit exceeded
                oldest = await cache.client.zrange(key, 0, 0, withscores=True)
                reset_at = oldest[0][1] + 60 if oldest else now + 60
                
                logger.warning(
                    "Rate limit exceeded",
                    identifier=identifier,
                    current=current_count,
                    limit=rpm,
                )
                
                return False, {
                    "remaining": 0,
                    "reset_at": int(reset_at),
                    "limit": rpm,
                }
            
            # Add current request
            await cache.client.zadd(key, {f"{now}:{id(now)}": now})
            
            # Set expiry on key (cleanup)
            await cache.client.expire(key, 120)  # 2 minutes
            
            remaining = rpm - current_count - 1
            
            return True, {
                "remaining": max(0, remaining),
                "reset_at": int(now + 60),
                "limit": rpm,
            }
            
        except Exception as e:
            logger.error("Rate limiter error", error=str(e))
            # Fail open on errors
            return True, {"remaining": rpm, "reset_at": 0, "limit": rpm}
    
    async def get_rate_info(self, identifier: str) -> dict:
        """Get current rate limit info for an identifier."""
        cache = await self._get_cache()
        
        if not cache.is_connected:
            return {"remaining": -1, "reset_at": 0, "limit": self._default_rpm}
        
        key = f"ratelimit:{identifier}"
        now = time.time()
        window_start = now - 60
        
        try:
            # Clean old entries
            await cache.client.zremrangebyscore(key, 0, window_start)
            
            # Count current
            current_count = await cache.client.zcard(key)
            remaining = max(0, self._default_rpm - current_count)
            
            return {
                "remaining": remaining,
                "reset_at": int(now + 60),
                "limit": self._default_rpm,
            }
        except Exception:
            return {"remaining": -1, "reset_at": 0, "limit": self._default_rpm}
    
    async def reset(self, identifier: str) -> bool:
        """Reset rate limit for an identifier (admin use)."""
        cache = await self._get_cache()
        
        if not cache.is_connected:
            return False
        
        key = f"ratelimit:{identifier}"
        await cache.client.delete(key)
        
        logger.info("Rate limit reset", identifier=identifier)
        return True


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


async def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def check_rate_limit(
    user_id: str,
    requests_per_minute: int | None = None,
) -> tuple[bool, dict]:
    """
    Check rate limit for a user.
    
    Convenience function for checking rate limits.
    """
    limiter = await get_rate_limiter()
    return await limiter.is_allowed(user_id, requests_per_minute)
