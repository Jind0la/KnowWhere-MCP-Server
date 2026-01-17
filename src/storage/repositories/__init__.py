"""
Repository Pattern - Data Access Objects

Each repository handles CRUD operations for its entity:
- MemoryRepository: Memory CRUD with vector search
- EdgeRepository: Knowledge graph edges
- UserRepository: User management
- ConsolidationRepository: Consolidation history
"""

from src.storage.repositories.memory_repo import MemoryRepository
from src.storage.repositories.edge_repo import EdgeRepository
from src.storage.repositories.user_repo import UserRepository
from src.storage.repositories.consolidation_repo import ConsolidationRepository

__all__ = [
    "MemoryRepository",
    "EdgeRepository",
    "UserRepository",
    "ConsolidationRepository",
]
