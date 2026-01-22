import pytest
import asyncio

def test_health_models_exist():
    try:
        from src.models.health import HealthStatus, HealthCheckResult
    except ImportError:
        pytest.fail("Could not import HealthStatus or HealthCheckResult from src.models.health")
    
    assert HealthStatus.UP.value == "UP"
    assert HealthStatus.DOWN.value == "DOWN"
    assert HealthStatus.DEGRADED.value == "DEGRADED"
    
    result = HealthCheckResult(
        service="test_service",
        status=HealthStatus.UP,
        latency_ms=10.5
    )
    assert result.service == "test_service"
    assert result.status == HealthStatus.UP
    assert result.latency_ms == 10.5
    assert result.message is None

@pytest.mark.asyncio
async def test_base_health_check_interface():
    try:
        from src.services.health import BaseHealthCheck
        from src.models.health import HealthCheckResult, HealthStatus
    except ImportError:
        pytest.fail("Could not import BaseHealthCheck from src.services.health")

    class MockHealthCheck(BaseHealthCheck):
        async def check(self) -> HealthCheckResult:
            return HealthCheckResult(
                service="mock",
                status=HealthStatus.UP,
                latency_ms=0.0
            )
            
    assert issubclass(MockHealthCheck, BaseHealthCheck)
    
    checker = MockHealthCheck()
    # Check if check method is async
    assert asyncio.iscoroutinefunction(checker.check)
    
    result = await checker.check()
    assert isinstance(result, HealthCheckResult)
