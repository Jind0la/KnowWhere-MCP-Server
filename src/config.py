"""
Configuration Management

Uses Pydantic Settings for type-safe environment variable handling.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    # Supabase / PostgreSQL
    supabase_url: str
    supabase_key: SecretStr
    database_url: SecretStr
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_password: str | None = None
    redis_db: int = 0
    cache_ttl_memories: int = 3600  # 1 hour
    cache_ttl_preferences: int = 86400  # 24 hours

    # OpenAI (Embeddings)
    openai_api_key: SecretStr
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1408

    # LLM Provider
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    openai_llm_model: str = "gpt-4-turbo-preview"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 100

    # Security
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key_prefix: str = "kw_prod"

    # Consolidation
    consolidation_duplicate_threshold: float = 0.85
    consolidation_conflict_threshold_low: float = 0.5
    consolidation_conflict_threshold_high: float = 0.85

    # Object Storage (S3/R2/GCS)
    storage_provider: str = "s3"  # s3, r2, gcs
    storage_bucket: str = "knowwhere-documents"
    storage_region: str = "us-east-1"
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_endpoint_url: str | None = None  # For R2/MinIO
    storage_max_file_size_mb: int = 50

    # Document Processing
    document_chunk_size: int = 1000
    document_chunk_overlap: int = 200
    tesseract_path: str | None = None  # OCR binary path

    # Feature Flags
    feature_knowledge_graph: bool = True
    feature_document_processing: bool = True
    feature_evolution_tracking: bool = True

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Ensure LLM provider is valid."""
        if v not in ("anthropic", "openai"):
            raise ValueError("llm_provider must be 'anthropic' or 'openai'")
        return v

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, v: int) -> int:
        """Ensure embedding dimensions are valid."""
        valid_dims = [256, 512, 1024, 1408, 1536, 3072]
        if v not in valid_dims:
            raise ValueError(f"embedding_dimensions must be one of {valid_dims}")
        return v

    @property
    def active_llm_api_key(self) -> SecretStr:
        """Get the API key for the active LLM provider."""
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY required when llm_provider=anthropic")
            return self.anthropic_api_key
        else:
            return self.openai_api_key

    @property
    def active_llm_model(self) -> str:
        """Get the model name for the active LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        return self.openai_llm_model


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Convenience function for testing
def get_settings_override(settings: Settings) -> Settings:
    """Override settings for testing."""
    return settings
