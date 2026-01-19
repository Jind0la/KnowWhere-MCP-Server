"""
MCP Tool: recall

Search and retrieve memories from Knowwhere.
Now uses graph-enhanced RecallEngine for intelligent retrieval.
"""

import time
from uuid import UUID

import structlog

from src.models.memory import MemoryType
from src.models.requests import DateRange, RecallFilters, RecallInput, RecallOutput
from src.engine.recall_engine import RecallEngine, get_recall_engine

logger = structlog.get_logger(__name__)


async def recall(
    user_id: UUID,
    query: str,
    filters: dict | None = None,
    limit: int = 10,
    offset: int = 0,
    relevance_threshold: float = 0.0,
    include_sampling: bool = False,
) -> RecallOutput:
    """
    Search and retrieve memories using graph-enhanced recall.
    
    This tool uses the RecallEngine which provides:
    - Vector similarity search (primary retrieval)
    - Evolution awareness (filters out superseded memories)
    - Entity expansion (finds related memories via shared entities)
    - Recency boost (recently accessed memories are prioritized)
    
    Args:
        user_id: The user whose memories to search
        query: Search query (natural language)
        filters: Optional filters (memory_type, entity, date_range, importance_min)
        limit: Maximum number of results (1-50)
        
    Returns:
        RecallOutput with matching memories and similarity scores
    """
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
    
    # Use the graph-enhanced RecallEngine
    engine = await get_recall_engine()
    
    result = await engine.recall(
        user_id=user_id,
        query=query,
        filters=parsed_filters,
        limit=limit,
        offset=offset,
        # Graph-enhanced options (all enabled by default)
        respect_evolution=True,
        expand_entities=True,
        include_related=include_sampling,  # Include related if sampling mode
        apply_recency_boost=True,
    )
    
    logger.info(
        "Recall completed",
        results_count=result.count,
        evolution_filtered=result.evolution_filtered_count,
        entity_expanded=result.entity_expanded_count,
        search_time_ms=result.search_time_ms,
    )
    
    return RecallOutput(
        query=query,
        count=result.count,
        total_available=result.total_available,
        memories=result.memories,
        search_time_ms=result.search_time_ms,
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
    "description": "Search and retrieve memories from Knowwhere using graph-enhanced recall. Respects memory evolution (newer versions preferred), expands via shared entities, and learns from usage patterns.",
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
            "relevance_threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.0,
                "description": "Minimum similarity score required (0.0 to 1.0)",
            },
        },
        "required": ["query"],
    },
}
