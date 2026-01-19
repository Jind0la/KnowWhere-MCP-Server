"""
Entity Hub Model

Represents a Zettelkasten-style entity node that connects memories.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class HubType(str, Enum):
    """Type of entity hub."""
    PERSON = "person"
    PLACE = "place"
    EVENT = "event"
    RECIPE = "recipe"
    CONCEPT = "concept"
    TECH = "tech"
    PROJECT = "project"
    ORGANIZATION = "organization"


class EntitySource(str, Enum):
    """How the entity was learned."""
    LLM = "llm"
    USER_DEFINED = "user_defined"
    SYSTEM = "system"
    IMPORTED = "imported"


class EntityHubBase(BaseModel):
    """Base entity hub fields."""
    
    entity_name: str = Field(
        ...,
        max_length=255,
        description="Normalized entity name (lowercase)"
    )
    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Display name with original casing"
    )
    canonical_name: str | None = Field(
        default=None,
        max_length=500,
        description="User-defined label (e.g., 'Sarah (Freundin)')"
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        description="Zettelkasten category (e.g., 'Personal Contacts')"
    )
    hub_type: HubType = Field(
        default=HubType.CONCEPT,
        description="Type of entity hub"
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names for fuzzy matching"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in this classification"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class EntityHubCreate(EntityHubBase):
    """Schema for creating an entity hub."""
    
    user_id: UUID = Field(..., description="Owner of the entity")
    source: EntitySource = Field(
        default=EntitySource.LLM,
        description="How the entity was learned"
    )
    embedding: list[float] | None = Field(
        default=None,
        description="Optional embedding vector"
    )


class EntityHub(EntityHubBase):
    """Full entity hub entity."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    user_id: UUID = Field(..., description="Owner of the entity")
    
    # Stats
    usage_count: int = Field(default=1, description="How many times used")
    memory_count: int = Field(default=0, description="How many memories reference this")
    last_used: datetime = Field(default_factory=datetime.utcnow)
    
    # Source
    source: EntitySource = Field(default=EntitySource.LLM)
    
    # Embedding (optional)
    embedding: list[float] | None = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}

    def matches(self, text: str) -> bool:
        """Check if this entity matches the given text."""
        text_lower = text.lower()
        
        # Check main name
        if self.entity_name.lower() in text_lower:
            return True
        
        # Check aliases
        for alias in self.aliases:
            if alias.lower() in text_lower:
                return True
        
        return False


class EntityHubUpdate(BaseModel):
    """Schema for updating an entity hub."""
    
    display_name: str | None = None
    canonical_name: str | None = None
    category: str | None = None
    hub_type: HubType | None = None
    aliases: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] | None = None


# =============================================================================
# Memory-Entity Link Models
# =============================================================================

class MemoryEntityLinkCreate(BaseModel):
    """Schema for creating a memory-entity link."""
    
    memory_id: UUID = Field(..., description="Memory ID")
    entity_id: UUID = Field(..., description="Entity hub ID")
    user_id: UUID = Field(..., description="Owner")
    strength: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Link strength"
    )
    is_primary: bool = Field(
        default=False,
        description="Is this the primary entity of the memory"
    )
    mention_count: int = Field(
        default=1,
        description="How many times mentioned in the memory"
    )
    context_snippet: str | None = Field(
        default=None,
        max_length=500,
        description="Surrounding text context"
    )


class MemoryEntityLink(MemoryEntityLinkCreate):
    """Full memory-entity link entity."""
    
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


# =============================================================================
# LLM Response Models
# =============================================================================

class ExtractedEntity(BaseModel):
    """Entity extracted by LLM."""
    
    name: str = Field(..., description="Entity name")
    type: HubType = Field(default=HubType.CONCEPT, description="Entity type")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    category: str | None = Field(default=None, description="Suggested category")


class EntityExtractionResult(BaseModel):
    """Result of entity extraction."""
    
    entities: list[ExtractedEntity] = Field(default_factory=list)
    from_dictionary: list[str] = Field(
        default_factory=list,
        description="Entities matched from user's dictionary"
    )
    from_llm: list[str] = Field(
        default_factory=list,
        description="Entities newly extracted by LLM"
    )
    processing_time_ms: int = Field(default=0)
