"""
MCP Tool: recall

Search and retrieve memories from Knowwhere.
"""

import time
from uuid import UUID

import structlog

from src.models.memory import MemoryType
from src.models.requests import DateRange, RecallFilters, RecallInput, RecallOutput
from src.services.embedding import get_embedding_service
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


async def recall(
    user_id: UUID,
    query: str,
    filters: dict | None = None,
    limit: int = 10,
    offset: int = 0,
    include_sampling: bool = False,
) -> RecallOutput:
    """
    Search and retrieve memories using semantic similarity.
    
    This tool performs vector similarity search to find memories
    that are semantically related to the query.
    
    Args:
        user_id: The user whose memories to search
        query: Search query (natural language)
        filters: Optional filters (memory_type, entity, date_range, importance_min)
        limit: Maximum number of results (1-50)
        
    Returns:
        RecallOutput with matching memories and similarity scores
    """
    start_time = time.time()
    
    logger.info(
        "Recall tool called",
        user_id=str(user_id),
        query=query[:100],
        limit=limit,
        offset=offset,
        include_sampling=include_sampling,
    )

    # Validate limit and offset
    limit = max(1, min(50, limit))
    offset = max(0, offset)
    
    # Parse filters
    parsed_filters = _parse_filters(filters) if filters else None
    
    # Generate query embedding
    embedding_service = await get_embedding_service()
    query_embedding = await embedding_service.embed(query)
    
    # Search memories
    db = await get_database()
    repo = MemoryRepository(db)
    
    # Get memories with potential sampling
    base_limit = limit
    if include_sampling and limit > 10:
        # For sampling, get more results initially to allow better selection
        base_limit = min(limit * 2, 100)

    memories = await repo.search_similar(
        embedding=query_embedding,
        user_id=user_id,
        limit=base_limit,
        memory_type=parsed_filters.memory_type if parsed_filters else None,
        min_importance=parsed_filters.importance_min if parsed_filters else None,
        entity=parsed_filters.entity if parsed_filters else None,
        date_range=parsed_filters.date_range.value if parsed_filters and parsed_filters.date_range else None,
    )

    # Apply offset and limit for pagination/sampling
    if offset > 0:
        memories = memories[offset:]

    memories = memories[:limit]
    
    # Update access timestamps for returned memories
    for memory in memories:
        await repo._update_access(memory.id)
    
    # Calculate search time
    search_time_ms = int((time.time() - start_time) * 1000)
    
    # Get total count (without limit)
    total_available = await repo.count_by_user(user_id)
    
    logger.info(
        "Recall completed",
        results_count=len(memories),
        search_time_ms=search_time_ms,
    )
    
    return RecallOutput(
        query=query,
        count=len(memories),
        total_available=total_available,
        memories=memories,
        search_time_ms=search_time_ms,
    )


def _parse_filters(filters: dict) -> RecallFilters:
    """Parse raw filter dict into RecallFilters model."""
    memory_type = None
    if "memory_type" in filters and filters["memory_type"]:
        try:
            memory_type = MemoryType(filters["memory_type"].lower())
        except ValueError:
            pass
    
    date_range = None
    if "date_range" in filters and filters["date_range"]:
        try:
            date_range = DateRange(filters["date_range"])
        except ValueError:
            pass
    
    return RecallFilters(
        memory_type=memory_type,
        entity=filters.get("entity"),
        date_range=date_range,
        importance_min=filters.get("importance_min"),
    )


# Tool specification for MCP
RECALL_SPEC = {
    "name": "recall",
    "description": "Search and retrieve memories from Knowwhere using semantic similarity. Use this to find relevant context about the user.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (natural language)",
                "minLength": 1,
                "maxLength": 1000,
            },
            "filters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["episodic", "semantic", "preference", "procedural", "meta"],
                        "description": "Filter by memory type",
                    },
                    "entity": {
                        "type": "string",
                        "description": "Filter by entity name",
                    },
                    "date_range": {
                        "type": "string",
                        "enum": ["last_7_days", "last_30_days", "last_year", "all_time"],
                        "description": "Filter by time range",
                    },
                    "importance_min": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Minimum importance filter",
                    },
                },
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
                "description": "Maximum number of results",
            },
        },
        "required": ["query"],
    },
}
