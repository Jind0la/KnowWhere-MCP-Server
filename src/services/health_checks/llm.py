import time
from src.services.health import BaseHealthCheck
from src.models.health import HealthCheckResult, HealthStatus
from src.services.llm import LLMService

class LLMHealthCheck(BaseHealthCheck):
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            # Send a minimal prompt to verify API connectivity and auth
            await self.llm_service.complete(
                prompt="ping",
                max_tokens=1,
                temperature=0.0
            )
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service="llm_provider",
                status=HealthStatus.UP,
                latency_ms=latency
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service="llm_provider",
                status=HealthStatus.DOWN,
                latency_ms=latency,
                message=str(e)
            )
