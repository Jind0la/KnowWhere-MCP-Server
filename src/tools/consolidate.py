"""
MCP Tool: consolidate_session

Process a conversation transcript and extract memories.
"""

from datetime import datetime
from uuid import UUID

import structlog

from src.engine.consolidation import get_consolidation_engine
from src.models.requests import ConsolidateInput, ConsolidateOutput, NewMemorySummary
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


async def consolidate_session(
    user_id: UUID,
    session_transcript: str,
    session_date: datetime | None = None,
    conversation_id: str | None = None,
) -> ConsolidateOutput:
    """
    Process a conversation transcript and extract structured memories.
    
    This tool analyzes a conversation to:
    1. Extract factual claims, preferences, and learnings
    2. Detect and merge duplicate information
    3. Resolve conflicting statements
    4. Build knowledge graph relationships
    5. Store all extracted memories
    
    Args:
        user_id: The user who owns these memories
        session_transcript: Full conversation transcript to process
        session_date: When the session occurred (optional)
        conversation_id: Reference ID for the conversation (optional)
        
    Returns:
        ConsolidateOutput with processing details and created memories
    """
    logger.info(
        "Consolidate session tool called",
        user_id=str(user_id),
        transcript_length=len(session_transcript),
        conversation_id=conversation_id,
    )
    
    # Validate transcript length
    if len(session_transcript) < 10:
        raise ValueError("Session transcript is too short (minimum 10 characters)")
    
    if len(session_transcript) > 100000:
        raise ValueError("Session transcript is too long (maximum 100,000 characters)")
    
    # Run consolidation
    engine = await get_consolidation_engine()
    result = await engine.consolidate(
        user_id=user_id,
        session_transcript=session_transcript,
        conversation_id=conversation_id,
    )
    
    # Fetch created memories for summary
    db = await get_database()
    repo = MemoryRepository(db)
    
    new_memories_summary: list[NewMemorySummary] = []
    for memory_id in result.new_memory_ids:
        memory = await repo.get_by_id(memory_id, user_id)
        if memory:
            new_memories_summary.append(NewMemorySummary(
                id=memory.id,
                content=memory.content[:200] + "..." if len(memory.content) > 200 else memory.content,
                memory_type=memory.memory_type,
                importance=memory.importance,
                entities=memory.entities[:5],  # Limit entities in summary
            ))
    
    logger.info(
        "Consolidation completed",
        consolidation_id=str(result.consolidation_id),
        memories_created=result.new_memories_count,
        edges_created=result.edges_created,
        processing_time_ms=result.processing_time_ms,
    )
    
    return ConsolidateOutput(
        consolidation_id=result.consolidation_id,
        new_memories_count=result.new_memories_count,
        new_memories=new_memories_summary,
        merged_count=result.merged_count,
        conflicts_resolved=result.conflicts_resolved,
        edges_created=result.edges_created,
        patterns_detected=result.patterns_detected,
        processing_time_ms=result.processing_time_ms,
        status=result.status.value,
        error_message=result.error_message,
    )


# Tool specification for MCP
CONSOLIDATE_SESSION_SPEC = {
    "name": "consolidate_session",
    "description": "Process a conversation transcript and extract structured memories. This analyzes the conversation to find facts, preferences, and learnings, then stores them as memories.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_transcript": {
                "type": "string",
                "description": "Full conversation transcript to process",
                "minLength": 10,
                "maxLength": 100000,
            },
            "session_date": {
                "type": "string",
                "format": "date-time",
                "description": "When the session occurred (ISO 8601 format)",
            },
            "conversation_id": {
                "type": "string",
                "description": "Reference ID for the conversation",
            },
        },
        "required": ["session_transcript"],
    },
}
