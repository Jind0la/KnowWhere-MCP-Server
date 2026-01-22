import time
from src.services.health import BaseHealthCheck
from src.models.health import HealthCheckResult, HealthStatus
from src.storage.database import Database

class VectorSearchHealthCheck(BaseHealthCheck):
    def __init__(self, db: Database):
        self.db = db

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            # We want to verify that pgvector is installed and working.
            # We can try to cast a string to a vector and perform a distance calculation.
            # SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector
            # If pgvector is not installed, the cast to ::vector will fail.
            
            query = "SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector"
            await self.db.fetchval(query)
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service="vector_search",
                status=HealthStatus.UP,
                latency_ms=latency
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service="vector_search",
                status=HealthStatus.DOWN,
                latency_ms=latency,
                message=str(e)
            )
