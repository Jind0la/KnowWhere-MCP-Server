"""
User Model

Represents users of the Knowwhere system.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class UserTier(str, Enum):
    """Subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AuthProvider(str, Enum):
    """Authentication provider."""
    OAUTH = "oauth"
    EMAIL = "email"
    API_KEY = "api_key"


class UserBase(BaseModel):
    """Base user fields."""
    
    email: EmailStr = Field(..., description="User email address")
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Unique username"
    )
    full_name: str | None = Field(
        default=None,
        max_length=255,
        description="Full name"
    )
    avatar_url: str | None = Field(
        default=None,
        max_length=500,
        description="Avatar image URL"
    )
    bio: str | None = Field(
        default=None,
        max_length=1000,
        description="User bio"
    )


class UserCreate(UserBase):
    """Schema for creating a user."""
    
    auth_provider: AuthProvider = Field(
        default=AuthProvider.EMAIL,
        description="Authentication method"
    )
    password_hash: str | None = Field(
        default=None,
        description="Hashed password (for email auth)"
    )


class User(UserBase):
    """
    Full user entity.
    
    Includes subscription info, quotas, and account status.
    """
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    
    # Authentication
    email_verified: bool = Field(
        default=False,
        description="Whether email is verified"
    )
    verified_at: datetime | None = Field(
        default=None,
        description="Email verification timestamp"
    )
    auth_provider: AuthProvider = Field(
        default=AuthProvider.EMAIL,
        description="Authentication method"
    )
    
    # Subscription
    tier: UserTier = Field(
        default=UserTier.FREE,
        description="Subscription tier"
    )
    stripe_customer_id: str | None = Field(
        default=None,
        description="Stripe customer ID"
    )
    stripe_subscription_id: str | None = Field(
        default=None,
        description="Stripe subscription ID"
    )
    
    # Quotas
    monthly_quota_requests: int = Field(
        default=100000,
        description="Monthly API request quota"
    )
    monthly_quota_storage_bytes: int = Field(
        default=1073741824,  # 1GB
        description="Monthly storage quota in bytes"
    )
    
    # Status
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        description="Account status"
    )
    suspended_at: datetime | None = Field(
        default=None,
        description="Suspension timestamp"
    )
    suspension_reason: str | None = Field(
        default=None,
        description="Reason for suspension"
    )
    
    # Settings & Metadata
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences and settings"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    deleted_at: datetime | None = Field(
        default=None,
        description="Soft delete timestamp"
    )
    last_login_at: datetime | None = Field(
        default=None,
        description="Last login timestamp"
    )

    model_config = {"from_attributes": True}

    def is_active(self) -> bool:
        """Check if user account is active."""
        return self.status == UserStatus.ACTIVE

    def is_premium(self) -> bool:
        """Check if user has premium tier."""
        return self.tier in (UserTier.PRO, UserTier.ENTERPRISE)

    def can_access_feature(self, feature: str) -> bool:
        """Check if user can access a specific feature."""
        # Free tier features
        free_features = {"remember", "recall", "delete_memory"}
        
        # Pro tier features
        pro_features = free_features | {"consolidate_session", "export_memories"}
        
        # Enterprise features
        enterprise_features = pro_features | {"analyze_evolution", "team_management"}
        
        if self.tier == UserTier.FREE:
            return feature in free_features
        elif self.tier == UserTier.PRO:
            return feature in pro_features
        else:  # Enterprise
            return feature in enterprise_features


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    username: str | None = Field(default=None, min_length=3, max_length=100)
    full_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=1000)
    settings: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class UserQuotaUsage(BaseModel):
    """User quota usage statistics."""
    
    user_id: UUID
    period_start: datetime
    period_end: datetime
    requests_used: int = 0
    requests_limit: int
    storage_used_bytes: int = 0
    storage_limit_bytes: int
    memories_count: int = 0
    
    @property
    def requests_remaining(self) -> int:
        """Calculate remaining requests."""
        return max(0, self.requests_limit - self.requests_used)
    
    @property
    def storage_remaining_bytes(self) -> int:
        """Calculate remaining storage."""
        return max(0, self.storage_limit_bytes - self.storage_used_bytes)
    
    @property
    def requests_usage_percent(self) -> float:
        """Calculate request usage percentage."""
        if self.requests_limit == 0:
            return 100.0
        return (self.requests_used / self.requests_limit) * 100
