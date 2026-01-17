"""
Embedding Service

OpenAI embeddings with batching and caching support.
"""

import hashlib
from typing import Sequence

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings
from src.storage.cache import CacheService, get_cache

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.
    
    Features:
    - Async embedding generation
    - Batch processing for efficiency
    - Redis caching to avoid re-computation
    - Automatic retry on failure
    """
    
    def __init__(
        self,
        settings: Settings | None = None,
        cache: CacheService | None = None,
    ):
        self.settings = settings or get_settings()
        self._cache = cache
        self._client: AsyncOpenAI | None = None
    
    @property
    def client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client
    
    async def get_cache(self) -> CacheService:
        """Get cache service."""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            1408-dimensional embedding vector
        """
        # Check cache first
        cache = await self.get_cache()
        cached = await cache.get_embedding(text)
        if cached is not None:
            logger.debug("Embedding cache hit", text_hash=self._hash_text(text)[:8])
            return cached
        
        # Generate embedding
        logger.debug("Generating embedding", text_length=len(text))
        
        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=text,
            dimensions=self.settings.embedding_dimensions,
        )
        
        embedding = response.data[0].embedding
        
        # Cache result
        await cache.set_embedding(text, embedding)
        
        logger.debug(
            "Embedding generated",
            dimensions=len(embedding),
            tokens=response.usage.total_tokens if response.usage else 0,
        )
        
        return embedding
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Check cache for each text
        cache = await self.get_cache()
        results: dict[int, list[float]] = {}
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        
        for i, text in enumerate(texts):
            cached = await cache.get_embedding(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
        
        if not uncached_texts:
            logger.debug("All embeddings from cache", count=len(texts))
            return [results[i] for i in range(len(texts))]
        
        # Generate embeddings for uncached texts
        logger.debug(
            "Generating batch embeddings",
            total=len(texts),
            cached=len(results),
            to_generate=len(uncached_texts),
        )
        
        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=uncached_texts,
            dimensions=self.settings.embedding_dimensions,
        )
        
        # Match results to original indices and cache them
        for j, data in enumerate(response.data):
            original_idx = uncached_indices[j]
            embedding = data.embedding
            results[original_idx] = embedding
            
            # Cache each embedding
            await cache.set_embedding(uncached_texts[j], embedding)
        
        logger.debug(
            "Batch embeddings generated",
            count=len(uncached_texts),
            tokens=response.usage.total_tokens if response.usage else 0,
        )
        
        # Return in original order
        return [results[i] for i in range(len(texts))]
    
    async def similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score between 0 and 1
        """
        import numpy as np
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def find_duplicates(
        self,
        embeddings: list[list[float]],
        threshold: float = 0.85,
    ) -> list[tuple[int, int, float]]:
        """
        Find duplicate pairs among embeddings.
        
        Args:
            embeddings: List of embeddings to compare
            threshold: Similarity threshold for duplicates
            
        Returns:
            List of (index1, index2, similarity) tuples
        """
        import numpy as np
        
        if len(embeddings) < 2:
            return []
        
        # Convert to numpy array for efficient computation
        matrix = np.array(embeddings)
        
        # Compute pairwise similarities
        # Normalize vectors
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = matrix / norms
        
        # Compute similarity matrix
        similarities = np.dot(normalized, normalized.T)
        
        # Find pairs above threshold
        duplicates = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = float(similarities[i, j])
                if sim >= threshold:
                    duplicates.append((i, j, sim))
        
        return sorted(duplicates, key=lambda x: x[2], reverse=True)
    
    def estimate_cost(self, texts: Sequence[str]) -> float:
        """
        Estimate embedding cost in USD.
        
        Based on OpenAI pricing: $0.02 per 1M tokens
        """
        # Rough estimate: 1 token ≈ 4 characters
        total_chars = sum(len(t) for t in texts)
        estimated_tokens = total_chars / 4
        
        cost_per_million = 0.02
        return (estimated_tokens / 1_000_000) * cost_per_million
    
    def _hash_text(self, text: str) -> str:
        """Generate hash for text (for logging/debugging)."""
        return hashlib.sha256(text.encode()).hexdigest()


# Global embedding service instance
_embedding_service: EmbeddingService | None = None


async def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    
    return _embedding_service
