"""
MCP Tool: analyze_evolution

Track how preferences and knowledge evolved over time.
"""

from datetime import datetime
from uuid import UUID

import structlog

from src.engine.knowledge_graph import get_knowledge_graph
from src.models.requests import (
    AnalyzeInput,
    AnalyzeOutput,
    EvolutionEvent,
    TimeWindow,
)
from src.services.llm import get_llm_service
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


async def analyze_evolution(
    user_id: UUID,
    entity_id: UUID | None = None,
    entity_name: str | None = None,
    time_window: str = "all_time",
) -> AnalyzeOutput:
    """
    Track how an entity, preference, or concept evolved over time.
    
    This tool analyzes the knowledge graph to show:
    1. When something was first mentioned
    2. How it changed over time
    3. Related entities and patterns
    4. AI-generated insights about the evolution
    
    Args:
        user_id: The user whose memories to analyze
        entity_id: UUID of a specific memory to track (optional)
        entity_name: Name of an entity to track (optional)
        time_window: Time filter (last_7_days, last_30_days, last_year, all_time)
        
    Returns:
        AnalyzeOutput with evolution timeline and insights
    """
    logger.info(
        "Analyze evolution tool called",
        user_id=str(user_id),
        entity_name=entity_name,
        time_window=time_window,
    )
    
    # Validate: need either entity_id or entity_name
    if not entity_id and not entity_name:
        raise ValueError("Either entity_id or entity_name must be provided")
    
    # Parse time window
    try:
        window = TimeWindow(time_window)
    except ValueError:
        window = TimeWindow.ALL_TIME
    
    # Get knowledge graph manager
    kg = await get_knowledge_graph()
    
    # If entity_id provided, get the entity name from memory
    resolved_entity_name = entity_name
    if entity_id and not entity_name:
        db = await get_database()
        repo = MemoryRepository(db)
        memory = await repo.get_by_id(entity_id, user_id)
        if memory and memory.entities:
            resolved_entity_name = memory.entities[0]
        else:
            resolved_entity_name = "Unknown"
    
    if not resolved_entity_name:
        raise ValueError("Could not resolve entity name")
    
    # Get evolution timeline
    timeline_data = await kg.get_evolution_timeline(
        user_id=user_id,
        entity_name=resolved_entity_name,
        time_window=window.value,
    )
    
    # Convert to EvolutionEvent objects
    timeline: list[EvolutionEvent] = []
    for event in timeline_data:
        timeline.append(EvolutionEvent(
            date=datetime.fromisoformat(event["date"]),
            memory_id=UUID(event["memory_id"]),
            content_summary=event["content_summary"],
            change_type=event["change_type"],
        ))
    
    # Get related entities
    db = await get_database()
    repo = MemoryRepository(db)
    all_memories = await repo.list_by_user(user_id, limit=100)
    
    related_entities: set[str] = set()
    for memory in all_memories:
        if resolved_entity_name.lower() in [e.lower() for e in memory.entities]:
            related_entities.update(memory.entities)
    
    # Remove the searched entity itself
    related_entities.discard(resolved_entity_name)
    related_list = list(related_entities)[:10]
    
    # Generate insights using LLM
    insights: list[str] = []
    patterns: list[str] = []
    
    if timeline:
        try:
            llm = await get_llm_service()
            
            # Build context for LLM
            timeline_summary = "\n".join([
                f"- {e.date.strftime('%Y-%m-%d')}: {e.content_summary} ({e.change_type})"
                for e in timeline[:10]
            ])
            
            prompt = f"""Analyze this evolution timeline for "{resolved_entity_name}":

{timeline_summary}

Provide:
1. 2-3 key patterns you observe
2. 2-3 insights about how this evolved

Return as JSON:
{{
  "patterns": ["pattern1", "pattern2"],
  "insights": ["insight1", "insight2"]
}}"""
            
            response = await llm.complete(
                prompt,
                system="You are an expert at analyzing user preference evolution. Return only valid JSON.",
                max_tokens=512,
                temperature=0.5,
            )
            
            import json
            try:
                # Clean response
                cleaned = response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                cleaned = cleaned.strip()
                
                data = json.loads(cleaned)
                patterns = data.get("patterns", [])
                insights = data.get("insights", [])
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            logger.warning("Failed to generate insights", error=str(e))
    
    # Calculate stats
    first_mentioned = timeline[0].date if timeline else None
    last_mentioned = timeline[-1].date if timeline else None
    total_mentions = len(timeline)
    
    logger.info(
        "Evolution analysis completed",
        entity=resolved_entity_name,
        total_mentions=total_mentions,
        patterns_found=len(patterns),
    )
    
    return AnalyzeOutput(
        entity_name=resolved_entity_name,
        time_window=window,
        evolution_timeline=timeline,
        patterns=patterns,
        insights=insights,
        related_entities=related_list,
        total_mentions=total_mentions,
        first_mentioned=first_mentioned,
        last_mentioned=last_mentioned,
    )


# Tool specification for MCP
ANALYZE_EVOLUTION_SPEC = {
    "name": "analyze_evolution",
    "description": "Track how an entity, preference, or concept evolved over time. Use this to understand how the user's preferences or knowledge changed.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of a specific memory to track",
            },
            "entity_name": {
                "type": "string",
                "description": "Name of an entity to track (e.g., 'TypeScript', 'async/await')",
            },
            "time_window": {
                "type": "string",
                "enum": ["last_7_days", "last_30_days", "last_year", "all_time"],
                "default": "all_time",
                "description": "Time window for analysis",
            },
        },
    },
}
