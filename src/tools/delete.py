"""
MCP Tool: delete_memory

Delete a specific memory (GDPR-compliant).
"""

from datetime import datetime
from uuid import UUID

import structlog

from src.engine.knowledge_graph import get_knowledge_graph
from src.models.requests import DeleteInput, DeleteOutput
from src.storage.cache import get_cache
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


async def delete_memory(
    user_id: UUID,
    memory_id: UUID,
    hard_delete: bool = False,
) -> DeleteOutput:
    """
    Delete a specific memory (GDPR-compliant).
    
    By default, performs a soft delete (marks as deleted but retains data
    for a grace period). Use hard_delete=True for immediate permanent deletion.
    
    Also removes any knowledge graph edges connected to this memory.
    
    Args:
        user_id: The user who owns the memory
        memory_id: ID of the memory to delete
        hard_delete: Whether to permanently delete (vs soft-delete)
        
    Returns:
        DeleteOutput with deletion confirmation
    """
    logger.info(
        "Delete memory tool called",
        user_id=str(user_id),
        memory_id=str(memory_id),
        hard_delete=hard_delete,
    )
    
    # Get database connection
    db = await get_database()
    repo = MemoryRepository(db)
    
    # Verify memory exists and belongs to user
    memory = await repo.get_by_id(memory_id, user_id)
    if not memory:
        raise ValueError(f"Memory {memory_id} not found or does not belong to user")
    
    # Delete associated knowledge graph edges
    kg = await get_knowledge_graph()
    edges_removed = await kg.delete_edges_for_memory(user_id, memory_id)
    
    # Perform deletion
    if hard_delete:
        success = await repo.hard_delete(memory_id, user_id)
        deletion_type = "hard"
    else:
        success = await repo.soft_delete(memory_id, user_id)
        deletion_type = "soft"
    
    if not success:
        raise ValueError(f"Failed to delete memory {memory_id}")
    
    # Invalidate cache
    cache = await get_cache()
    await cache.invalidate_memory(str(memory_id))
    await cache.invalidate_user_cache(str(user_id))
    
    logger.info(
        "Memory deleted",
        memory_id=str(memory_id),
        deletion_type=deletion_type,
        edges_removed=edges_removed,
    )
    
    return DeleteOutput(
        memory_id=memory_id,
        deleted=True,
        deleted_at=datetime.utcnow(),
        deletion_type=deletion_type,
        related_edges_removed=edges_removed,
    )


# Tool specification for MCP
DELETE_MEMORY_SPEC = {
    "name": "delete_memory",
    "description": "Delete a specific memory. Performs soft-delete by default (GDPR-compliant with grace period). Use hard_delete for immediate permanent deletion.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the memory to delete",
            },
            "hard_delete": {
                "type": "boolean",
                "default": False,
                "description": "Whether to permanently delete (vs soft-delete)",
            },
        },
        "required": ["memory_id"],
    },
}
