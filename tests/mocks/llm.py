"""
Mock LLM Service

Provides configurable responses for testing without API calls.
"""

from typing import Any

from src.models.consolidation import Claim, Conflict, ConflictResolution


class MockLLMService:
    """
    Mock implementation of LLMService for testing.
    
    Features:
    - Configurable responses for each method
    - Predefined test claims and patterns
    - Call tracking for verification
    """
    
    def __init__(
        self,
        claims: list[Claim] | None = None,
        entities: list[str] | None = None,
        patterns: list[str] | None = None,
        relationships: list[dict[str, Any]] | None = None,
        complete_response: str = "{}",
    ):
        # Configurable responses
        self._claims = claims
        self._entities = entities or []
        self._patterns = patterns or []
        self._relationships = relationships or []
        self._complete_response = complete_response
        
        # Call tracking
        self._extract_claims_call_count = 0
        self._extract_entities_call_count = 0
        self._resolve_conflict_call_count = 0
        self._infer_relationships_call_count = 0
        self._detect_patterns_call_count = 0
        self._complete_call_count = 0
        
        # Store last inputs for verification
        self._last_transcript: str | None = None
        self._last_conflict: Conflict | None = None
        self._last_prompt: str | None = None
    
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Return configured completion response."""
        self._complete_call_count += 1
        self._last_prompt = prompt
        return self._complete_response
    
    async def extract_claims(self, transcript: str) -> list[Claim]:
        """
        Extract claims from transcript.
        
        Returns configured claims or generates default test claims.
        """
        self._extract_claims_call_count += 1
        self._last_transcript = transcript
        
        if self._claims is not None:
            return self._claims
        
        # Generate default test claims based on transcript content
        return self._generate_default_claims(transcript)
    
    async def resolve_conflict(self, conflict: Conflict) -> ConflictResolution:
        """Resolve a conflict between two claims."""
        self._resolve_conflict_call_count += 1
        self._last_conflict = conflict
        
        return ConflictResolution(
            original_conflict=conflict,
            resolution="Both statements can be true in different contexts",
            is_real_conflict=False,
            evolved_memory=f"User's preference evolved: {conflict.claim_a.claim[:50]}...",
            confidence=0.85,
        )
    
    async def extract_entities(self, text: str) -> list[str]:
        """Extract entities from text."""
        self._extract_entities_call_count += 1
        
        if self._entities:
            return self._entities
        
        # Simple extraction based on common patterns
        return self._simple_entity_extraction(text)
    
    async def infer_relationships(
        self,
        claims: list[Claim],
        entities: list[str],
    ) -> list[dict[str, Any]]:
        """Infer relationships between entities."""
        self._infer_relationships_call_count += 1
        
        if self._relationships:
            return self._relationships
        
        # Generate basic relationships
        relationships = []
        if len(entities) >= 2:
            relationships.append({
                "from_entity": entities[0],
                "to_entity": entities[1],
                "relationship_type": "related_to",
                "confidence": 0.8,
            })
        
        return relationships
    
    async def detect_patterns(self, claims: list[Claim]) -> list[str]:
        """Detect patterns in claims."""
        self._detect_patterns_call_count += 1
        
        if self._patterns:
            return self._patterns
        
        # Generate basic patterns
        patterns = []
        
        preference_claims = [c for c in claims if c.claim_type == "preference"]
        if len(preference_claims) >= 2:
            patterns.append("Consistent technology preferences")
        
        if len(claims) >= 3:
            patterns.append("Active learning and exploration")
        
        return patterns

    async def check_for_contradiction(
        self, 
        old_content: str, 
        new_content: str
    ) -> bool:
        """Mock contradiction check."""
        return "contradict" in new_content.lower() or "not" in new_content.lower()

    async def classify_content(self, content: str) -> dict[str, str | None]:
        """Mock classification."""
        return {"domain": "Test", "category": "General"}

    def _generate_default_claims(self, transcript: str) -> list[Claim]:
        """Generate default test claims from transcript."""
        claims = []
        
        # Look for preference indicators
        if "prefer" in transcript.lower() or "like" in transcript.lower():
            claims.append(Claim(
                claim="User has a preference mentioned in the conversation",
                source="transcript",
                confidence=0.9,
                claim_type="preference",
                entities=["preference"],
            ))
        
        # Look for factual statements
        if "is" in transcript.lower() or "are" in transcript.lower():
            claims.append(Claim(
                claim="Factual information was shared",
                source="transcript",
                confidence=0.85,
                claim_type="fact",
                entities=["fact"],
            ))
        
        # Default claim if none found
        if not claims:
            claims.append(Claim(
                claim="General conversation content",
                source="transcript",
                confidence=0.7,
                claim_type="fact",
                entities=[],
            ))
        
        return claims
    
    def _simple_entity_extraction(self, text: str) -> list[str]:
        """Simple entity extraction without LLM."""
        entities = []
        
        # Common technology keywords
        tech_keywords = [
            "Python", "TypeScript", "JavaScript", "React", "FastAPI",
            "async", "await", "API", "database", "Redis", "PostgreSQL",
        ]
        
        text_lower = text.lower()
        for keyword in tech_keywords:
            if keyword.lower() in text_lower:
                entities.append(keyword)
        
        return list(set(entities))
    
    def set_claims(self, claims: list[Claim]) -> None:
        """Set claims to return from extract_claims()."""
        self._claims = claims
    
    def set_entities(self, entities: list[str]) -> None:
        """Set entities to return from extract_entities()."""
        self._entities = entities
    
    def set_patterns(self, patterns: list[str]) -> None:
        """Set patterns to return from detect_patterns()."""
        self._patterns = patterns
    
    def set_relationships(self, relationships: list[dict[str, Any]]) -> None:
        """Set relationships to return from infer_relationships()."""
        self._relationships = relationships
    
    def set_complete_response(self, response: str) -> None:
        """Set response for complete()."""
        self._complete_response = response
    
    def reset_call_counts(self) -> None:
        """Reset all call counters."""
        self._extract_claims_call_count = 0
        self._extract_entities_call_count = 0
        self._resolve_conflict_call_count = 0
        self._infer_relationships_call_count = 0
        self._detect_patterns_call_count = 0
        self._complete_call_count = 0
    
    @property
    def extract_claims_call_count(self) -> int:
        return self._extract_claims_call_count
    
    @property
    def extract_entities_call_count(self) -> int:
        return self._extract_entities_call_count
    
    @property
    def resolve_conflict_call_count(self) -> int:
        return self._resolve_conflict_call_count
    
    @property
    def complete_call_count(self) -> int:
        return self._complete_call_count
    
    @property
    def last_transcript(self) -> str | None:
        return self._last_transcript
    
    @property
    def last_conflict(self) -> Conflict | None:
        return self._last_conflict
    
    @property
    def last_prompt(self) -> str | None:
        return self._last_prompt


# Convenience function to match the real service pattern
async def get_mock_llm_service() -> MockLLMService:
    """Get a mock LLM service instance."""
    return MockLLMService()
