"""
Request and Response Schemas for MCP Tools

These schemas define the input/output contracts for each MCP tool.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.memory import Memory, MemoryType, MemoryWithSimilarity


# =============================================================================
# REMEMBER Tool
# =============================================================================

class RememberInput(BaseModel):
    """Input schema for the remember() tool."""
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="The memory content (what to remember)"
    )
    memory_type: MemoryType = Field(
        ...,
        description="Type of memory: episodic, semantic, preference, procedural, meta"
    )
    entities: list[str] | None = Field(
        default=None,
        description="Related entities/concepts (auto-extracted if not provided)"
    )
    importance: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Importance level (1=least, 10=most)"
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional custom metadata"
    )


class RememberOutput(BaseModel):
    """Output schema for the remember() tool."""
    
    memory_id: UUID = Field(..., description="ID of the created memory")
    status: str = Field(default="created", description="Operation status")
    embedding_status: str = Field(
        default="generated",
        description="Status of embedding generation"
    )
    entities_extracted: list[str] = Field(
        default_factory=list,
        description="Entities extracted from content"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )


# =============================================================================
# RECALL Tool
# =============================================================================

class DateRange(str, Enum):
    """Time-based filters for recall."""
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_YEAR = "last_year"
    ALL_TIME = "all_time"


class RecallFilters(BaseModel):
    """Filters for recall queries."""
    
    memory_type: MemoryType | None = Field(
        default=None,
        description="Filter by memory type"
    )
    entity: str | None = Field(
        default=None,
        description="Filter by entity"
    )
    date_range: DateRange | None = Field(
        default=None,
        description="Filter by time range"
    )
    importance_min: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Minimum importance filter"
    )


class RecallInput(BaseModel):
    """Input schema for the recall() tool."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query (semantic search)"
    )
    filters: RecallFilters | None = Field(
        default=None,
        description="Optional filters to narrow results"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )


class RecallOutput(BaseModel):
    """Output schema for the recall() tool."""
    
    query: str = Field(..., description="The original query")
    count: int = Field(..., description="Number of results returned")
    total_available: int = Field(
        ...,
        description="Total matching memories (before limit)"
    )
    memories: list[MemoryWithSimilarity] = Field(
        default_factory=list,
        description="Retrieved memories with similarity scores"
    )
    search_time_ms: int = Field(
        ...,
        description="Search execution time in milliseconds"
    )


# =============================================================================
# CONSOLIDATE_SESSION Tool
# =============================================================================

class ConsolidateInput(BaseModel):
    """Input schema for the consolidate_session() tool."""
    
    session_transcript: str = Field(
        ...,
        min_length=10,
        max_length=100000,
        description="Full conversation transcript to process"
    )
    session_date: datetime | None = Field(
        default=None,
        description="When the session occurred"
    )
    conversation_id: str | None = Field(
        default=None,
        description="Reference ID for the conversation"
    )


class NewMemorySummary(BaseModel):
    """Summary of a newly created memory."""
    
    id: UUID
    content: str
    memory_type: MemoryType
    importance: int
    entities: list[str]


class ConsolidateOutput(BaseModel):
    """Output schema for the consolidate_session() tool."""
    
    consolidation_id: UUID = Field(
        ...,
        description="Unique ID for this consolidation job"
    )
    new_memories_count: int = Field(
        ...,
        description="Number of new memories created"
    )
    new_memories: list[NewMemorySummary] = Field(
        default_factory=list,
        description="Summaries of created memories"
    )
    merged_count: int = Field(
        default=0,
        description="Number of duplicate claims merged"
    )
    conflicts_resolved: int = Field(
        default=0,
        description="Number of conflicts resolved"
    )
    edges_created: int = Field(
        default=0,
        description="Number of knowledge graph edges created"
    )
    patterns_detected: list[str] = Field(
        default_factory=list,
        description="Patterns detected in the session"
    )
    processing_time_ms: int = Field(
        ...,
        description="Total processing time"
    )
    status: str = Field(
        default="completed",
        description="Operation status"
    )


