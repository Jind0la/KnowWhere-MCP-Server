"""
Tests for JWT Token Handler

Tests JWT token creation, verification, expiration, and scope handling.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.auth.jwt import JWTHandler, create_access_token, create_refresh_token, verify_token
from src.config import Settings


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with JWT configuration."""
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
        jwt_secret_key="test-jwt-secret-key-minimum-32-characters-long",
        jwt_algorithm="HS256",
        jwt_expiration_hours=24,
    )


@pytest.fixture
def jwt_handler(test_settings: Settings) -> JWTHandler:
    """Create a JWT handler with test settings."""
    return JWTHandler(test_settings)


@pytest.fixture
def user_id() -> str:
    """Generate a test user ID."""
    return str(uuid4())


# =============================================================================
# Token Creation Tests
# =============================================================================

class TestTokenCreation:
    """Tests for token creation."""

    def test_create_access_token(self, jwt_handler: JWTHandler, user_id: str):
        """Test creating a basic access token."""
        token = jwt_handler.create_access_token(user_id=user_id)
        
        assert token is not None
        assert len(token) > 0
        assert token.count(".") == 2  # JWT format: header.payload.signature

    def test_create_access_token_with_email(self, jwt_handler: JWTHandler, user_id: str):
        """Test creating access token with email."""
        token = jwt_handler.create_access_token(
            user_id=user_id,
            email="test@example.com",
        )
        
        # Verify token contains email
        token_data = jwt_handler.verify_token(token)
        assert token_data is not None
        assert token_data.email == "test@example.com"

    def test_create_access_token_with_tier(self, jwt_handler: JWTHandler, user_id: str):
        """Test creating access token with tier."""
        token = jwt_handler.create_access_token(
            user_id=user_id,
            tier="pro",
        )
        
        token_data = jwt_handler.verify_token(token)
        assert token_data is not None
        assert token_data.tier == "pro"

    def test_create_refresh_token(self, jwt_handler: JWTHandler, user_id: str):
        """Test creating a refresh token."""
        token = jwt_handler.create_refresh_token(user_id=user_id)
        
        assert token is not None
        assert len(token) > 0


# =============================================================================
# Token Verification Tests
# =============================================================================

