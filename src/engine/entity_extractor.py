"""
Entity Extractor

Extracts named entities from text using LLM and heuristics.
"""

import re
from typing import Set

import structlog

from src.services.llm import LLMService, get_llm_service

logger = structlog.get_logger(__name__)


# Common technology entities for fast matching
KNOWN_TECHNOLOGIES = {
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "julia",
    
    # Web frameworks
    "react", "vue", "angular", "svelte", "next.js", "nextjs", "nuxt", "remix",
    "fastapi", "django", "flask", "express", "nestjs", "rails", "laravel",
    
    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch",
    "sqlite", "dynamodb", "cassandra", "neo4j", "supabase", "firebase",
    
    # Cloud/DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform",
    "github actions", "gitlab ci", "jenkins", "vercel", "netlify", "railway",
    
    # AI/ML
    "openai", "anthropic", "claude", "gpt", "llm", "langchain", "llamaindex",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
    
    # Tools
    "git", "npm", "yarn", "pnpm", "pip", "poetry", "vscode", "cursor",
    "postman", "figma", "notion", "slack", "discord",
    
    # Concepts
    "async/await", "rest api", "graphql", "websocket", "microservices",
    "serverless", "ci/cd", "devops", "agile", "scrum",
}


class EntityExtractor:
    """
    Extracts named entities from text.
    
    Uses a combination of:
    - Known technology dictionary matching
    - Pattern-based extraction
    - LLM-based extraction for complex cases
    """
    
    def __init__(self, llm_service: LLMService | None = None):
        self._llm_service = llm_service
    
    async def _get_llm_service(self) -> LLMService:
        """Get LLM service instance."""
        if self._llm_service is None:
            self._llm_service = await get_llm_service()
        return self._llm_service
    
    async def extract(self, text: str, use_llm: bool = True) -> list[str]:
        """
        Extract entities from text.
        
        Args:
            text: Text to analyze
            use_llm: Whether to use LLM for extraction (more accurate but slower)
            
        Returns:
            List of unique entity names
        """
        entities: Set[str] = set()
        
        # Fast path: dictionary matching
        dict_entities = self._extract_from_dictionary(text)
        entities.update(dict_entities)
        
        # Pattern matching
        pattern_entities = self._extract_from_patterns(text)
        entities.update(pattern_entities)
        
        # LLM extraction for more complex cases
        if use_llm:
            try:
                llm = await self._get_llm_service()
                llm_entities = await llm.extract_entities(text)
                entities.update(llm_entities)
            except Exception as e:
                logger.warning("LLM entity extraction failed", error=str(e))
        
        # Normalize and deduplicate
        normalized = self._normalize_entities(list(entities))
        
        logger.debug(
            "Entities extracted",
            text_length=len(text),
            entity_count=len(normalized),
        )
        
        return normalized
    
    def extract_fast(self, text: str) -> list[str]:
        """
        Fast entity extraction without LLM (synchronous).
        
        Uses only dictionary and pattern matching.
        """
        entities: Set[str] = set()
        
        dict_entities = self._extract_from_dictionary(text)
        entities.update(dict_entities)
        
        pattern_entities = self._extract_from_patterns(text)
        entities.update(pattern_entities)
        
        return self._normalize_entities(list(entities))
    
    def _extract_from_dictionary(self, text: str) -> Set[str]:
        """Extract entities by matching against known technology dictionary."""
        entities: Set[str] = set()
        text_lower = text.lower()
        
        for tech in KNOWN_TECHNOLOGIES:
            # Use word boundary matching
            pattern = r'\b' + re.escape(tech) + r'\b'
            if re.search(pattern, text_lower):
                # Return with original casing from dictionary
                entities.add(tech.title() if len(tech) > 3 else tech.upper())
        
        return entities
    
    def _extract_from_patterns(self, text: str) -> Set[str]:
        """Extract entities using regex patterns."""
        entities: Set[str] = set()
        
        # CamelCase words (likely class/framework names)
        camel_case = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', text)
        entities.update(camel_case)
        
        # Package-style names (e.g., fastapi, nextjs)
        package_names = re.findall(r'\b[a-z]+(?:-[a-z]+)+\b', text)
        entities.update(name for name in package_names if len(name) > 3)
        
        # npm-style package names (e.g., @scope/package)
        npm_packages = re.findall(r'@[\w-]+/[\w-]+', text)
        entities.update(npm_packages)
        
        # Version-qualified names (e.g., Python 3.11, Node 18)
        versioned = re.findall(r'\b([A-Z][a-z]+)\s*\d+(?:\.\d+)*\b', text)
        entities.update(versioned)
        
        # File extensions as technology indicators
        extensions = re.findall(r'\.([a-z]{2,4})\b', text.lower())
        extension_map = {
            'py': 'Python',
            'ts': 'TypeScript',
            'js': 'JavaScript',
            'rs': 'Rust',
            'go': 'Go',
            'rb': 'Ruby',
            'java': 'Java',
            'sql': 'SQL',
        }
        for ext in extensions:
            if ext in extension_map:
                entities.add(extension_map[ext])
        
        return entities
    
    def _normalize_entities(self, entities: list[str]) -> list[str]:
        """
        Normalize and deduplicate entities.
        
        - Remove duplicates (case-insensitive)
        - Apply standard casing
        - Filter out too short or invalid entries
        """
        seen: Set[str] = set()
        normalized: list[str] = []
        
        # Standard casing for known technologies
        casing_map = {
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "postgresql": "PostgreSQL",
            "mongodb": "MongoDB",
            "graphql": "GraphQL",
            "nextjs": "Next.js",
            "nodejs": "Node.js",
            "vuejs": "Vue.js",
            "reactjs": "React",
            "github": "GitHub",
            "gitlab": "GitLab",
            "vscode": "VS Code",
            "fastapi": "FastAPI",
            "openai": "OpenAI",
            "chatgpt": "ChatGPT",
            "aws": "AWS",
            "gcp": "GCP",
            "api": "API",
            "sql": "SQL",
            "css": "CSS",
            "html": "HTML",
            "json": "JSON",
            "xml": "XML",
            "yaml": "YAML",
            "llm": "LLM",
            "ai": "AI",
            "ml": "ML",
        }
        
        for entity in entities:
            if not entity or len(entity) < 2:
                continue
            
            # Normalize key for deduplication
            key = entity.lower().strip()
            
            if key in seen:
                continue
            seen.add(key)
            
            # Apply standard casing if known
            if key in casing_map:
                normalized.append(casing_map[key])
            else:
                # Keep original casing
                normalized.append(entity.strip())
        
        return sorted(normalized)
    
    def merge_entity_lists(self, *entity_lists: list[str]) -> list[str]:
        """Merge multiple entity lists into one deduplicated list."""
        all_entities: Set[str] = set()
        for entities in entity_lists:
            all_entities.update(entities)
        return self._normalize_entities(list(all_entities))


# Singleton instance
_entity_extractor: EntityExtractor | None = None


async def get_entity_extractor() -> EntityExtractor:
    """Get or create the global entity extractor."""
    global _entity_extractor
    
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    
    return _entity_extractor
