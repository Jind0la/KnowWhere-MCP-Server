import time
from src.services.health import BaseHealthCheck
from src.models.health import HealthCheckResult, HealthStatus
from src.storage.database import Database

class PostgresHealthCheck(BaseHealthCheck):
    def __init__(self, db: Database):
        self.db = db

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            is_healthy = await self.db.health_check()
            latency = (time.time() - start_time) * 1000
            
            if is_healthy:
                return HealthCheckResult(
                    service="postgresql",
                    status=HealthStatus.UP,
                    latency_ms=latency
                )
            else:
                return HealthCheckResult(
                    service="postgresql",
                    status=HealthStatus.DOWN,
                    latency_ms=latency,
                    message="Database health check failed"
                )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service="postgresql",
                status=HealthStatus.DOWN,
                latency_ms=latency,
                message=str(e)
            )
