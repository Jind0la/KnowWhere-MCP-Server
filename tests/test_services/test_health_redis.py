import pytest
from unittest.mock import AsyncMock, patch
from src.models.health import HealthStatus
from src.storage.cache import CacheService

@pytest.mark.asyncio
async def test_redis_health_check_success():
    try:
        from src.services.health_checks.redis import RedisHealthCheck
    except ImportError:
        pytest.fail("Could not import RedisHealthCheck from src.services.health_checks.redis")
    
    mock_cache = AsyncMock(spec=CacheService)
    mock_cache.health_check.return_value = True
    
    checker = RedisHealthCheck(cache=mock_cache)
    result = await checker.check()
    
    assert result.service == "redis"
    assert result.status == HealthStatus.UP
    assert result.latency_ms >= 0
    assert result.message is None

@pytest.mark.asyncio
async def test_redis_health_check_failure():
    try:
        from src.services.health_checks.redis import RedisHealthCheck
    except ImportError:
        pytest.fail("Could not import RedisHealthCheck from src.services.health_checks.redis")
    
    mock_cache = AsyncMock(spec=CacheService)
    mock_cache.health_check.return_value = False
    
    checker = RedisHealthCheck(cache=mock_cache)
    result = await checker.check()
    
    assert result.service == "redis"
    assert result.status == HealthStatus.DOWN
    assert result.message is not None
