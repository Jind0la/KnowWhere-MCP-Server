"""
LLM Service

Abstraction layer for LLM providers (Claude/GPT).
Handles claim extraction, conflict resolution, and entity extraction.
"""

import json
from typing import Any, Literal

import structlog
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings
from src.models.consolidation import Claim, ConflictResolution, Conflict

logger = structlog.get_logger(__name__)


class LLMService:
    """
    Abstraction for LLM operations supporting both Claude and GPT.
    
    Features:
    - Provider-agnostic interface
    - Claim extraction from transcripts
    - Conflict detection and resolution
    - Entity extraction
    - Automatic retry on failure
    """
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._anthropic_client: AsyncAnthropic | None = None
        self._openai_client: AsyncOpenAI | None = None
    
    @property
    def provider(self) -> Literal["anthropic", "openai"]:
        """Get the configured LLM provider."""
        return self.settings.llm_provider
    
    @property
    def anthropic(self) -> AsyncAnthropic:
        """Get or create Anthropic client."""
        if self._anthropic_client is None:
            api_key = self.settings.anthropic_api_key
            if api_key is None:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self._anthropic_client = AsyncAnthropic(
                api_key=api_key.get_secret_value()
            )
        return self._anthropic_client
    
    @property
    def openai(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._openai_client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a completion from the LLM.
        
        Args:
            prompt: User prompt
            system: System message
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        if self.provider == "anthropic":
            return await self._complete_anthropic(prompt, system, max_tokens, temperature)
        else:
            return await self._complete_openai(prompt, system, max_tokens, temperature)
    
    async def _complete_anthropic(
        self,
        prompt: str,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Complete using Claude."""
        message = await self.anthropic.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            system=system or "You are a helpful AI assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        
        # Extract text from response
        text_content = next(
            (block.text for block in message.content if hasattr(block, "text")),
            ""
        )
        
        logger.debug(
            "Claude completion",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
        
        return text_content
    
    async def _complete_openai(
        self,
        prompt: str,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Complete using GPT."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.openai.chat.completions.create(
            model=self.settings.openai_llm_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        content = response.choices[0].message.content or ""
        
        logger.debug(
            "GPT completion",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        
        return content
    
    async def extract_claims(self, transcript: str) -> list[Claim]:
        """
        Extract factual claims from a conversation transcript.
        
        Args:
            transcript: Conversation text
            
        Returns:
            List of extracted claims
        """
        system = """Du bist ein Experte für das Extrahieren von wichtigen Erkenntnissen aus Gesprächen.

WICHTIGE REGELN:
1. SPRACHE BEIBEHALTEN: Antworte in der GLEICHEN SPRACHE wie das Transcript (Deutsch → Deutsch, English → English)
2. QUALITÄT > QUANTITÄT: Extrahiere nur WIRKLICH wichtige Aussagen
3. KEINE TRIVIALEN SCHRITTE: Ignoriere offensichtliche technische Schritte wie "User installiert X" oder "User führt Befehl aus"
4. PERSÖNLICHER FOKUS: Priorisiere persönliche Präferenzen, Entscheidungen und Erkenntnisse

PRIORISIERUNG (von hoch nach niedrig):
🔴 HOCH: Persönliche Präferenzen, Lieblingsprojekte, Arbeitsweise
🟠 MITTEL: Entscheidungen mit Begründung, Erkenntnisse, Workflows
🟡 NIEDRIG: Reine Fakten ohne persönlichen Bezug
⚪ IGNORIEREN: Triviale Befehle, offensichtliche Schritte, temporäre Zustände

Return ONLY valid JSON, no other text."""

        prompt = f"""Analysiere dieses Gespräch und extrahiere die WICHTIGSTEN Erkenntnisse über den User.

EXTRAHIERE NUR:
✅ Persönliche Präferenzen ("Ich bevorzuge...", "Mein Lieblings...")
✅ Entscheidungen mit Kontext ("Ich habe mich für X entschieden weil...")
✅ Erkenntnisse & Learnings ("Ich habe gelernt dass...")
✅ Arbeitsweise & Workflows ("Ich arbeite normalerweise mit...")
✅ Projektbezogene Fakten ("Mein Projekt heißt...", "Ich arbeite an...")
✅ Technologie-Stack & Tools die der User aktiv nutzt

IGNORIERE:
❌ Einzelne Befehle oder Installationsschritte
❌ Temporäre Debugging-Sessions
❌ Offensichtliche Aussagen ohne Mehrwert
❌ Reine Fragen ohne Antwort

Für jeden Claim:
1. "claim": Aussage in der ORIGINALSPRACHE des Transcripts (klar, eigenständig)
2. "source": Woher im Gespräch (kurz)
3. "confidence": Sicherheit (0.0-1.0)
4. "claim_type": Einer von:
   - "preference" (persönliche Vorliebe)
   - "decision" (Entscheidung mit Begründung)
   - "workflow" (Arbeitsweise, Prozess)
   - "insight" (Erkenntnis, Learning)
   - "project_fact" (Fakt über Projekt/Arbeit)
   - "tool_usage" (aktiv genutzte Tools/Tech)
   - "struggle" (Problem, Herausforderung)
5. "entities": Wichtige Entities (max 5)
6. "importance": Wichtigkeit 1-10 (10 = sehr persönlich/wichtig)

Transcript:
---
{transcript}
---

JSON Array (max 10-15 Claims, nur die wichtigsten):"""

        response = await self.complete(prompt, system, max_tokens=4096, temperature=0.3)
        
        # Parse JSON response
        try:
            # Clean response (remove markdown code blocks if present)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            claims_data = json.loads(cleaned)
            
            claims = []
            for item in claims_data:
                # Map new claim_types to existing memory types
                claim_type = item.get("claim_type", "fact")
                type_mapping = {
                    "preference": "preference",
                    "decision": "preference",  # Decisions are often preferences
                    "workflow": "procedural",
                    "insight": "semantic",
                    "project_fact": "semantic",
                    "tool_usage": "semantic",
                    "struggle": "episodic",
                    "how_to": "procedural",
                    "fact": "semantic",
                    "learning": "semantic",
                }
                mapped_type = type_mapping.get(claim_type, "semantic")
                
                # Get importance from response or calculate from confidence
                importance = item.get("importance")
                if importance is None:
                    # Derive importance from confidence and type
                    base_importance = int(item.get("confidence", 0.8) * 10)
                    if claim_type == "preference":
                        base_importance = min(10, base_importance + 2)
                    importance = base_importance
                
                claims.append(Claim(
                    claim=item.get("claim", ""),
                    source=item.get("source", "transcript"),
                    confidence=float(item.get("confidence", 0.8)),
                    claim_type=mapped_type,
                    entities=item.get("entities", [])[:5],  # Limit entities
                    importance=int(importance),
                ))
            
            # Sort by importance and limit
            claims.sort(key=lambda c: c.importance if hasattr(c, 'importance') else 5, reverse=True)
            
            logger.info("Claims extracted", count=len(claims))
            return claims
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse claims JSON", error=str(e), response=response[:200])
            return []
    
    async def resolve_conflict(self, conflict: Conflict) -> ConflictResolution:
        """
        Resolve a conflict between two claims.
        
        Args:
            conflict: The conflict to resolve
            
        Returns:
            Resolution with explanation
        """
        system = """You are an expert at analyzing potentially conflicting statements and understanding nuance.
Your goal is to determine if two statements truly conflict or if they can both be true in different contexts.
Return ONLY valid JSON, no other text."""

        prompt = f"""Analyze these two potentially conflicting statements from the same user:

Statement A: "{conflict.claim_a.claim}"
Statement B: "{conflict.claim_b.claim}"

Similarity score: {conflict.similarity:.2f}

Determine:
1. Are these truly contradictory, or can both be true?
2. If both can be true, explain how (e.g., different contexts, evolution of thinking)
3. If there's been an evolution in preference/thinking, describe it

Return JSON:
{{
  "resolution": "Explanation of how both statements relate",
  "is_real_conflict": true/false,
  "evolved_memory": "If there's evolution, describe the change (or null)",
  "confidence": 0.0-1.0
}}

JSON Response:"""

        response = await self.complete(prompt, system, max_tokens=1024, temperature=0.3)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            
            return ConflictResolution(
                original_conflict=conflict,
                resolution=data.get("resolution", "Could not resolve"),
                is_real_conflict=data.get("is_real_conflict", True),
                evolved_memory=data.get("evolved_memory"),
                confidence=float(data.get("confidence", 0.7)),
            )
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse resolution JSON", error=str(e))
            return ConflictResolution(
                original_conflict=conflict,
                resolution="Could not automatically resolve this conflict",
                is_real_conflict=True,
                evolved_memory=None,
                confidence=0.5,
            )
    
    async def extract_entities(self, text: str) -> list[str]:
        """
        Extract named entities from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of entity names
        """
        system = """You are an expert at extracting named entities from text.
Focus on: technologies, programming languages, frameworks, tools, concepts, people, organizations.
Return ONLY a JSON array of strings, no other text."""

        prompt = f"""Extract all important entities from this text:

"{text}"

Return a JSON array of entity names. Example: ["Python", "FastAPI", "async/await", "TypeScript"]

JSON Response:"""

        response = await self.complete(prompt, system, max_tokens=512, temperature=0.2)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            entities = json.loads(cleaned)
            return entities if isinstance(entities, list) else []
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse entities JSON")
            return []
    
    async def infer_relationships(
        self,
        claims: list[Claim],
        entities: list[str],
    ) -> list[dict[str, Any]]:
        """
        Infer relationships between entities based on claims.
        
        Args:
            claims: List of claims mentioning entities
            entities: List of known entities
            
        Returns:
            List of relationship dictionaries
        """
        if not entities or len(entities) < 2:
            return []
        
        claims_text = "\n".join([f"- {c.claim}" for c in claims])
        entities_text = ", ".join(entities)
        
        system = """You are an expert at inferring relationships between concepts based on context.
Return ONLY valid JSON, no other text."""

        prompt = f"""Based on these statements, infer relationships between the entities.

Statements:
{claims_text}

Entities: {entities_text}

For each relationship found, provide:
1. "from_entity": Source entity name
2. "to_entity": Target entity name  
3. "relationship_type": One of: likes, dislikes, leads_to, related_to, depends_on, evolves_into
4. "confidence": Your confidence (0.0-1.0)

Return a JSON array. Example:
[
  {{"from_entity": "TypeScript", "to_entity": "JavaScript", "relationship_type": "related_to", "confidence": 0.9}}
]

JSON Response:"""

        response = await self.complete(prompt, system, max_tokens=1024, temperature=0.3)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            relationships = json.loads(cleaned)
            return relationships if isinstance(relationships, list) else []
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse relationships JSON")
            return []
    
    async def detect_patterns(self, claims: list[Claim]) -> list[str]:
        """
        Detect patterns in a list of claims.
        
        Args:
            claims: List of claims to analyze
            
        Returns:
            List of detected patterns as strings
        """
        if not claims:
            return []
        
        claims_text = "\n".join([f"- {c.claim} (type: {c.claim_type})" for c in claims])
        
        # Detect language from claims
        sample_text = " ".join([c.claim for c in claims[:3]])
        is_german = any(word in sample_text.lower() for word in ["der", "die", "das", "und", "ist", "für", "mit"])
        
        system = """Du bist ein Experte für das Erkennen von Mustern in Nutzerverhalten und Präferenzen.
Antworte in der GLEICHEN SPRACHE wie die Eingabe.
Return ONLY a JSON array of strings, no other text.""" if is_german else """You are an expert at identifying patterns in user behavior and preferences.
Respond in the SAME LANGUAGE as the input.
Return ONLY a JSON array of strings, no other text."""

        prompt = f"""Analysiere diese Aussagen und identifiziere Muster:

{claims_text}

Suche nach:
- 🎯 Konsistente Präferenzen (z.B. "Bevorzugt moderne Tools")
- 📈 Entwicklung im Denken (z.B. "Wechsel von X zu Y")
- 🔄 Wiederkehrende Themen (z.B. "Fokus auf Developer Experience")
- 💡 Lern-Patterns (z.B. "Lernt durch praktische Projekte")
- 🛠️ Arbeitsweise (z.B. "Iterativer Entwicklungsansatz")

Return JSON array mit 3-5 Pattern-Beschreibungen.
Jedes Pattern sollte spezifisch und aussagekräftig sein.

Beispiel: ["Bevorzugt TypeScript für bessere Typsicherheit", "Nutzt Docker für konsistente Entwicklungsumgebungen"]

JSON:"""

        response = await self.complete(prompt, system, max_tokens=512, temperature=0.5)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            patterns = json.loads(cleaned)
            return patterns if isinstance(patterns, list) else []
            
        except json.JSONDecodeError:
            return []


# Global LLM service instance
_llm_service: LLMService | None = None


async def get_llm_service() -> LLMService:
    """Get or create the global LLM service."""
    global _llm_service
    
    if _llm_service is None:
        _llm_service = LLMService()
    
    return _llm_service
