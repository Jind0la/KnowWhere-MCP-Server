"""
MCP Tool: remember

Store a new memory in Knowwhere with duplicate detection.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.config import get_settings
from src.engine.entity_extractor import get_entity_extractor
from src.engine.memory_processor import MemoryProcessor
from src.models.memory import MemorySource, MemoryType
from src.models.requests import RememberInput, RememberOutput
from src.services.embedding import get_embedding_service
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)

# Duplicate detection threshold (same as consolidation)
DUPLICATE_THRESHOLD = 0.85


async def check_for_duplicate(
    user_id: UUID,
    content: str,
    embedding: list[float],
) -> tuple[bool, dict | None]:
    """
    Check if a similar memory already exists.
    
    Returns:
        (is_duplicate, existing_memory_info) - existing_memory_info contains id and similarity
    """
    db = await get_database()
    repo = MemoryRepository(db)
    
    # Search for similar memories
    similar_memories = await repo.search_similar(
        embedding=embedding,
        user_id=user_id,
        limit=3,
    )
    
    if not similar_memories:
        return False, None
    
    # Check if any memory exceeds the duplicate threshold
    for memory in similar_memories:
        if hasattr(memory, 'similarity') and memory.similarity >= DUPLICATE_THRESHOLD:
            logger.info(
                "Duplicate memory detected",
                existing_id=str(memory.id),
                similarity=memory.similarity,
            )
            return True, {
                "id": memory.id,
                "content": memory.content,
                "similarity": memory.similarity,
            }
        
        # Also check for exact or near-exact content match
        if memory.content.strip().lower() == content.strip().lower():
            logger.info(
                "Exact duplicate content detected",
                existing_id=str(memory.id),
            )
            return True, {
                "id": memory.id,
                "content": memory.content,
                "similarity": 1.0,
            }
    
    return False, None


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
    
    # Generate embedding early for duplicate check
    embedding_service = await get_embedding_service()
    embedding = await embedding_service.embed(content)
    
    # Check for duplicates (unless skipped)
    if not skip_duplicate_check:
        is_duplicate, existing = await check_for_duplicate(user_id, content, embedding)
        
        if is_duplicate and existing:
            logger.info(
                "Returning existing memory instead of creating duplicate",
                existing_id=str(existing["id"]),
                similarity=existing.get("similarity", 1.0),
            )
            
            # Return the existing memory info
            return RememberOutput(
                memory_id=existing["id"],
                status="duplicate_found",
                embedding_status="existing",
                entities_extracted=entities or [],
                created_at=datetime.now(),  # Not accurate but indicates "now"
                message=f"Similar memory already exists (similarity: {existing.get('similarity', 1.0):.0%})",
            )
    
    # Extract entities if not provided
    extracted_entities = entities or []
    if not extracted_entities:
        entity_extractor = await get_entity_extractor()
        extracted_entities = await entity_extractor.extract(content)
    
    # Process and store memory (pass pre-computed embedding)
    processor = MemoryProcessor()
    memory = await processor.process_memory(
        user_id=user_id,
        content=content,
        memory_type=mem_type,
        entities=extracted_entities,
        importance=importance,
        source=MemorySource.MANUAL,
        metadata=metadata or {},
        embedding=embedding,  # Pass pre-computed embedding
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
