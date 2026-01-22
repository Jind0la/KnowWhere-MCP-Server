import pytest
from unittest.mock import AsyncMock, patch
from src.models.health import HealthStatus
from src.storage.database import Database

@pytest.mark.asyncio
async def test_postgres_health_check_success():
    try:
        from src.services.health_checks.database import PostgresHealthCheck
    except ImportError:
        pytest.fail("Could not import PostgresHealthCheck from src.services.health_checks.database")
    
    mock_db = AsyncMock(spec=Database)
    mock_db.health_check.return_value = True
    
    checker = PostgresHealthCheck(db=mock_db)
    result = await checker.check()
    
    assert result.service == "postgresql"
    assert result.status == HealthStatus.UP
    assert result.latency_ms >= 0
    assert result.message is None

@pytest.mark.asyncio
async def test_postgres_health_check_failure():
    try:
        from src.services.health_checks.database import PostgresHealthCheck
    except ImportError:
        pytest.fail("Could not import PostgresHealthCheck from src.services.health_checks.database")
    
    mock_db = AsyncMock(spec=Database)
    mock_db.health_check.return_value = False
    
    checker = PostgresHealthCheck(db=mock_db)
    result = await checker.check()
    
    assert result.service == "postgresql"
    assert result.status == HealthStatus.DOWN
    assert result.message is not None
