"""
User Repository

Data access layer for User entities.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from src.models.user import AuthProvider, User, UserCreate, UserStatus, UserTier, UserUpdate
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class UserRepository:
    """
    Repository for User CRUD operations.
    
    Provides:
    - User creation and management
    - Authentication lookups
    - Quota tracking
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create(self, user: UserCreate, user_id: UUID | None = None) -> User:
        """Create a new user."""
        fields = [
            "email", "username", "full_name", "avatar_url", "bio",
            "auth_provider", "password_hash"
        ]
        values = [
            user.email, user.username, user.full_name, user.avatar_url, user.bio,
            user.auth_provider.value, user.password_hash
        ]
        
        if user_id:
            fields.append("id")
            values.append(user_id)
            
        param_placeholders = ", ".join([f"${i+1}" for i in range(len(fields))])
        
        query = f"""
            INSERT INTO users ({", ".join(fields)})
            VALUES ({param_placeholders})
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, *values)
        
        logger.info("User created", user_id=row["id"], email=user.email)
        return self._row_to_user(row)
    
    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        query = "SELECT * FROM users WHERE id = $1 AND status != 'deleted'"
        row = await self.db.fetchrow(query, user_id)
        return self._row_to_user(row) if row else None
    
    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        query = "SELECT * FROM users WHERE email = $1 AND status != 'deleted'"
        row = await self.db.fetchrow(query, email)
        return self._row_to_user(row) if row else None
    
    async def get_by_username(self, username: str) -> User | None:
        """Get a user by username."""
        query = "SELECT * FROM users WHERE username = $1 AND status != 'deleted'"
        row = await self.db.fetchrow(query, username)
        return self._row_to_user(row) if row else None
    
    async def exists_by_email(self, email: str) -> bool:
        """Check if a user exists with this email."""
        query = "SELECT EXISTS(SELECT 1 FROM users WHERE email = $1)"
        return await self.db.fetchval(query, email)
    
    async def update(self, user_id: UUID, update_data: UserUpdate) -> User | None:
        """Update a user."""
        updates = []
        params: list[Any] = []
        param_idx = 1
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not updates:
            return await self.get_by_id(user_id)
        
        params.append(user_id)
        
        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, *params)
        return self._row_to_user(row) if row else None
    
    async def update_last_login(self, user_id: UUID) -> None:
        """Update last login timestamp."""
        query = "UPDATE users SET last_login_at = NOW() WHERE id = $1"
        await self.db.execute(query, user_id)
    
    async def verify_email(self, user_id: UUID) -> bool:
        """Mark user email as verified."""
        query = """
            UPDATE users 
            SET email_verified = TRUE, verified_at = NOW()
            WHERE id = $1
            RETURNING id
        """
        result = await self.db.fetchval(query, user_id)
        return result is not None
    
    async def update_tier(self, user_id: UUID, tier: UserTier) -> bool:
        """Update user subscription tier."""
        # Set quotas based on tier
        quotas = {
            UserTier.FREE: (100000, 1073741824),  # 100k requests, 1GB
            UserTier.PRO: (1000000, 10737418240),  # 1M requests, 10GB
            UserTier.ENTERPRISE: (10000000, 107374182400),  # 10M requests, 100GB
        }
        
        requests, storage = quotas.get(tier, quotas[UserTier.FREE])
        
        query = """
            UPDATE users 
            SET tier = $2, monthly_quota_requests = $3, monthly_quota_storage_bytes = $4
            WHERE id = $1
            RETURNING id
        """
        result = await self.db.fetchval(query, user_id, tier.value, requests, storage)
        return result is not None
    
    async def suspend(self, user_id: UUID, reason: str) -> bool:
        """Suspend a user account."""
        query = """
            UPDATE users 
            SET status = 'suspended', suspended_at = NOW(), suspension_reason = $2
            WHERE id = $1 AND status = 'active'
            RETURNING id
        """
        result = await self.db.fetchval(query, user_id, reason)
        if result:
            logger.warning("User suspended", user_id=user_id, reason=reason)
        return result is not None
    
    async def reactivate(self, user_id: UUID) -> bool:
        """Reactivate a suspended user."""
        query = """
            UPDATE users 
            SET status = 'active', suspended_at = NULL, suspension_reason = NULL
            WHERE id = $1 AND status = 'suspended'
            RETURNING id
        """
        result = await self.db.fetchval(query, user_id)
        return result is not None
    
    async def soft_delete(self, user_id: UUID) -> bool:
        """Soft delete a user (GDPR-compliant)."""
        query = """
            UPDATE users 
            SET status = 'deleted', deleted_at = NOW()
            WHERE id = $1 AND status != 'deleted'
            RETURNING id
        """
        result = await self.db.fetchval(query, user_id)
        if result:
            logger.info("User soft-deleted", user_id=user_id)
        return result is not None
    
    async def hard_delete(self, user_id: UUID) -> bool:
        """
        Permanently delete a user and all their data.
        
        WARNING: This cascades to memories, edges, etc.
        """
        query = "DELETE FROM users WHERE id = $1 RETURNING id"
        result = await self.db.fetchval(query, user_id)
        if result:
            logger.warning("User hard-deleted", user_id=user_id)
        return result is not None
    
    async def get_quota_usage(self, user_id: UUID) -> dict[str, Any]:
        """Get user's current quota usage."""
        # Get user quotas
        user = await self.get_by_id(user_id)
        if not user:
            return {}
        
        # Count memories
        memory_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM memories WHERE user_id = $1 AND status = 'active'",
            user_id
        )
        
        # Estimate storage (rough estimate: content length)
        storage_used = await self.db.fetchval(
            "SELECT COALESCE(SUM(LENGTH(content)), 0) FROM memories WHERE user_id = $1 AND status = 'active'",
            user_id
        )
        
        return {
            "user_id": str(user_id),
            "tier": user.tier.value,
            "requests_limit": user.monthly_quota_requests,
            "storage_limit_bytes": user.monthly_quota_storage_bytes,
            "memories_count": memory_count or 0,
            "storage_used_bytes": storage_used or 0,
        }
    
    def _row_to_user(self, row: Any) -> User:
        """Convert database row to User model."""
        import json
        
        # Handle JSONB fields that might come as strings
        settings = row["settings"] or {}
        metadata = row["metadata"] or {}
        
        if isinstance(settings, str):
            settings = json.loads(settings) if settings else {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        
        return User(
            id=row["id"],
            email=row["email"],
            email_verified=row["email_verified"],
            verified_at=row["verified_at"],
            auth_provider=AuthProvider(row["auth_provider"]) if row["auth_provider"] else AuthProvider.EMAIL,
            username=row["username"],
            full_name=row["full_name"],
            avatar_url=row["avatar_url"],
            bio=row["bio"],
            tier=UserTier(row["tier"]) if row["tier"] else UserTier.FREE,
            stripe_customer_id=row["stripe_customer_id"],
            stripe_subscription_id=row["stripe_subscription_id"],
            monthly_quota_requests=row["monthly_quota_requests"],
            monthly_quota_storage_bytes=row["monthly_quota_storage_bytes"],
            status=UserStatus(row["status"]) if row["status"] else UserStatus.ACTIVE,
            suspended_at=row["suspended_at"],
            suspension_reason=row["suspension_reason"],
            settings=settings,
            metadata=metadata,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
            last_login_at=row["last_login_at"],
        )
