"""
MCP Tool Implementations

The 6 core tools exposed via MCP:
- remember: Store a new memory
- recall: Search and retrieve memories
- consolidate_session: Process conversation transcript
- analyze_evolution: Track preference/knowledge evolution
- export_memories: Export user memories
- delete_memory: GDPR-compliant deletion
"""

from src.tools.remember import remember
from src.tools.recall import recall
from src.tools.consolidate import consolidate_session
from src.tools.analyze import analyze_evolution
from src.tools.export import export_memories
from src.tools.delete import delete_memory

__all__ = [
    "remember",
    "recall",
    "consolidate_session",
    "analyze_evolution",
    "export_memories",
    "delete_memory",
]
