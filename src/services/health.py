from abc import ABC, abstractmethod
from src.models.health import HealthCheckResult

class BaseHealthCheck(ABC):
    """Abstract base class for all health check services."""
    
    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """
        Perform the health check.
        
        Returns:
            HealthCheckResult: The result of the health check containing status and latency.
        """
        pass
