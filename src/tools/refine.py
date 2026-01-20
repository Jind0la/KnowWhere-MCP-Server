"""
MCP Tool: refine
Correction and evolution of existing knowledge.
"""

from typing import Any
from uuid import UUID

import structlog

from src.models.edge import EdgeCreate, EdgeType
from src.models.memory import MemoryStatus, MemoryUpdate
from src.services.entity_hub_service import get_entity_hub_service
from src.engine.memory_processor import MemoryProcessor
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository
from src.storage.repositories.edge_repo import EdgeRepository

logger = structlog.get_logger(__name__)

async def refine_knowledge(
    user_id: UUID,
    memory_id: str,
    new_content: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Refines existing knowledge by creating a new version and superseding the old one.
    
    Args:
        user_id: Owner of the memory
        memory_id: UUID of the memory to refine
        new_content: The corrected/updated content
        reason: Optional reason for the refinement
        
    Returns:
        Dict with status and new_memory_id
    """
    # Support both string and UUID object robustly
    mem_id = memory_id if isinstance(memory_id, UUID) else UUID(str(memory_id))

    db = await get_database()
    memory_repo = MemoryRepository(db)
    edge_repo = EdgeRepository(db)
    
    # 1. Fetch old memory
    old_memory = await memory_repo.get_by_id(mem_id, user_id)
    if not old_memory:
        raise ValueError(f"Memory not found or not active: {memory_id}")
    
    logger.info(
        "Refining memory",
        old_id=str(old_memory.id),
        user_id=str(user_id),
        new_content_len=len(new_content)
    )

    # 2. Create new memory
    # Reuse classification and type from old memory unless overridden
    processor = MemoryProcessor()
    
    # We want to re-extract entities for the new content
    entity_hub_service = await get_entity_hub_service()
    extraction_result = await entity_hub_service.extract_and_learn(user_id, new_content)
    new_entities = [e.name for e in extraction_result.entities]

    new_memory = await processor.process_memory(
        user_id=user_id,
        content=new_content,
        memory_type=old_memory.memory_type,
        entities=new_entities,
        importance=old_memory.importance,
        source=old_memory.source,
        source_id=old_memory.source_id,
        metadata={
            **(old_memory.metadata or {}),
            "refined_from": str(old_memory.id),
            "refinement_reason": reason
        }
    )
    
    # Link new memory to its entities
    await entity_hub_service.link_memory_to_entities(
        memory=new_memory,
        entities=extraction_result.entities,
    )

    # 3. Update old memory status to SUPERSEDED
    update_data = MemoryUpdate(
        status=MemoryStatus.SUPERSEDED,
        superseded_by=new_memory.id
    )
    await memory_repo.update(old_memory.id, user_id, update_data)

    # 4. Create EVOLVES_INTO edge
    edge_create = EdgeCreate(
        user_id=user_id,
        from_node_id=old_memory.id,
        to_node_id=new_memory.id,
        edge_type=EdgeType.EVOLVES_INTO,
        strength=1.0,
        confidence=1.0,
        reason=reason or "Knowledge refinement/correction",
        metadata={"auto_generated": True, "type": "refinement"}
    )
    await edge_repo.create(edge_create)

    logger.info(
        "Refinement complete",
        old_id=str(old_memory.id),
        new_id=str(new_memory.id)
    )

    return {
        "status": "refined",
        "old_memory_id": str(old_memory.id),
        "new_memory_id": str(new_memory.id),
        "message": f"Knowledge successfully refined. Old version archived as superseded."
    }

REFINE_SPEC = {
    "name": "mcp_refine_knowledge",
    "description": "Refines or corrects an existing memory. Use this instead of deleting when a misunderstanding occurred or information has evolved. The old memory will be kept as 'superseded' history.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "The UUID of the memory to refine (find this via mcp_recall first)",
            },
            "new_content": {
                "type": "string",
                "description": "The updated or corrected memory content",
                "minLength": 1,
                "maxLength": 8000,
            },
            "reason": {
                "type": "string",
                "description": "Optional reason for the refinement (e.g., 'User corrected my misunderstanding')",
            }
        },
        "required": ["memory_id", "new_content"],
    },
}
