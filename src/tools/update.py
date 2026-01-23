"""
MCP Tool: update_memory
Direct status updates and metadata refinement.
"""

from typing import Any
from uuid import UUID

import structlog

from src.models.memory import MemoryStatus, MemoryUpdate, MemoryType
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)

async def update_memory(
    user_id: UUID,
    memory_id: str,
    status: str | None = None,
    importance: int | None = None,
    memory_type: str | None = None,
    content: str | None = None,
    entities: list[str] | None = None,
) -> dict[str, Any]:
    """
    Updates specific fields of an existing memory.
    
    Args:
        user_id: Owner of the memory
        memory_id: UUID of the memory to update
        status: New status (active, stale, irrelevant)
        importance: New importance score (1-10)
        memory_type: New memory type (semantic, preference, etc.)
        content: Updated content text (will trigger re-embedding)
        entities: Updated list of entities
        
    Returns:
        Dict with status and updated_memory_id
    """
    mem_id = memory_id if isinstance(memory_id, UUID) else UUID(str(memory_id))

    db = await get_database()
    repo = MemoryRepository(db)
    
    # Check if memory exists
    old_memory = await repo.get_by_id(mem_id, user_id)
    if not old_memory:
        # Check if it exists but is not active (e.g. stale/irrelevant)
        # Search for all non-deleted
        all_mems = await repo.search_similar([0.0]*1408, user_id, status=None) # Passing status=None searches non-deleted
        match = next((m for m in all_mems if m.id == mem_id), None)
        if not match:
             raise ValueError(f"Memory not found: {memory_id}")
        old_memory = match

    update_data = MemoryUpdate()
    if status:
        update_data.status = MemoryStatus(status)
    if importance is not None:
        update_data.importance = importance
    if memory_type:
        update_data.memory_type = MemoryType(memory_type)
    if content:
        update_data.content = content
        # Note: Repository should handle re-embedding if content changes
    if entities is not None:
        update_data.entities = entities

    updated = await repo.update(mem_id, user_id, update_data)
    
    if not updated:
        raise ValueError(f"Failed to update memory: {memory_id}")

    logger.info(
        "Memory updated",
        memory_id=str(updated.id),
        status=updated.status.value,
        importance=updated.importance
    )

    return {
        "status": "updated",
        "memory_id": str(updated.id),
        "new_status": updated.status.value,
        "message": f"Memory {memory_id} successfully updated to status '{updated.status.value}'."
    }

UPDATE_MEMORY_SPEC = {
    "name": "mcp_update_memory",
    "description": "Updates specific fields of a memory, such as status (active, stale, irrelevant) or importance. Use this for memory hygiene and aging without changing the actual content.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "The UUID of the memory to update",
            },
            "status": {
                "type": "string",
                "enum": ["active", "stale", "irrelevant"],
                "description": "New status for the memory",
            },
            "importance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Updated importance score",
            },
            "memory_type": {
                "type": "string",
                "enum": ["semantic", "preference", "procedural", "episodic", "meta"],
                "description": "Update the classification of the memory",
            },
            "content": {
                "type": "string",
                "description": "Update the text content of the memory. NOTE: For significant changes that represent 'learning', prefer using refine_knowledge to preserve history. Use this for corrections.",
            },
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Update the list of extracted entities",
            }
        },
        "required": ["memory_id"],
    },
}
