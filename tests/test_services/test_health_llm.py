import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.models.health import HealthStatus
from src.services.llm import LLMService

@pytest.mark.asyncio
async def test_llm_health_check_success():
    try:
        from src.services.health_checks.llm import LLMHealthCheck
    except ImportError:
        pytest.fail("Could not import LLMHealthCheck from src.services.health_checks.llm")
    
    mock_llm_service = AsyncMock(spec=LLMService)
    # We assume the health check will probably call 'complete' with a simple prompt
    mock_llm_service.complete.return_value = "pong"
    
    checker = LLMHealthCheck(llm_service=mock_llm_service)
    result = await checker.check()
    
    assert result.service == "llm_provider"
    assert result.status == HealthStatus.UP
    assert result.latency_ms >= 0
    assert result.message is None

@pytest.mark.asyncio
async def test_llm_health_check_failure():
    try:
        from src.services.health_checks.llm import LLMHealthCheck
    except ImportError:
        pytest.fail("Could not import LLMHealthCheck from src.services.health_checks.llm")
    
    mock_llm_service = AsyncMock(spec=LLMService)
    mock_llm_service.complete.side_effect = Exception("API Key Invalid")
    
    checker = LLMHealthCheck(llm_service=mock_llm_service)
    result = await checker.check()
    
    assert result.service == "llm_provider"
    assert result.status == HealthStatus.DOWN
    assert "API Key Invalid" in result.message
