"""
Entity Hub Service

Zettelkasten-style entity extraction and management service.
Uses a self-learning dictionary combined with LLM fallback.
"""

import json
import time
from typing import Any
from uuid import UUID

import structlog

from src.config import get_settings
from src.models.entity_hub import (
    EntityExtractionResult,
    EntityHub,
    EntityHubCreate,
    EntitySource,
    ExtractedEntity,
    HubType,
    MemoryEntityLinkCreate,
)
from src.models.memory import Memory
from src.services.llm import LLMService, get_llm_service
from src.storage.database import Database, get_database
from src.storage.repositories.entity_hub_repo import EntityHubRepository

logger = structlog.get_logger(__name__)


# =============================================================================
# Zettelkasten LLM Prompt
# =============================================================================

ZETTELKASTEN_ENTITY_SYSTEM_PROMPT = """Du bist ein Zettelkasten-Bibliothekar.

DEINE AUFGABE: Identifiziere ZENTRALE KONZEPTE, die diese Information mit anderen verbinden könnten.

REGELN:
1. KEINE trivialen Wörter (Artikel, Mengenangaben, Adjektive, Verben)
2. NUR Konzepte die als "Hub" dienen könnten - Dinge die mehrfach vorkommen werden
3. Personen, Orte, Themen, Events, Rezepte, Technologien sind gute Hubs
4. Generische Begriffe wie "Rezept", "Projekt", "System" sind KEINE guten Hubs

ENTITY TYPEN:
- person: Namen von Menschen (Sarah, Max, Dr. Müller)
- place: Orte, Länder, Städte (Berlin, Italien, Büro)
- event: Ereignisse, Feiertage (Geburtstag, Weihnachten, Meeting)
- recipe: Gerichte, Rezepte (Lasagne, Tiramisu, Jägerschnitzel)
- concept: Abstrakte Konzepte, Hobbies (Fotografie, Minimalismus, Gesundheit)
- tech: Technologien, Tools, Programmiersprachen (Python, Docker, FastAPI)
- project: Projektname, Produkte (Knowwhere, Monday-App)
- organization: Firmen, Vereine (Google, FC Bayern)

BEISPIELE:

Input: "Ich mache Lasagne für Sarahs Geburtstag nächsten Freitag in Berlin"
Output: [
  {"name": "Sarah", "type": "person", "confidence": 0.95},
  {"name": "Lasagne", "type": "recipe", "confidence": 0.9},
  {"name": "Geburtstag", "type": "event", "confidence": 0.85},
  {"name": "Berlin", "type": "place", "confidence": 0.9}
]

Input: "Mein Python-Projekt Knowwhere nutzt FastAPI und PostgreSQL"
Output: [
  {"name": "Knowwhere", "type": "project", "confidence": 0.95},
  {"name": "Python", "type": "tech", "confidence": 0.9},
  {"name": "FastAPI", "type": "tech", "confidence": 0.9},
  {"name": "PostgreSQL", "type": "tech", "confidence": 0.9}
]

FALSCH (NICHT SO):
- ["nächsten", "Freitag", "mache", "nutzt"] ← Triviale Wörter
- ["Rezept", "Projekt", "System", "Daten"] ← Zu generisch
- ["500g", "2 Dosen", "20 Minuten"] ← Mengenangaben

Return ONLY valid JSON array, no other text."""


ZETTELKASTEN_ENTITY_USER_PROMPT = """Analysiere diesen Text und extrahiere die zentralen Zettelkasten-Hubs:

"{content}"

JSON Array (nur die wichtigsten 3-7 Konzepte):"""


# =============================================================================
# Entity Hub Service
# =============================================================================

