"""
Tests for API Key Manager

Tests API key generation, hashing, verification, and management.
"""

import hashlib
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from src.auth.api_keys import APIKeyManager, generate_api_key, hash_api_key
from src.config import Settings
from tests.mocks.database import MockDatabase


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        supabase_url="https://test.supabase.co",
        supabase_key="test-key",
        database_url="postgresql://test:test@localhost:5432/test",
        openai_api_key="sk-test-key",
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test-key",
        api_key_prefix="kw_test",
    )


@pytest_asyncio.fixture
async def mock_db() -> MockDatabase:
    """Create a connected mock database."""
    db = MockDatabase()
    await db.connect()
    return db


@pytest_asyncio.fixture
async def api_key_manager(test_settings: Settings, mock_db: MockDatabase) -> APIKeyManager:
    """Create an API key manager with mock database."""
    return APIKeyManager(settings=test_settings, db=mock_db)


@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return uuid4()


# =============================================================================
# Key Generation Tests
# =============================================================================

class TestKeyGeneration:
    """Tests for API key generation."""

    def test_generate_key_format(self, test_settings: Settings):
        """Test that generated keys have correct format."""
        manager = APIKeyManager(test_settings)
        
        full_key, key_hash = manager.generate_api_key()
        
        # Key should start with prefix
        assert full_key.startswith("kw_test_")
        # Key should be long enough (prefix + underscore + 43 chars from urlsafe b64)
        assert len(full_key) > 50
        # Hash should be 64 chars (SHA-256 hex)
        assert len(key_hash) == 64

    def test_generate_key_unique(self, test_settings: Settings):
        """Test that generated keys are unique."""
        manager = APIKeyManager(test_settings)
        
        keys = set()
        for _ in range(100):
            full_key, _ = manager.generate_api_key()
            keys.add(full_key)
        
        # All 100 keys should be unique
        assert len(keys) == 100

    def test_generate_key_returns_hash(self, test_settings: Settings):
        """Test that generate_api_key returns valid hash."""
        manager = APIKeyManager(test_settings)
        
        full_key, key_hash = manager.generate_api_key()
        
        # Manually compute hash and compare
        expected_hash = hashlib.sha256(full_key.encode()).hexdigest()
        assert key_hash == expected_hash


# =============================================================================
# Hash Tests
# =============================================================================

class TestKeyHashing:
    """Tests for API key hashing."""

    def test_hash_key_deterministic(self):
        """Test that hashing is deterministic."""
        key = "kw_test_abc123xyz"
        
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        
        assert hash1 == hash2

    def test_hash_key_different_for_different_keys(self):
        """Test that different keys produce different hashes."""
        key1 = "kw_test_key_one"
        key2 = "kw_test_key_two"
        
        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)
        
        assert hash1 != hash2

    def test_hash_key_sha256_format(self):
        """Test that hash is valid SHA-256 hex."""
        key = "kw_test_any_key"
        
        key_hash = hash_api_key(key)
        
        # SHA-256 produces 64 hex characters
        assert len(key_hash) == 64
        # Should only contain hex characters
        assert all(c in "0123456789abcdef" for c in key_hash)


# =============================================================================
# Key Prefix Tests
# =============================================================================

class TestKeyPrefix:
    """Tests for key prefix handling."""

    def test_get_key_prefix(self, test_settings: Settings):
        """Test extracting prefix from key."""
        manager = APIKeyManager(test_settings)
        key = "kw_prod_abc123xyz789"
        
        prefix = manager.get_key_prefix(key)
        
        # Returns parts[0]_parts[1][:8] = "kw_prod" (prod is only 4 chars)
        assert prefix == "kw_prod"

    def test_get_key_prefix_short_key(self, test_settings: Settings):
        """Test prefix extraction from short key."""
        manager = APIKeyManager(test_settings)
        key = "short"
        
        prefix = manager.get_key_prefix(key)
        
        assert prefix == "short"[:12]


# =============================================================================
# Create and Verify Tests
# =============================================================================

class TestCreateAndVerify:
    """Tests for creating and verifying API keys."""

    @pytest.mark.asyncio
    async def test_create_api_key(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
        user_id,
    ):
        """Test creating an API key."""
        # Add user to mock DB
        mock_db.add_user(user_id, "test@example.com", "pro")
        
        result = await api_key_manager.create_api_key(
            user_id=user_id,
            name="Test Key",
        )
        
        assert "id" in result
        assert "key" in result
        assert "key_prefix" in result
        assert result["name"] == "Test Key"
        assert result["key"].startswith("kw_test_")

    @pytest.mark.asyncio
    async def test_create_api_key_with_scopes(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
        user_id,
    ):
        """Test creating an API key with custom scopes."""
        mock_db.add_user(user_id, "test@example.com", "pro")
        scopes = ["memories:read", "custom:scope"]
        
        result = await api_key_manager.create_api_key(
            user_id=user_id,
            name="Scoped Key",
            scopes=scopes,
        )
        
        assert result["scopes"] == scopes

    @pytest.mark.asyncio
    async def test_create_api_key_with_expiration(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
        user_id,
    ):
        """Test creating an API key with expiration."""
        mock_db.add_user(user_id, "test@example.com", "pro")
        
        result = await api_key_manager.create_api_key(
            user_id=user_id,
            name="Expiring Key",
            expires_in_days=30,
        )
        
        assert result["expires_at"] is not None
        # Should expire in ~30 days
        expected_expiry = datetime.utcnow() + timedelta(days=30)
        assert abs((result["expires_at"] - expected_expiry).total_seconds()) < 60


# =============================================================================
# Verification Tests
# =============================================================================

class TestKeyVerification:
    """Tests for API key verification."""

    @pytest.mark.asyncio
    async def test_verify_invalid_key(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
    ):
        """Test verifying an invalid key returns None."""
        result = await api_key_manager.verify_api_key("invalid_key_123")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_nonexistent_key(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
    ):
        """Test verifying a nonexistent key returns None."""
        # Create a properly formatted but nonexistent key
        full_key, _ = api_key_manager.generate_api_key()
        
        result = await api_key_manager.verify_api_key(full_key)
        
        assert result is None


# =============================================================================
# List Keys Tests
# =============================================================================

class TestListKeys:
    """Tests for listing user API keys."""

    @pytest.mark.asyncio
    async def test_list_user_keys_empty(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
        user_id,
    ):
        """Test listing keys when user has none."""
        keys = await api_key_manager.list_user_keys(user_id)
        
        assert keys == []


# =============================================================================
# Revoke Tests
# =============================================================================

class TestKeyRevocation:
    """Tests for API key revocation."""

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_key(
        self,
        api_key_manager: APIKeyManager,
        mock_db: MockDatabase,
        user_id,
    ):
        """Test revoking a nonexistent key returns False."""
        result = await api_key_manager.revoke_api_key(uuid4(), user_id)
        
        assert result is False


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_generate_api_key_function(self):
        """Test the generate_api_key convenience function."""
        full_key, key_hash = generate_api_key()
        
        assert full_key is not None
        assert key_hash is not None
        # Default prefix
        assert full_key.startswith("kw_prod_")

    def test_hash_api_key_function(self):
        """Test the hash_api_key convenience function."""
        key = "test_key_123"
        
        result = hash_api_key(key)
        
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert result == expected
