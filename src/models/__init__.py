"""
Pydantic Models

Core data structures:
- Memory: The core memory entity
- KnowledgeEdge: Graph relationships
- User: User entity
- ConsolidationResult: Session processing result
- Request/Response schemas for tools
"""

from src.models.memory import (
    Memory,
    MemoryType,
    MemoryStatus,
    MemoryCreate,
    MemoryWithSimilarity,
)
from src.models.edge import (
    KnowledgeEdge,
    EdgeType,
    EdgeCreate,
)
from src.models.user import User, UserTier
from src.models.consolidation import (
    ConsolidationResult,
    Claim,
    ConflictResolution,
    ConsolidationHistory,
)
from src.models.requests import (
    RememberInput,
    RememberOutput,
    RecallInput,
    RecallOutput,
    ConsolidateInput,
    ConsolidateOutput,
    AnalyzeInput,
    AnalyzeOutput,
    ExportInput,
    ExportOutput,
    DeleteInput,
    DeleteOutput,
)

__all__ = [
    # Memory
    "Memory",
    "MemoryType",
    "MemoryStatus",
    "MemoryCreate",
    "MemoryWithSimilarity",
    # Edge
    "KnowledgeEdge",
    "EdgeType",
    "EdgeCreate",
    # User
    "User",
    "UserTier",
    # Consolidation
    "ConsolidationResult",
    "Claim",
    "ConflictResolution",
    "ConsolidationHistory",
    # Requests
    "RememberInput",
    "RememberOutput",
    "RecallInput",
    "RecallOutput",
    "ConsolidateInput",
    "ConsolidateOutput",
    "AnalyzeInput",
    "AnalyzeOutput",
    "ExportInput",
    "ExportOutput",
    "DeleteInput",
    "DeleteOutput",
]
