"""
MCP Tool: remember

Store a new memory in Knowwhere with duplicate detection.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.config import get_settings
from src.engine.memory_processor import MemoryProcessor
from src.models.memory import MemorySource, MemoryType
from src.models.requests import RememberInput, RememberOutput
from src.services.embedding import get_embedding_service
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)




async def remember(
    user_id: UUID,
    content: str,
    memory_type: str | None = None,
    entities: list[str] | None = None,
    importance: int | None = None,
    metadata: dict[str, Any] | None = None,
    skip_duplicate_check: bool = False,
) -> RememberOutput:
    """
    Store a new memory in Knowwhere with duplicate detection.
    
    This is the core tool for adding new memories. It:
    1. Generates an embedding for the content
    2. Checks for duplicate memories (>85% similarity)
    3. Extracts entities if not provided
    4. Stores the memory in the database (if not duplicate)
    
    Args:
        user_id: The user who owns this memory
        content: The memory content (what to remember)
        memory_type: Optional type (auto-classified if None)
        entities: Optional list of related entities (auto-extracted if not provided)
        importance: Optional importance level (auto-calculated if None)
        metadata: Optional additional metadata
        skip_duplicate_check: Skip duplicate detection (for imports/migrations)
        
    Returns:
        RememberOutput with memory_id, status, and extracted entities
    """
    logger.info(
        "Remember tool called",
        user_id=str(user_id),
        memory_type=memory_type,
        content_length=len(content),
    )
    
    # Validate and convert memory type if provided
    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType(memory_type.lower())
        except ValueError:
            raise ValueError(
                f"Invalid memory_type: {memory_type}. "
                f"Must be one of: episodic, semantic, preference, procedural, meta"
            )
    
    # Validate importance if provided
    if importance is not None:
        importance = max(1, min(10, importance))
    
    # Use MemoryProcessor for all logic (Deduplication, Conflict, Entity/Graph)
    processor = MemoryProcessor()
    
    memory, proc_status = await processor.process_memory(
        user_id=user_id,
        content=content,
        memory_type=mem_type,
        entities=entities,
        importance=importance,
        source=MemorySource.MANUAL,
        metadata=metadata or {},
        embedding=None,
    )
    
    # proc_status is one of: "created", "updated", "refined"
    status = "created"
    if proc_status == "updated":
        status = "duplicate_found"
    elif proc_status == "refined":
        status = "refined"

    return RememberOutput(
        memory_id=memory.id,
        status=status,
        embedding_status="generated",
        entities_extracted=memory.entities,
        created_at=memory.created_at,
    )


# Tool specification for MCP
REMEMBER_SPEC = {
    "name": "remember",
    "description": (
        "Store a new memory in Knowwhere. Use this to remember facts, preferences, learnings, or procedures. "
        "KnowWhere uses a hierarchical taxonomy with three primary domains:\n"
        "- 'KnowWhere': For everything project-related (Source Code, API, Architecture, etc.)\n"
        "- 'Personal': For user info, bio, preferences, habits, and workflows.\n"
        "- 'General': For abstract facts not tied to the project or user.\n"
        "Attributes like type and importance are automatically determined if not provided."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The memory content (what to remember)",
                "minLength": 1,
                "maxLength": 8000,
            },
            "memory_type": {
                "type": "string",
                "enum": ["episodic", "semantic", "preference", "procedural", "meta"],
                "description": "Optional: Type of memory. If omitted, the system will auto-classify it.",
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: Related entities/concepts (auto-extracted if not provided)",
            },
            "importance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Optional: Importance level (1-10). If omitted, the system will auto-calculate it.",
            },
            "metadata": {
                "type": "object",
                "description": "Additional custom metadata",
            },
        },
        "required": ["content"],
    },
}
