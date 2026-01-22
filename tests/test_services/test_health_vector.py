import pytest
from unittest.mock import AsyncMock, patch
from src.models.health import HealthStatus
from src.storage.database import Database

@pytest.mark.asyncio
async def test_vector_health_check_success():
    try:
        from src.services.health_checks.vector import VectorSearchHealthCheck
    except ImportError:
        pytest.fail("Could not import VectorSearchHealthCheck from src.services.health_checks.vector")
    
    mock_db = AsyncMock(spec=Database)
    # Mocking a successful vector operation
    mock_db.fetchval.return_value = 0.5 # Dummy distance
    
    checker = VectorSearchHealthCheck(db=mock_db)
    result = await checker.check()
    
    assert result.service == "vector_search"
    assert result.status == HealthStatus.UP
    assert result.latency_ms >= 0
    assert result.message is None

@pytest.mark.asyncio
async def test_vector_health_check_failure():
    try:
        from src.services.health_checks.vector import VectorSearchHealthCheck
    except ImportError:
        pytest.fail("Could not import VectorSearchHealthCheck from src.services.health_checks.vector")
    
    mock_db = AsyncMock(spec=Database)
    # Mocking a failed vector operation
    mock_db.fetchval.side_effect = Exception("pgvector extension not installed")
    
    checker = VectorSearchHealthCheck(db=mock_db)
    result = await checker.check()
    
    assert result.service == "vector_search"
    assert result.status == HealthStatus.DOWN
    assert "pgvector extension not installed" in result.message
