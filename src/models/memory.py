"""
Memory Model

The core entity representing a piece of knowledge stored in the system.
Supports 5 memory types: episodic, semantic, preference, procedural, meta.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class MemoryType(str, Enum):
    """
    Types of memories following cognitive science principles.
    
    - EPISODIC: Specific events/conversations (e.g., "In session #42, user said...")
    - SEMANTIC: Facts and relationships (e.g., "TypeScript is a superset of JavaScript")
    - PREFERENCE: User preferences (e.g., "User prefers async/await over callbacks")
    - PROCEDURAL: How-to knowledge (e.g., "To setup React with TypeScript: npm create...")
    - META: Meta-cognitive knowledge (e.g., "User struggles with async concepts")
    """
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    PROCEDURAL = "procedural"
    META = "meta"


class MemoryStatus(str, Enum):
    """Memory lifecycle status."""
    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"
    DELETED = "deleted"
    SUPERSEDED = "superseded"
    IRRELEVANT = "irrelevant"  # Knowledge that is no longer useful but kept for history
    STALE = "stale"            # Knowledge that might be outdated



class MemorySource(str, Enum):
    """Source of the memory."""
    CONVERSATION = "conversation"
    DOCUMENT = "document"
    IMPORT = "import"
    MANUAL = "manual"
    CONSOLIDATION = "consolidation"


class MemoryBase(BaseModel):
    """Base memory fields shared across create/read operations."""
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="The memory content (what to remember)"
    )
    memory_type: MemoryType = Field(
        ...,
        description="Type of memory (episodic, semantic, preference, procedural, meta)"
    )
    status: MemoryStatus = Field(
        default=MemoryStatus.ACTIVE,
        description="Current status"
    )
    entities: list[str] = Field(
        default_factory=list,
        description="List of entities/concepts extracted from the memory"
    )
    domain: str | None = Field(
        default=None,
        description="High-level project or domain (e.g. Knowwhere, Personal)"
    )
    category: str | None = Field(
        default=None,
        description="Functional category or topic (e.g. Backend, Auth)"
    )
    importance: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Importance level (1=least, 10=most)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for this memory"
    )
    source: MemorySource = Field(
        default=MemorySource.CONVERSATION,
        description="Where this memory originated"
    )
    source_id: str | None = Field(
        default=None,
        description="Reference ID (conversation_id, file_id, etc.)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom metadata"
    )


class MemoryCreate(MemoryBase):
    """Schema for creating a new memory."""
    
    user_id: UUID = Field(..., description="Owner of the memory")
    embedding: list[float] | None = Field(
        default=None,
        description="Vector embedding (auto-generated if not provided)"
    )

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: list[float] | None) -> list[float] | None:
        """Validate embedding dimensions."""
        if v is not None and len(v) != 1408:
            raise ValueError(f"Embedding must have 1408 dimensions, got {len(v)}")
        return v


class Memory(MemoryBase):
    """
    Full memory entity with all fields.
    
    This is the complete representation of a memory as stored in the database.
    """
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    user_id: UUID = Field(..., description="Owner of the memory")
    embedding: list[float] | None = Field(
        default=None,
        description="Vector embedding (1408 dimensions)",
        exclude=True,  # Never include embeddings in JSON responses
    )
    
    # Status tracking is now in base, but Memory keeps it for full schema
    status: MemoryStatus = Field(
        default=MemoryStatus.ACTIVE,
        description="Current status"
    )
    superseded_by: UUID | None = Field(
        default=None,
        description="ID of memory that supersedes this one"
    )
    
    # Access tracking
    access_count: int = Field(
        default=0,
        description="Number of times this memory was recalled"
    )
    last_accessed: datetime | None = Field(
        default=None,
        description="Last time this memory was recalled"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    deleted_at: datetime | None = Field(
        default=None,
        description="Soft delete timestamp"
    )

    model_config = {"from_attributes": True}

    @property
    def content_preview(self) -> str:
        """Get first 500 characters of content for display."""
        return self.content[:500] if len(self.content) > 500 else self.content

    def is_preference(self) -> bool:
        """Check if this is a preference memory."""
        return self.memory_type == MemoryType.PREFERENCE

    def is_active(self) -> bool:
        """Check if memory is active."""
        return self.status == MemoryStatus.ACTIVE


class MemoryWithSimilarity(Memory):
    """Memory with similarity score from vector search."""
    
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity score"
    )
    
    @property
    def relevance_score(self) -> float:
        """
        Combined relevance score considering similarity and importance.
        
        Formula: similarity * (1 + importance/10)
        """
        return self.similarity * (1 + self.importance / 10)


class MemoryUpdate(BaseModel):
    """Schema for updating a memory."""
    
    content: str | None = None
    memory_type: MemoryType | None = None
    entities: list[str] | None = None
    importance: int | None = Field(default=None, ge=1, le=10)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: MemoryStatus | None = None
    superseded_by: UUID | None = None
    metadata: dict[str, Any] | None = None
