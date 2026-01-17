"""
External Service Clients

- EmbeddingService: OpenAI embeddings with caching
- LLMService: Abstraction for Claude/GPT
- ObjectStorageService: S3/R2/GCS storage for documents
"""

from src.services.embedding import EmbeddingService, get_embedding_service
from src.services.llm import LLMService, get_llm_service
from src.services.storage import ObjectStorageService, get_storage

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "LLMService",
    "get_llm_service",
    "ObjectStorageService",
    "get_storage",
]
