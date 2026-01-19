"""
Entity Hub Repository

Data access layer for Entity Hub management in the Zettelkasten system.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.models.entity_hub import (
    EntityHub,
    EntityHubCreate,
    EntityHubUpdate,
    EntitySource,
    HubType,
    MemoryEntityLink,
    MemoryEntityLinkCreate,
)
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class EntityHubRepository:
    """
    Repository for Entity Hub CRUD operations.
    
    Provides:
    - Create, read, update, delete for entity hubs
    - Memory-entity linking
    - Dictionary lookup for fast matching
    - Entity statistics
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    # =========================================================================
    # Entity Hub CRUD
    # =========================================================================
    
    async def create(self, entity: EntityHubCreate) -> EntityHub:
        """Create a new entity hub."""
        query = """
            INSERT INTO entity_hubs (
                user_id, entity_name, display_name, canonical_name,
                category, hub_type, aliases, source, confidence,
                embedding, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            entity.user_id,
            entity.entity_name.lower().strip(),  # Normalize
            entity.display_name or entity.entity_name,
            entity.canonical_name,
            entity.category,
            entity.hub_type.value,
            entity.aliases,
            entity.source.value,
            entity.confidence,
            entity.embedding,
            json.dumps(entity.metadata) if entity.metadata else None,
        )
        
        logger.info(
            "Entity hub created",
            entity_id=str(row["id"]),
            name=entity.entity_name,
            type=entity.hub_type.value,
        )
        return self._row_to_entity_hub(row)
    
    async def get_by_id(self, entity_id: UUID, user_id: UUID) -> EntityHub | None:
        """Get entity hub by ID."""
        query = """
            SELECT * FROM entity_hubs
            WHERE id = $1 AND user_id = $2
        """
        row = await self.db.fetchrow(query, entity_id, user_id)
        return self._row_to_entity_hub(row) if row else None
    
    async def get_by_name(self, user_id: UUID, entity_name: str) -> EntityHub | None:
        """Get entity hub by name (case-insensitive)."""
        query = """
            SELECT * FROM entity_hubs
            WHERE user_id = $1 AND LOWER(entity_name) = LOWER($2)
        """
        row = await self.db.fetchrow(query, user_id, entity_name.strip())
        return self._row_to_entity_hub(row) if row else None
    
    async def get_or_create(
        self,
        user_id: UUID,
        entity_name: str,
        hub_type: HubType = HubType.CONCEPT,
        category: str | None = None,
        source: EntitySource = EntitySource.LLM,
        confidence: float = 0.8,
    ) -> tuple[EntityHub, bool]:
        """
        Get existing entity or create new one.
        
        Returns:
            Tuple of (EntityHub, was_created)
        """
        existing = await self.get_by_name(user_id, entity_name)
        if existing:
            return existing, False
        
        from src.models.entity_hub import EntityHubCreate
        
        # Create new entity
        entity_create = EntityHubCreate(
            user_id=user_id,
            entity_name=entity_name.lower().strip(),
            display_name=entity_name.strip(),
            hub_type=hub_type,
            category=category,
            source=source,
            confidence=confidence,
        )
        
        try:
            created = await self.create(entity_create)
            return created, True
        except Exception as e:
            # If creation failed, it might be due to a race condition
            # Try fetching one more time
            existing = await self.get_by_name(user_id, entity_name)
            if existing:
                return existing, False
            raise e
    
    async def update(
        self,
        entity_id: UUID,
        user_id: UUID,
        update_data: EntityHubUpdate,
    ) -> EntityHub | None:
        """Update an entity hub."""
        updates = []
        params: list[Any] = []
        param_idx = 1
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            if value is not None:
                if field == "hub_type":
                    value = value.value
                elif field == "metadata":
                    value = json.dumps(value)
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not updates:
            return await self.get_by_id(entity_id, user_id)
        
        params.extend([entity_id, user_id])
        
        query = f"""
            UPDATE entity_hubs
            SET {', '.join(updates)}
            WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, *params)
        return self._row_to_entity_hub(row) if row else None
    
    async def delete(self, entity_id: UUID, user_id: UUID) -> bool:
        """Delete an entity hub."""
        query = """
            DELETE FROM entity_hubs
            WHERE id = $1 AND user_id = $2
            RETURNING id
        """
        result = await self.db.fetchval(query, entity_id, user_id)
        return result is not None
    
    # =========================================================================
    # Dictionary Lookup (Fast Matching)
    # =========================================================================
    
    async def get_user_dictionary(
        self,
        user_id: UUID,
        limit: int = 500,
    ) -> dict[str, EntityHub]:
        """
        Get user's learned entity dictionary for fast matching.
        
        Returns:
            Dict mapping normalized entity names to EntityHub objects
        """
        query = """
            SELECT * FROM entity_hubs
            WHERE user_id = $1
            ORDER BY usage_count DESC
            LIMIT $2
        """
        
        rows = await self.db.fetch(query, user_id, limit)
        
        dictionary: dict[str, EntityHub] = {}
        for row in rows:
            entity = self._row_to_entity_hub(row)
            dictionary[entity.entity_name.lower()] = entity
            
            # Also add aliases to dictionary
            for alias in entity.aliases:
                dictionary[alias.lower()] = entity
        
        return dictionary
    
    async def find_matching_entities(
        self,
        user_id: UUID,
        text: str,
    ) -> list[EntityHub]:
        """
        Find all user's learned entities that match in the given text.
        
        Uses both exact matching and alias matching.
        """
        dictionary = await self.get_user_dictionary(user_id)
        text_lower = text.lower()
        
        matched: list[EntityHub] = []
        seen_ids: set[UUID] = set()
        
        for name, entity in dictionary.items():
            if entity.id in seen_ids:
                continue
            
            # Check if entity name or alias appears in text
            if name in text_lower:
                matched.append(entity)
                seen_ids.add(entity.id)
        
        return matched
    
    async def search_entities(
        self,
        user_id: UUID,
        query: str,
        limit: int = 20,
    ) -> list[EntityHub]:
        """Search entities by name (fuzzy matching)."""
        sql = """
            SELECT *, 
                   similarity(entity_name, $2) AS sim
            FROM entity_hubs
            WHERE user_id = $1 
              AND (
                  entity_name % $2 
                  OR entity_name ILIKE '%' || $2 || '%'
                  OR $2 = ANY(aliases)
              )
            ORDER BY sim DESC, usage_count DESC
            LIMIT $3
        """
        
        rows = await self.db.fetch(sql, user_id, query.lower(), limit)
        return [self._row_to_entity_hub(row) for row in rows]
    
    # =========================================================================
    # Entity Statistics
    # =========================================================================
    
    async def get_top_entities(
        self,
        user_id: UUID,
        limit: int = 20,
        hub_type: HubType | None = None,
    ) -> list[EntityHub]:
        """Get top entities by usage count."""
        conditions = ["user_id = $1"]
        params: list[Any] = [user_id]
        
        if hub_type:
            conditions.append("hub_type = $2")
            params.append(hub_type.value)
            params.append(limit)
            limit_param = "$3"
        else:
            params.append(limit)
            limit_param = "$2"
        
        query = f"""
            SELECT * FROM entity_hubs
            WHERE {' AND '.join(conditions)}
            ORDER BY memory_count DESC, usage_count DESC
            LIMIT {limit_param}
        """
        
        rows = await self.db.fetch(query, *params)
        return [self._row_to_entity_hub(row) for row in rows]
    
    async def get_entity_stats(self, user_id: UUID) -> dict[str, Any]:
        """Get comprehensive entity statistics."""
        query = """
            SELECT
                COUNT(*) as total_entities,
                COUNT(CASE WHEN hub_type = 'person' THEN 1 END) as person_count,
                COUNT(CASE WHEN hub_type = 'place' THEN 1 END) as place_count,
                COUNT(CASE WHEN hub_type = 'event' THEN 1 END) as event_count,
                COUNT(CASE WHEN hub_type = 'recipe' THEN 1 END) as recipe_count,
                COUNT(CASE WHEN hub_type = 'concept' THEN 1 END) as concept_count,
                COUNT(CASE WHEN hub_type = 'tech' THEN 1 END) as tech_count,
                SUM(memory_count) as total_links,
                AVG(usage_count) as avg_usage
            FROM entity_hubs
            WHERE user_id = $1
        """
        
        row = await self.db.fetchrow(query, user_id)
        
        if not row:
            return {
                "total_entities": 0,
                "by_type": {},
                "total_links": 0,
                "avg_usage": 0.0,
            }
        
        return {
            "total_entities": row["total_entities"],
            "by_type": {
                "person": row["person_count"],
                "place": row["place_count"],
                "event": row["event_count"],
                "recipe": row["recipe_count"],
                "concept": row["concept_count"],
                "tech": row["tech_count"],
            },
            "total_links": row["total_links"] or 0,
            "avg_usage": float(row["avg_usage"] or 0.0),
        }
    
    # =========================================================================
    # Memory-Entity Links
    # =========================================================================
    
    async def create_link(self, link: MemoryEntityLinkCreate) -> MemoryEntityLink:
        """Create a memory-entity link."""
        query = """
            INSERT INTO memory_entity_links (
                memory_id, entity_id, user_id, strength, 
                is_primary, mention_count, context_snippet
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (memory_id, entity_id) 
            DO UPDATE SET
                strength = GREATEST(memory_entity_links.strength, EXCLUDED.strength),
                mention_count = memory_entity_links.mention_count + 1
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            link.memory_id,
            link.entity_id,
            link.user_id,
            link.strength,
            link.is_primary,
            link.mention_count,
            link.context_snippet,
        )
        
        return self._row_to_link(row)
    
    async def create_links_batch(
        self,
        links: list[MemoryEntityLinkCreate],
    ) -> list[MemoryEntityLink]:
        """Create multiple memory-entity links."""
        results: list[MemoryEntityLink] = []
        for link in links:
            try:
                result = await self.create_link(link)
                results.append(result)
            except Exception as e:
                logger.warning(
                    "Failed to create link",
                    memory_id=str(link.memory_id),
                    entity_id=str(link.entity_id),
                    error=str(e),
                )
        return results
    
    async def get_links_for_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
    ) -> list[MemoryEntityLink]:
        """Get all entity links for a memory."""
        query = """
            SELECT * FROM memory_entity_links
            WHERE memory_id = $1 AND user_id = $2
            ORDER BY is_primary DESC, strength DESC
        """
        rows = await self.db.fetch(query, memory_id, user_id)
        return [self._row_to_link(row) for row in rows]
    
    async def get_memories_for_entity(
        self,
        entity_id: UUID,
        user_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get all memories linked to an entity."""
        query = """
            SELECT 
                m.id, m.content, m.memory_type, m.importance,
                mel.strength, mel.is_primary, mel.created_at as link_created
            FROM memory_entity_links mel
            INNER JOIN memories m ON m.id = mel.memory_id
            WHERE mel.entity_id = $1 AND mel.user_id = $2 AND m.status = 'active'
            ORDER BY mel.is_primary DESC, mel.strength DESC, m.created_at DESC
            LIMIT $3
        """
        
        rows = await self.db.fetch(query, entity_id, user_id, limit)
        return [dict(row) for row in rows]
    
    async def delete_links_for_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
    ) -> int:
        """Delete all entity links for a memory."""
        query = """
            DELETE FROM memory_entity_links
            WHERE memory_id = $1 AND user_id = $2
            RETURNING id
        """
        rows = await self.db.fetch(query, memory_id, user_id)
        return len(rows)
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _row_to_entity_hub(self, row: Any) -> EntityHub:
        """Convert database row to EntityHub model."""
        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        aliases = row.get("aliases") or []
        if isinstance(aliases, str):
            aliases = json.loads(aliases)
        
        return EntityHub(
            id=row["id"],
            user_id=row["user_id"],
            entity_name=row["entity_name"],
            display_name=row.get("display_name"),
            canonical_name=row.get("canonical_name"),
            category=row.get("category"),
            hub_type=HubType(row["hub_type"]),
            usage_count=row.get("usage_count", 1),
            memory_count=row.get("memory_count", 0),
            last_used=row.get("last_used"),
            aliases=aliases,
            source=EntitySource(row.get("source", "llm")),
            confidence=row.get("confidence", 0.8),
            embedding=row.get("embedding"),
            metadata=metadata,
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
        )
    
    def _row_to_link(self, row: Any) -> MemoryEntityLink:
        """Convert database row to MemoryEntityLink model."""
        return MemoryEntityLink(
            id=row["id"],
            memory_id=row["memory_id"],
            entity_id=row["entity_id"],
            user_id=row["user_id"],
            strength=row.get("strength", 1.0),
            is_primary=row.get("is_primary", False),
            mention_count=row.get("mention_count", 1),
            context_snippet=row.get("context_snippet"),
            created_at=row["created_at"],
        )
