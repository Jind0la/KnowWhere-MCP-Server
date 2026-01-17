"""
MCP Tool: remember

Store a new memory in Knowwhere.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.engine.entity_extractor import get_entity_extractor
from src.engine.memory_processor import MemoryProcessor
from src.models.memory import MemorySource, MemoryType
from src.models.requests import RememberInput, RememberOutput

logger = structlog.get_logger(__name__)


async def remember(
    user_id: UUID,
    content: str,
    memory_type: str,
    entities: list[str] | None = None,
    importance: int = 5,
    metadata: dict[str, Any] | None = None,
) -> RememberOutput:
    """
    Store a new memory in Knowwhere.
    
    This is the core tool for adding new memories. It:
    1. Generates an embedding for the content
    2. Extracts entities if not provided
    3. Stores the memory in the database
    4. Invalidates relevant caches
    
    Args:
        user_id: The user who owns this memory
        content: The memory content (what to remember)
        memory_type: Type of memory (episodic, semantic, preference, procedural, meta)
        entities: Optional list of related entities (auto-extracted if not provided)
        importance: Importance level 1-10 (default: 5)
        metadata: Optional additional metadata
        
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
    
    # Extract entities if not provided
    extracted_entities = entities or []
    if not extracted_entities:
        entity_extractor = await get_entity_extractor()
        extracted_entities = await entity_extractor.extract(content)
    
    # Process and store memory
    processor = MemoryProcessor()
    memory = await processor.process_memory(
        user_id=user_id,
        content=content,
        memory_type=mem_type,
        entities=extracted_entities,
        importance=importance,
        source=MemorySource.MANUAL,
        metadata=metadata or {},
    )
    
    logger.info(
        "Memory stored successfully",
        memory_id=str(memory.id),
        entities_count=len(extracted_entities),
    )
    
    return RememberOutput(
        memory_id=memory.id,
        status="created",
        embedding_status="generated",
        entities_extracted=extracted_entities,
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