# =============================================================================
# ANALYZE_EVOLUTION Tool
# =============================================================================

class TimeWindow(str, Enum):
    """Time windows for evolution analysis."""
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_YEAR = "last_year"
    ALL_TIME = "all_time"


class AnalyzeInput(BaseModel):
    """Input schema for the analyze_evolution() tool."""
    
    entity_id: UUID | None = Field(
        default=None,
        description="Entity UUID to track"
    )
    entity_name: str | None = Field(
        default=None,
        description="Entity name (alternative to entity_id)"
    )
    time_window: TimeWindow = Field(
        default=TimeWindow.ALL_TIME,
        description="Time window for analysis"
    )


class EvolutionEvent(BaseModel):
    """A single event in the evolution timeline."""
    
    date: datetime = Field(..., description="When this event occurred")
    memory_id: UUID = Field(..., description="Related memory ID")
    content_summary: str = Field(..., description="Brief description")
    change_type: str = Field(
        ...,
        description="Type: introduced, strengthened, weakened, changed, contradicted"
    )
    from_value: str | None = Field(default=None, description="Previous state")
    to_value: str | None = Field(default=None, description="New state")


class AnalyzeOutput(BaseModel):
    """Output schema for the analyze_evolution() tool."""
    
    entity_name: str = Field(..., description="The entity analyzed")
    time_window: TimeWindow = Field(..., description="Analysis time window")
    
    # Timeline
    evolution_timeline: list[EvolutionEvent] = Field(
        default_factory=list,
        description="Chronological list of changes"
    )
    
    # Patterns
    patterns: list[str] = Field(
        default_factory=list,
        description="Detected patterns in evolution"
    )
    
    # Insights
    insights: list[str] = Field(
        default_factory=list,
        description="AI-generated insights about the evolution"
    )
    
    # Related entities
    related_entities: list[str] = Field(
        default_factory=list,
        description="Entities related to this one"
    )
    
    # Stats
    total_mentions: int = Field(
        default=0,
        description="Total times entity was mentioned"
    )
    first_mentioned: datetime | None = Field(
        default=None,
        description="First mention date"
    )
    last_mentioned: datetime | None = Field(
        default=None,
        description="Most recent mention"
    )


# =============================================================================
# EXPORT_MEMORIES Tool
# =============================================================================

class ExportFormat(str, Enum):
    """Export formats."""
    JSON = "json"
    CSV = "csv"


class ExportInput(BaseModel):
    """Input schema for the export_memories() tool."""
    
    format: ExportFormat = Field(
        default=ExportFormat.JSON,
        description="Export format (json or csv)"
    )
    filters: RecallFilters | None = Field(
        default=None,
        description="Optional filters"
    )
    include_embeddings: bool = Field(
        default=False,
        description="Whether to include vector embeddings"
    )


class ExportOutput(BaseModel):
    """Output schema for the export_memories() tool."""
    
    format: ExportFormat = Field(..., description="Export format used")
    count: int = Field(..., description="Number of memories exported")
    data: str | list[dict[str, Any]] = Field(
        ...,
        description="Exported data (JSON string or list of dicts)"
    )
    export_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="When export was generated"
    )
    file_size_bytes: int | None = Field(
        default=None,
        description="Size of exported data"
    )


# =============================================================================
# DELETE_MEMORY Tool
# =============================================================================

class DeleteInput(BaseModel):
    """Input schema for the delete_memory() tool."""
    
    memory_id: UUID = Field(..., description="ID of memory to delete")
    hard_delete: bool = Field(
        default=False,
        description="Whether to permanently delete (vs soft-delete)"
    )


class DeleteOutput(BaseModel):
    """Output schema for the delete_memory() tool."""
    
    memory_id: UUID = Field(..., description="ID of deleted memory")
    deleted: bool = Field(..., description="Whether deletion succeeded")
    deleted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Deletion timestamp"
    )
    deletion_type: Literal["soft", "hard"] = Field(
        default="soft",
        description="Type of deletion performed"
    )
    related_edges_removed: int = Field(
        default=0,
        description="Number of related edges also removed"
    )
