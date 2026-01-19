"""
Consolidation Models

Models for session consolidation process and results.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConsolidationStatus(str, Enum):
    """Status of a consolidation job."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Claim(BaseModel):
    """
    A claim extracted from a conversation transcript.
    
    Claims are factual statements, preferences, or learnings
    that can be converted into memories.
    """
    
    claim: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The extracted claim text"
    )
    source: str = Field(
        default="transcript",
        description="Which part of the transcript this came from"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in the extraction"
    )
    claim_type: str | None = Field(
        default=None,
        description="Type: preference, fact, learning, decision, workflow, insight, etc."
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Entities mentioned in this claim (max 5)"
    )
    importance: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Importance score 1-10 (10 = very personal/important)"
    )
    domain: str | None = Field(default=None, description="Semantic Domain (e.g. Knowwhere)")
    category: str | None = Field(default=None, description="Semantic Category (e.g. Backend)")
    
    def to_memory_type(self) -> str:
        """Map claim type to memory type."""
        type_mapping = {
            "preference": "preference",
            "decision": "preference",  # Decisions reflect preferences
            "workflow": "procedural",
            "insight": "semantic",
            "project_fact": "semantic",
            "tool_usage": "semantic",
            "fact": "semantic",
            "learning": "episodic",
            "how_to": "procedural",
            "struggle": "episodic",
        }
        return type_mapping.get(self.claim_type or "", "semantic")


class DuplicateGroup(BaseModel):
    """A group of duplicate claims."""
    
    claims: list[Claim] = Field(
        ...,
        min_length=2,
        description="Claims that are duplicates of each other"
    )
    canonical: Claim = Field(
        ...,
        description="The canonical (primary) claim to keep"
    )
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average similarity within the group"
    )


class Conflict(BaseModel):
    """A detected conflict between two claims."""
    
    claim_a: Claim = Field(..., description="First conflicting claim")
    claim_b: Claim = Field(..., description="Second conflicting claim")
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score between claims"
    )
    conflict_type: str = Field(
        default="preference_conflict",
        description="Type of conflict detected"
    )


class ConflictResolution(BaseModel):
    """Result of resolving a conflict."""
    
    original_conflict: Conflict = Field(
        ...,
        description="The original conflict"
    )
    resolution: str = Field(
        ...,
        description="Explanation of how both claims can be true"
    )
    is_real_conflict: bool = Field(
        ...,
        description="Whether this is a true contradiction"
    )
    evolved_memory: str | None = Field(
        default=None,
        description="If there's evolution, describe it"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in the resolution"
    )


class Relationship(BaseModel):
    """An inferred relationship between entities."""
    
    from_entity: str = Field(..., description="Source entity")
    to_entity: str = Field(..., description="Target entity")
    relationship_type: str = Field(
        ...,
        description="Type: likes, dislikes, led_to, related_to, etc."
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence in this relationship"
    )


class ConsolidationResult(BaseModel):
    """
    Result of consolidating a session transcript.
    
    Contains all the extracted memories, merged duplicates,
    resolved conflicts, and created knowledge graph edges.
    """
    
    consolidation_id: UUID = Field(
        default_factory=uuid4,
        description="Unique ID for this consolidation"
    )
    user_id: UUID = Field(..., description="User who owns these memories")
    conversation_id: str | None = Field(default=None, description="Optional conversation reference")
    
    # Processing stats
    session_transcript_length: int = Field(
        default=0,
        description="Character count of input transcript"
    )
    claims_extracted: int = Field(
        default=0,
        description="Number of claims extracted"
    )
    
    # Results
    new_memories_count: int = Field(
        default=0,
        description="Number of new memories created"
    )
    new_memory_ids: list[UUID] = Field(
        default_factory=list,
        description="IDs of newly created memories"
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
    
    # Analysis
    patterns_detected: list[str] = Field(
        default_factory=list,
        description="Patterns detected in the session"
    )
    key_entities: list[str] = Field(
        default_factory=list,
        description="Most important entities mentioned"
    )
    
    # Timing
    processing_time_ms: int = Field(
        default=0,
        description="Total processing time in milliseconds"
    )
    
    # Status
    status: ConsolidationStatus = Field(
        default=ConsolidationStatus.COMPLETED,
        description="Status of the consolidation"
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if failed"
    )
    
    # Timestamp
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When consolidation was performed"
    )


class ConsolidationHistory(BaseModel):
    """
    Historical record of a consolidation job.
    
    Stored in the database for audit and analytics.
    """
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    user_id: UUID = Field(..., description="User who performed consolidation")
    
    # Session info
    consolidation_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="Date of consolidation"
    )
    session_id: str | None = Field(
        default=None,
        description="Session identifier"
    )
    conversation_id: str | None = Field(
        default=None,
        description="Conversation reference"
    )
    
    # Processing stats
    session_transcript_length: int = Field(
        default=0,
        description="Input character count"
    )
    claims_extracted: int = Field(default=0)
    memories_processed: int = Field(default=0)
    new_memories_created: int = Field(default=0)
    merged_count: int = Field(default=0)
    conflicts_resolved: int = Field(default=0)
    edges_created: int = Field(default=0)
    
    # Performance
    processing_time_ms: int = Field(default=0)
    tokens_used: int = Field(default=0, description="LLM tokens consumed")
    embedding_cost_usd: float = Field(default=0.0)
    
    # Quality
    duplicate_similarity_threshold: float = Field(default=0.85)
    conflict_similarity_range: str = Field(default="0.5-0.85")
    
    # Analysis
    patterns_detected: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    sentiment_analysis: dict[str, Any] = Field(default_factory=dict)
    
    # Status
    status: ConsolidationStatus = Field(default=ConsolidationStatus.COMPLETED)
    error_message: str | None = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