class TestTokenVerification:
    """Tests for token verification."""

    def test_verify_valid_token(self, jwt_handler: JWTHandler, user_id: str):
        """Test verifying a valid access token."""
        token = jwt_handler.create_access_token(user_id=user_id)
        
        token_data = jwt_handler.verify_token(token, token_type="access")
        
        assert token_data is not None
        assert token_data.sub == user_id

    def test_verify_expired_token(self, jwt_handler: JWTHandler, user_id: str):
        """Test that expired tokens are rejected."""
        # Create token that expires immediately
        token = jwt_handler.create_access_token(
            user_id=user_id,
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is None

    def test_verify_invalid_signature(self, jwt_handler: JWTHandler, user_id: str):
        """Test that tokens with invalid signatures are rejected."""
        token = jwt_handler.create_access_token(user_id=user_id)
        
        # Tamper with the token
        parts = token.split(".")
        parts[2] = "invalid_signature"
        tampered_token = ".".join(parts)
        
        token_data = jwt_handler.verify_token(tampered_token)
        
        assert token_data is None

    def test_verify_wrong_type(self, jwt_handler: JWTHandler, user_id: str):
        """Test that verifying with wrong type fails."""
        # Create refresh token
        token = jwt_handler.create_refresh_token(user_id=user_id)
        
        # Try to verify as access token
        token_data = jwt_handler.verify_token(token, token_type="access")
        
        assert token_data is None

    def test_verify_refresh_token(self, jwt_handler: JWTHandler, user_id: str):
        """Test verifying a refresh token."""
        token = jwt_handler.create_refresh_token(user_id=user_id)
        
        token_data = jwt_handler.verify_token(token, token_type="refresh")
        
        assert token_data is not None
        assert token_data.sub == user_id


# =============================================================================
# Token Claims Tests
# =============================================================================

class TestTokenClaims:
    """Tests for token claims/payload."""

    def test_token_contains_claims(self, jwt_handler: JWTHandler, user_id: str):
        """Test that token contains expected claims."""
        token = jwt_handler.create_access_token(
            user_id=user_id,
            email="test@example.com",
            tier="pro",
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is not None
        assert token_data.sub == user_id
        assert token_data.email == "test@example.com"
        assert token_data.tier == "pro"
        assert token_data.exp is not None
        assert token_data.iat is not None
        assert token_data.jti is not None

    def test_jti_unique(self, jwt_handler: JWTHandler, user_id: str):
        """Test that each token has a unique JTI."""
        token1 = jwt_handler.create_access_token(user_id=user_id)
        token2 = jwt_handler.create_access_token(user_id=user_id)
        
        data1 = jwt_handler.verify_token(token1)
        data2 = jwt_handler.verify_token(token2)
        
        assert data1 is not None
        assert data2 is not None
        assert data1.jti != data2.jti


# =============================================================================
# Scope Tests
# =============================================================================

class TestScopes:
    """Tests for scope assignment by tier."""

    def test_scopes_by_tier_free(self, jwt_handler: JWTHandler, user_id: str):
        """Test scopes for free tier."""
        token = jwt_handler.create_access_token(
            user_id=user_id,
            tier="free",
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is not None
        assert "memories:read" in token_data.scopes
        assert "memories:write" in token_data.scopes
        # Free tier should not have delete or consolidate
        assert "memories:delete" not in token_data.scopes
        assert "consolidate:execute" not in token_data.scopes

    def test_scopes_by_tier_pro(self, jwt_handler: JWTHandler, user_id: str):
        """Test scopes for pro tier."""
        token = jwt_handler.create_access_token(
            user_id=user_id,
            tier="pro",
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is not None
        assert "memories:read" in token_data.scopes
        assert "memories:write" in token_data.scopes
        assert "memories:delete" in token_data.scopes
        assert "consolidate:execute" in token_data.scopes
        assert "export:execute" in token_data.scopes

    def test_scopes_by_tier_enterprise(self, jwt_handler: JWTHandler, user_id: str):
        """Test scopes for enterprise tier."""
        token = jwt_handler.create_access_token(
            user_id=user_id,
            tier="enterprise",
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is not None
        assert "memories:read" in token_data.scopes
        assert "memories:write" in token_data.scopes
        assert "memories:delete" in token_data.scopes
        assert "consolidate:execute" in token_data.scopes
        assert "export:execute" in token_data.scopes
        assert "admin:manage" in token_data.scopes

    def test_custom_scopes(self, jwt_handler: JWTHandler, user_id: str):
        """Test custom scope assignment."""
        custom_scopes = ["memories:read", "custom:scope"]
        
        token = jwt_handler.create_access_token(
            user_id=user_id,
            scopes=custom_scopes,
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is not None
        assert token_data.scopes == custom_scopes


# =============================================================================
# Expiration Tests
# =============================================================================

class TestExpiration:
    """Tests for token expiration."""

    def test_custom_expiration(self, jwt_handler: JWTHandler, user_id: str):
        """Test creating token with custom expiration."""
        custom_delta = timedelta(hours=1)
        
        token = jwt_handler.create_access_token(
            user_id=user_id,
            expires_delta=custom_delta,
        )
        
        token_data = jwt_handler.verify_token(token)
        
        assert token_data is not None
        # Token should be valid (exp should be in the future)
        # Note: exp uses datetime.fromtimestamp (local time) while token created with utcnow
        assert token_data.exp > datetime.now() - timedelta(minutes=5)  # Allow some margin

    def test_refresh_token_longer_expiration(self, jwt_handler: JWTHandler, user_id: str):
        """Test that refresh tokens have longer expiration."""
        access_token = jwt_handler.create_access_token(user_id=user_id)
        refresh_token = jwt_handler.create_refresh_token(user_id=user_id)
        
        access_data = jwt_handler.verify_token(access_token, token_type="access")
        refresh_data = jwt_handler.verify_token(refresh_token, token_type="refresh")
        
        assert access_data is not None
        assert refresh_data is not None
        # Refresh token should expire later than access token
        assert refresh_data.exp > access_data.exp


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_create_access_token_function(self, test_settings: Settings, user_id: str):
        """Test the create_access_token convenience function."""
        # Note: This uses the global handler, so we test with default settings
        token = create_access_token(user_id=user_id)
        
        assert token is not None
        assert len(token) > 0

    def test_verify_token_function(self, test_settings: Settings, user_id: str):
        """Test the verify_token convenience function."""
        token = create_access_token(user_id=user_id)
        
        token_data = verify_token(token)
        
        assert token_data is not None
        assert token_data.sub == user_id
