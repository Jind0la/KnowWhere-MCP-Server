"""
Tests for Rate Limiter

Tests the RateLimiter class including rate limiting logic,
sliding window, and Redis fallback behavior.
"""

import pytest
import pytest_asyncio

from src.config import Settings
from src.middleware.rate_limit import RateLimiter, check_rate_limit
from tests.mocks.cache import MockCacheService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_settings_enabled() -> Settings:
    """Create test settings with rate limiting enabled."""
    return Settings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        database_url="postgresql://test:test@localhost:5432/test",
        openai_api_key="sk-test-key",
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test-key",
        rate_limit_enabled=True,
        rate_limit_requests_per_minute=10,  # Low limit for testing
    )


@pytest.fixture
def test_settings_disabled() -> Settings:
    """Create test settings with rate limiting disabled."""
    return Settings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        database_url="postgresql://test:test@localhost:5432/test",
        openai_api_key="sk-test-key",
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test-key",
        rate_limit_enabled=False,
    )


@pytest_asyncio.fixture
async def mock_cache() -> MockCacheService:
    """Create a connected mock cache."""
    cache = MockCacheService()
    await cache.connect()
    return cache


@pytest_asyncio.fixture
async def rate_limiter(
    test_settings_enabled: Settings,
    mock_cache: MockCacheService,
) -> RateLimiter:
    """Create a rate limiter with mock cache."""
    return RateLimiter(settings=test_settings_enabled, cache=mock_cache)


@pytest_asyncio.fixture
async def rate_limiter_disabled(
    test_settings_disabled: Settings,
    mock_cache: MockCacheService,
) -> RateLimiter:
    """Create a disabled rate limiter."""
    return RateLimiter(settings=test_settings_disabled, cache=mock_cache)


# =============================================================================
# Basic Rate Limiting Tests
# =============================================================================

class TestBasicRateLimiting:
    """Tests for basic rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, rate_limiter: RateLimiter):
        """Test that first request is always allowed."""
        is_allowed, rate_info = await rate_limiter.is_allowed("user-123")
        
        assert is_allowed is True
        assert rate_info["remaining"] >= 0

    @pytest.mark.asyncio
    async def test_under_limit_allowed(self, rate_limiter: RateLimiter):
        """Test that requests under limit are allowed."""
        user_id = "user-under-limit"
        
        # Make 5 requests (limit is 10)
        for _ in range(5):
            is_allowed, rate_info = await rate_limiter.is_allowed(user_id)
            assert is_allowed is True
        
        # Should still have remaining
        assert rate_info["remaining"] >= 0

    @pytest.mark.asyncio
    async def test_at_limit_blocked(self, rate_limiter: RateLimiter):
        """Test that requests at limit are blocked."""
        user_id = "user-at-limit"
        
        # Make 10 requests (hitting the limit)
        for _ in range(10):
            await rate_limiter.is_allowed(user_id)
        
        # 11th request should be blocked
        is_allowed, rate_info = await rate_limiter.is_allowed(user_id)
        
        assert is_allowed is False
        assert rate_info["remaining"] == 0

    @pytest.mark.asyncio
    async def test_over_limit_blocked(self, rate_limiter: RateLimiter):
        """Test that requests over limit are blocked."""
        user_id = "user-over-limit"
        
        # Make 15 requests (5 over limit)
        for i in range(15):
            is_allowed, _ = await rate_limiter.is_allowed(user_id)
            
            if i < 10:
                assert is_allowed is True
            else:
                assert is_allowed is False


# =============================================================================
# Disabled Rate Limiting Tests
# =============================================================================

class TestDisabledRateLimiting:
    """Tests for disabled rate limiting."""

    @pytest.mark.asyncio
    async def test_disabled_always_allows(self, rate_limiter_disabled: RateLimiter):
        """Test that disabled rate limiter always allows."""
        user_id = "unlimited-user"
        
        # Make many requests
        for _ in range(100):
            is_allowed, rate_info = await rate_limiter_disabled.is_allowed(user_id)
            assert is_allowed is True
            assert rate_info["limit"] == -1  # Indicates unlimited


# =============================================================================
# Redis Unavailable Tests
# =============================================================================

class TestRedisUnavailable:
    """Tests for behavior when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_redis_unavailable_allows(
        self,
        test_settings_enabled: Settings,
    ):
        """Test that requests are allowed when Redis is unavailable (fail-open)."""
        # Create cache but don't connect (simulates unavailable Redis)
        cache = MockCacheService()
        cache._connected = False
        
        rate_limiter = RateLimiter(settings=test_settings_enabled, cache=cache)
        
        is_allowed, rate_info = await rate_limiter.is_allowed("user-123")
        
        # Should allow (fail-open behavior)
        assert is_allowed is True


