from enum import Enum
from typing import Optional
from pydantic import BaseModel

class HealthStatus(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    DEGRADED = "DEGRADED"

class HealthCheckResult(BaseModel):
    service: str
    status: HealthStatus
    latency_ms: float
    message: Optional[str] = None
