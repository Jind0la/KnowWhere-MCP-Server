import time
from src.services.health import BaseHealthCheck
from src.models.health import HealthCheckResult, HealthStatus
from src.storage.cache import CacheService

class RedisHealthCheck(BaseHealthCheck):
    def __init__(self, cache: CacheService):
        self.cache = cache

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            is_healthy = await self.cache.health_check()
            latency = (time.time() - start_time) * 1000
            
            if is_healthy:
                return HealthCheckResult(
                    service="redis",
                    status=HealthStatus.UP,
                    latency_ms=latency
                )
            else:
                return HealthCheckResult(
                    service="redis",
                    status=HealthStatus.DOWN,
                    latency_ms=latency,
                    message="Redis health check failed"
                )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service="redis",
                status=HealthStatus.DOWN,
                latency_ms=latency,
                message=str(e)
            )