class EntityHubService:
    """
    Manages the Zettelkasten Entity Hub system.
    
    Features:
    - Self-learning entity dictionary per user
    - LLM-based extraction for unknown entities
    - Memory-entity linking
    - Fast dictionary matching for known entities
    """
    
    def __init__(
        self,
        db: Database | None = None,
        llm_service: LLMService | None = None,
    ):
        self._db = db
        self._llm_service = llm_service
        self._repo: EntityHubRepository | None = None
    
    async def _get_db(self) -> Database:
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def _get_repo(self) -> EntityHubRepository:
        if self._repo is None:
            db = await self._get_db()
            self._repo = EntityHubRepository(db)
        return self._repo
    
    async def _get_llm(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = await get_llm_service()
        return self._llm_service
    
    # =========================================================================
    # Main API: Extract and Learn
    # =========================================================================
    
    async def extract_and_learn(
        self,
        user_id: UUID,
        content: str,
    ) -> EntityExtractionResult:
        """
        Extract entities using the Zettelkasten approach:
        1. Check user's learned dictionary (fast, no LLM)
        2. For unknown terms: LLM classification
        3. Learn new entities into dictionary
        
        Args:
            user_id: User ID
            content: Text to extract entities from
            
        Returns:
            EntityExtractionResult with matched and new entities
        """
        start_time = time.time()
        
        repo = await self._get_repo()
        
        # Step 1: Check dictionary for known entities
        known_entities = await repo.find_matching_entities(user_id, content)
        from_dictionary = [e.display_name or e.entity_name for e in known_entities]
        
        logger.debug(
            "Dictionary match",
            user_id=str(user_id),
            matches=len(known_entities),
        )
        
        # Step 2: Use LLM to extract any additional entities
        llm_entities = await self._extract_via_llm(content)
        
        # Step 3: Filter out entities already in dictionary
        known_names_lower = {e.entity_name.lower() for e in known_entities}
        new_entities = [
            e for e in llm_entities 
            if e.name.lower() not in known_names_lower
        ]
        
        # Step 4: Learn new entities
        learned_hubs: list[EntityHub] = []
        for entity in new_entities:
            hub, was_created = await repo.get_or_create(
                user_id=user_id,
                entity_name=entity.name,
                hub_type=entity.type,
                category=entity.category,
                source=EntitySource.LLM,
                confidence=entity.confidence,
            )
            if was_created:
                learned_hubs.append(hub)
                logger.info(
                    "Learned new entity",
                    name=entity.name,
                    type=entity.type.value,
                )
        
        # Combine all entities
        all_entities = known_entities + learned_hubs
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name=e.display_name or e.entity_name,
                    type=e.hub_type,
                    confidence=e.confidence,
                    category=e.category,
                )
                for e in all_entities
            ],
            from_dictionary=from_dictionary,
            from_llm=[e.name for e in new_entities],
            processing_time_ms=processing_time_ms,
        )
    
    async def _extract_via_llm(self, content: str) -> list[ExtractedEntity]:
        """
        Extract entities using LLM with Zettelkasten prompt.
        """
        if not content or len(content.strip()) < 5:
            return []
        
        try:
            llm = await self._get_llm()
            
            response = await llm.complete(
                prompt=ZETTELKASTEN_ENTITY_USER_PROMPT.format(content=content[:2000]),
                system=ZETTELKASTEN_ENTITY_SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.2,
            )
            
            # Parse JSON response
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            entities_data = json.loads(cleaned)
            
            entities: list[ExtractedEntity] = []
            for item in entities_data:
                if not isinstance(item, dict):
                    continue
                
                name = item.get("name", "").strip()
                if not name or len(name) < 2:
                    continue
                
                # Map type string to HubType enum
                type_str = item.get("type", "concept").lower()
                type_mapping = {
                    "person": HubType.PERSON,
                    "place": HubType.PLACE,
                    "event": HubType.EVENT,
                    "recipe": HubType.RECIPE,
                    "concept": HubType.CONCEPT,
                    "tech": HubType.TECH,
                    "project": HubType.PROJECT,
                    "organization": HubType.ORGANIZATION,
                }
                hub_type = type_mapping.get(type_str, HubType.CONCEPT)
                
                entities.append(ExtractedEntity(
                    name=name,
                    type=hub_type,
                    confidence=float(item.get("confidence", 0.8)),
                    category=item.get("category"),
                ))
            
            logger.debug("LLM extraction", count=len(entities))
            return entities
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM entity response", error=str(e))
            return []
        except Exception as e:
            logger.error("LLM entity extraction failed", error=str(e))
            return []
    
    # =========================================================================
    # Memory Linking
    # =========================================================================
    
    async def link_memory_to_entities(
        self,
        memory: Memory,
        entities: list[ExtractedEntity] | None = None,
    ) -> int:
        """
        Create links between a memory and its entities.
        
        If entities are not provided, extracts them first.
        
        Args:
            memory: The memory to link
            entities: Optional pre-extracted entities
            
        Returns:
            Number of links created
        """
        repo = await self._get_repo()
        
        # Extract entities if not provided
        if entities is None:
            result = await self.extract_and_learn(memory.user_id, memory.content)
            entities = result.entities
        
        if not entities:
            return 0
        
        # Create links
        links_created = 0
        for i, entity in enumerate(entities):
            # Get or create the entity hub
            hub, _ = await repo.get_or_create(
                user_id=memory.user_id,
                entity_name=entity.name,
                hub_type=entity.type,
                category=entity.category,
            )
            
            # Create link
            link = MemoryEntityLinkCreate(
                memory_id=memory.id,
                entity_id=hub.id,
                user_id=memory.user_id,
                strength=entity.confidence,
                is_primary=(i == 0),  # First entity is primary
            )
            
            try:
                await repo.create_link(link)
                links_created += 1
            except Exception as e:
                logger.warning(
                    "Failed to create entity link",
                    memory_id=str(memory.id),
                    entity=entity.name,
                    error=str(e),
                )
        
        logger.info(
            "Memory linked to entities",
            memory_id=str(memory.id),
            links=links_created,
        )
        
        return links_created
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    async def get_user_entities(
        self,
        user_id: UUID,
        limit: int = 50,
        hub_type: HubType | None = None,
    ) -> list[EntityHub]:
        """Get user's top entities."""
        repo = await self._get_repo()
        return await repo.get_top_entities(user_id, limit, hub_type)
    
    async def get_memories_for_entity(
        self,
        user_id: UUID,
        entity_name: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get all memories linked to a specific entity."""
        repo = await self._get_repo()
        
        entity = await repo.get_by_name(user_id, entity_name)
        if not entity:
            return []
        
        return await repo.get_memories_for_entity(entity.id, user_id, limit)
    
    async def get_entity_stats(self, user_id: UUID) -> dict[str, Any]:
        """Get entity statistics for a user."""
        repo = await self._get_repo()
        return await repo.get_entity_stats(user_id)
    
    async def search_entities(
        self,
        user_id: UUID,
        query: str,
        limit: int = 20,
    ) -> list[EntityHub]:
        """Search entities by name."""
        repo = await self._get_repo()
        return await repo.search_entities(user_id, query, limit)


# =============================================================================
# Singleton Instance
# =============================================================================

_entity_hub_service: EntityHubService | None = None


async def get_entity_hub_service() -> EntityHubService:
    """Get or create the global EntityHubService instance."""
    global _entity_hub_service
    
    if _entity_hub_service is None:
        _entity_hub_service = EntityHubService()
    
    return _entity_hub_service
