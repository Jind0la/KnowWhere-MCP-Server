"""
Knowledge Edge Model

Represents relationships between memories in the knowledge graph.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EdgeType(str, Enum):
    """
    Types of relationships between memories.
    
    - LEADS_TO: One memory leads to another (causality)
    - RELATED_TO: General relationship
    - CONTRADICTS: Memories contradict each other
    - SUPPORTS: One memory supports another
    - LIKES: Preference relationship (user likes X)
    - DISLIKES: Negative preference
    - DEPENDS_ON: Dependency relationship
    - EVOLVES_INTO: Evolution of a concept/preference
    """
    LEADS_TO = "leads_to"
    RELATED_TO = "related_to"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    LIKES = "likes"
    DISLIKES = "dislikes"
    DEPENDS_ON = "depends_on"
    EVOLVES_INTO = "evolves_into"


class EdgeBase(BaseModel):
    """Base edge fields."""
    
    edge_type: EdgeType = Field(
        ...,
        description="Type of relationship"
    )
    strength: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Relationship strength (0-1)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in this relationship"
    )
    causality: bool = Field(
        default=False,
        description="Is this a causal relationship?"
    )
    bidirectional: bool = Field(
        default=False,
        description="Does this relationship work both ways?"
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Why does this relationship exist?"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class EdgeCreate(EdgeBase):
    """Schema for creating a knowledge edge."""
    
    user_id: UUID = Field(..., description="Owner of the edge")
    from_node_id: UUID = Field(..., description="Source memory ID")
    to_node_id: UUID = Field(..., description="Target memory ID")

    @model_validator(mode="after")
    def validate_no_self_reference(self) -> "EdgeCreate":
        """Ensure edge doesn't reference the same node."""
        if self.from_node_id == self.to_node_id:
            raise ValueError("Edge cannot reference the same memory (self-reference)")
        return self


class KnowledgeEdge(EdgeBase):
    """
    Full knowledge edge entity.
    
    Represents a directed edge in the knowledge graph connecting two memories.
    """
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    user_id: UUID = Field(..., description="Owner of the edge")
    from_node_id: UUID = Field(..., description="Source memory ID")
    to_node_id: UUID = Field(..., description="Target memory ID")
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def validate_no_self_reference(self) -> "KnowledgeEdge":
        """Ensure edge doesn't reference the same node."""
        if self.from_node_id == self.to_node_id:
            raise ValueError("Edge cannot reference the same memory (self-reference)")
        return self

    def is_causal(self) -> bool:
        """Check if this is a causal relationship."""
        return self.causality or self.edge_type in (
            EdgeType.LEADS_TO,
            EdgeType.EVOLVES_INTO,
            EdgeType.DEPENDS_ON,
        )

    def is_strong(self, threshold: float = 0.7) -> bool:
        """Check if relationship is strong."""
        return self.strength >= threshold


class EdgeWithNodes(KnowledgeEdge):
    """Edge with expanded node information."""
    
    from_node_content: str | None = Field(
        default=None,
        description="Content preview of source memory"
    )
    to_node_content: str | None = Field(
        default=None,
        description="Content preview of target memory"
    )


class EdgeUpdate(BaseModel):
    """Schema for updating an edge."""
    
    edge_type: EdgeType | None = None
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    causality: bool | None = None
    bidirectional: bool | None = None
    reason: str | None = None
    metadata: dict[str, Any] | None = None
