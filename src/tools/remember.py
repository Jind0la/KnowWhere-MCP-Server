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
    memory_type: str,
    entities: list[str] | None = None,
    importance: int = 5,
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
        memory_type: Type of memory (episodic, semantic, preference, procedural, meta)
        entities: Optional list of related entities (auto-extracted if not provided)
        importance: Importance level 1-10 (default: 5)
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
    
    # Validate and convert memory type
    try:
        mem_type = MemoryType(memory_type.lower())
    except ValueError:
        raise ValueError(
            f"Invalid memory_type: {memory_type}. "
            f"Must be one of: episodic, semantic, preference, procedural, meta"
        )
    
    # Validate importance
    importance = max(1, min(10, importance))
    
    # Use MemoryProcessor for all logic (Deduplication, Conflict, Entity/Graph)
    # v1.3.0 "Magic" consolidated here
    processor = MemoryProcessor()
    
    # Check if similarity is already computed via skip_duplicate_check (optional optimization)
    # But for simplicity and consistency, we let the processor handle it
    memory, proc_status = await processor.process_memory(
        user_id=user_id,
        content=content,
        memory_type=mem_type,
        entities=entities, # Pass user-provided entities
        importance=importance,
        source=MemorySource.MANUAL, # MCP tool calls are manual instructions
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
    "description": "Store a new memory in Knowwhere. Use this to remember facts, preferences, learnings, or procedures about the user.",
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
                "description": "Type of memory: episodic (specific events), semantic (facts), preference (user preferences), procedural (how-to), meta (about user's knowledge)",
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Related entities/concepts (auto-extracted if not provided)",
            },
            "importance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
                "description": "Importance level (1=least, 10=most)",
            },
            "metadata": {
                "type": "object",
                "description": "Additional custom metadata",
            },
        },
        "required": ["content", "memory_type"],
    },
}
