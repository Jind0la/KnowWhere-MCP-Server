"""
Authentication Models

Pydantic models for authentication.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AuthUser(BaseModel):
    """Authenticated user context."""
    
    id: UUID = Field(..., description="User UUID")
    email: EmailStr = Field(..., description="User email")
    tier: str = Field(default="free", description="Subscription tier")
    scopes: list[str] = Field(
        default_factory=list,
        description="Permission scopes"
    )
    
    # Authentication method
    auth_method: str = Field(
        default="jwt",
        description="How user authenticated (jwt, api_key)"
    )
    
    # Rate limiting
    rate_limit_requests_per_minute: int = Field(
        default=100,
        description="User's rate limit"
    )

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope."""
        return scope in self.scopes or "admin:manage" in self.scopes

    def can_write_memories(self) -> bool:
        """Check if user can create/update memories."""
        return self.has_scope("memories:write")

    def can_delete_memories(self) -> bool:
        """Check if user can delete memories."""
        return self.has_scope("memories:delete")


class TokenData(BaseModel):
    """JWT token payload data."""
    
    sub: str = Field(..., description="Subject (user_id)")
    email: Optional[str] = None
    tier: Optional[str] = None
    scopes: list[str] = Field(default_factory=list)
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # JWT ID for revocation


class TokenRequest(BaseModel):
    """OAuth token request."""
    
    grant_type: str = Field(
        ...,
        description="OAuth grant type (password, refresh_token)"
    )
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    """OAuth token response."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(
        default=86400,
        description="Token lifetime in seconds"
    )
    refresh_token: Optional[str] = Field(
        None,
        description="Refresh token for obtaining new access tokens"
    )
    scope: str = Field(
        default="memories:read memories:write",
        description="Granted scopes"
    )


class APIKeyCreate(BaseModel):
    """Request to create an API key."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name for the key"
    )
    scopes: list[str] = Field(
        default_factory=lambda: ["memories:read", "memories:write"],
        description="Permission scopes for this key"
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiration (None = never)"
    )


class APIKeyResponse(BaseModel):
    """Response after creating an API key."""
    
    id: UUID = Field(..., description="API key UUID")
    key: str = Field(
        ...,
        description="The API key (only shown once!)"
    )
    key_prefix: str = Field(
        ...,
        description="Key prefix for identification"
    )
    name: str = Field(..., description="Key name")
    scopes: list[str] = Field(..., description="Granted scopes")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(
        None,
        description="Expiration timestamp"
    )


class APIKeyInfo(BaseModel):
    """API key information (without the secret)."""
    
    id: UUID
    key_prefix: str
    name: str
    scopes: list[str]
    status: str
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]


class LoginRequest(BaseModel):
    """User login request."""
    
    email: EmailStr
    password: str = Field(..., min_length=8)


class RefreshRequest(BaseModel):
    """Token refresh request."""
    
    refresh_token: str
