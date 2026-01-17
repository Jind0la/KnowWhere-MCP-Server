"""
Mock Embedding Service

Provides deterministic embeddings for testing without OpenAI API calls.
"""

import hashlib
from typing import Sequence

import numpy as np


class MockEmbeddingService:
    """
    Mock implementation of EmbeddingService for testing.
    
    Features:
    - Deterministic embeddings based on text hash
    - Configurable similarity responses
    - No external API calls
    """
    
    def __init__(
        self,
        dimensions: int = 1408,
        default_similarity: float = 0.85,
    ):
        self.dimensions = dimensions
        self.default_similarity = default_similarity
        self._similarity_overrides: dict[tuple[str, str], float] = {}
        self._embed_call_count = 0
        self._embed_batch_call_count = 0
    
    async def embed(self, text: str) -> list[float]:
        """
        Generate a deterministic embedding based on text hash.
        
        The same text always produces the same embedding.
        """
        self._embed_call_count += 1
        return self._generate_embedding(text)
    
    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        self._embed_batch_call_count += 1
        return [self._generate_embedding(text) for text in texts]
    
    async def similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """
        Calculate similarity between two embeddings.
        
        Returns the configured default similarity unless overridden.
        """
        # Use numpy for actual cosine similarity calculation
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
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
        """Find duplicate pairs among embeddings."""
        if len(embeddings) < 2:
            return []
        
        duplicates = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = await self.similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    duplicates.append((i, j, sim))
        
        return sorted(duplicates, key=lambda x: x[2], reverse=True)
    
    def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate a deterministic embedding vector from text.
        
        Uses SHA-256 hash as seed for reproducible results.
        """
        # Create hash from text
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Use hash as seed for reproducible random numbers
        seed = int(text_hash[:8], 16)
        rng = np.random.default_rng(seed)
        
        # Generate normalized embedding
        embedding = rng.standard_normal(self.dimensions)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.tolist()
    
    def set_similarity_override(
        self,
        text1: str,
        text2: str,
        similarity: float,
    ) -> None:
        """Set a specific similarity score for two texts."""
        key = tuple(sorted([text1, text2]))
        self._similarity_overrides[key] = similarity
    
    def reset_call_counts(self) -> None:
        """Reset call counters."""
        self._embed_call_count = 0
        self._embed_batch_call_count = 0
    
    @property
    def embed_call_count(self) -> int:
        """Number of times embed() was called."""
        return self._embed_call_count
    
    @property
    def embed_batch_call_count(self) -> int:
        """Number of times embed_batch() was called."""
        return self._embed_batch_call_count


# Convenience function to match the real service pattern
async def get_mock_embedding_service() -> MockEmbeddingService:
    """Get a mock embedding service instance."""
    return MockEmbeddingService()