# =============================================================================
# Rate Info Tests
# =============================================================================

class TestRateInfo:
    """Tests for rate limit information."""

    @pytest.mark.asyncio
    async def test_rate_info_contains_required_fields(self, rate_limiter: RateLimiter):
        """Test that rate info contains all required fields."""
        is_allowed, rate_info = await rate_limiter.is_allowed("user-info")
        
        assert "remaining" in rate_info
        assert "reset_at" in rate_info
        assert "limit" in rate_info

    @pytest.mark.asyncio
    async def test_rate_info_remaining_decreases(self, rate_limiter: RateLimiter):
        """Test that remaining count decreases with requests."""
        user_id = "user-remaining"
        
        _, info1 = await rate_limiter.is_allowed(user_id)
        _, info2 = await rate_limiter.is_allowed(user_id)
        
        # Remaining should decrease
        assert info2["remaining"] < info1["remaining"]


# =============================================================================
# Get Rate Info Tests
# =============================================================================

class TestGetRateInfo:
    """Tests for getting rate limit info without making a request."""

    @pytest.mark.asyncio
    async def test_get_rate_info(self, rate_limiter: RateLimiter):
        """Test getting rate info for a user."""
        user_id = "user-get-info"
        
        # Make some requests first
        for _ in range(3):
            await rate_limiter.is_allowed(user_id)
        
        # Get info
        rate_info = await rate_limiter.get_rate_info(user_id)
        
        assert "remaining" in rate_info
        assert "reset_at" in rate_info
        assert "limit" in rate_info
        # Should have 7 remaining (10 - 3)
        assert rate_info["remaining"] == 7


# =============================================================================
# Reset Tests
# =============================================================================

class TestReset:
    """Tests for rate limit reset."""

    @pytest.mark.asyncio
    async def test_reset_clears_limit(self, rate_limiter: RateLimiter, mock_cache: MockCacheService):
        """Test that reset clears the rate limit."""
        user_id = "user-reset"
        
        # Hit the limit
        for _ in range(10):
            await rate_limiter.is_allowed(user_id)
        
        # Should be blocked
        is_allowed, _ = await rate_limiter.is_allowed(user_id)
        assert is_allowed is False
        
        # Reset
        result = await rate_limiter.reset(user_id)
        assert result is True
        
        # Should be allowed again
        is_allowed, _ = await rate_limiter.is_allowed(user_id)
        assert is_allowed is True


# =============================================================================
# Custom Limit Tests
# =============================================================================

class TestCustomLimits:
    """Tests for custom rate limits."""

    @pytest.mark.asyncio
    async def test_custom_requests_per_minute(self, rate_limiter: RateLimiter):
        """Test using custom requests per minute limit."""
        user_id = "user-custom-limit"
        
        # Use custom limit of 5
        for _ in range(5):
            is_allowed, _ = await rate_limiter.is_allowed(
                user_id,
                requests_per_minute=5,
            )
            assert is_allowed is True
        
        # 6th request should be blocked
        is_allowed, _ = await rate_limiter.is_allowed(
            user_id,
            requests_per_minute=5,
        )
        assert is_allowed is False


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_function(self, mock_cache: MockCacheService):
        """Test the check_rate_limit convenience function."""
        # Note: This uses the global rate limiter
        # We test that it doesn't crash and returns expected format
        is_allowed, rate_info = await check_rate_limit("test-user")
        
        assert isinstance(is_allowed, bool)
        assert isinstance(rate_info, dict)
