"""
API Key Management

Handles API key generation, hashing, and validation.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog

from src.config import Settings, get_settings
from src.storage.database import Database, get_database

logger = structlog.get_logger(__name__)


class APIKeyManager:
    """
    Manages API keys for server-to-server authentication.
    
    API keys are:
    - Prefixed for easy identification (e.g., kw_prod_xxx)
    - Hashed with SHA-256 before storage
    - Scoped with specific permissions
    """
    
    def __init__(self, settings: Settings | None = None, db: Database | None = None):
        self.settings = settings or get_settings()
        self._db = db
        self._prefix = self.settings.api_key_prefix
    
    async def _get_db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    def generate_api_key(self) -> tuple[str, str]:
        """
        Generate a new API key.
        
        Returns:
            Tuple of (full_key, key_hash)
            - full_key: The complete API key to give to user (only shown once)
            - key_hash: SHA-256 hash of the key for storage
        """
        # Generate random secret (32 bytes = 256 bits)
        secret = secrets.token_urlsafe(32)
        
        # Create full key with prefix
        full_key = f"{self._prefix}_{secret}"
        
        # Hash for storage
        key_hash = self.hash_api_key(full_key)
        
        return full_key, key_hash
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key for secure storage.
        
        Uses SHA-256 for consistent, fast hashing.
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def get_key_prefix(api_key: str) -> str:
        """Extract the prefix from an API key for identification."""
        parts = api_key.split("_")
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1][:8]}"
        return api_key[:12]
    
    async def create_api_key(
        self,
        user_id: UUID,
        name: str,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> dict:
        """
        Create and store a new API key.
        
        Args:
            user_id: Owner user ID
            name: Human-readable name for the key
            scopes: Permission scopes
            expires_in_days: Days until expiration (None = never)
            
        Returns:
            Dict with key info including the actual key (only time it's shown)
        """
        # Generate key
        full_key, key_hash = self.generate_api_key()
        key_prefix = self.get_key_prefix(full_key)
        
        # Default scopes
        if scopes is None:
            scopes = ["memories:read", "memories:write"]
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Store in database
        db = await self._get_db()
        
        query = """
            INSERT INTO api_keys (
                user_id, key_prefix, key_hash, scopes, name, expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, created_at
        """
        
        row = await db.fetchrow(
            query,
            user_id,
            key_prefix,
            key_hash,
            scopes,
            name,
            expires_at,
        )
        
        logger.info(
            "API key created",
            key_id=str(row["id"]),
            user_id=str(user_id),
            key_prefix=key_prefix,
        )
        
        return {
            "id": row["id"],
            "key": full_key,  # Only shown once!
            "key_prefix": key_prefix,
            "name": name,
            "scopes": scopes,
            "created_at": row["created_at"],
            "expires_at": expires_at,
        }
    
    async def verify_api_key(self, api_key: str) -> dict | None:
        """
        Verify an API key and return user info.
        
        Args:
            api_key: The full API key
            
        Returns:
            Dict with user_id and scopes if valid, None otherwise
        """
        key_hash = self.hash_api_key(api_key)
        
        db = await self._get_db()
        
        query = """
            SELECT 
                ak.id, ak.user_id, ak.scopes, ak.status, ak.expires_at,
                u.email, u.tier
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.key_hash = $1 AND ak.status = 'active'
        """
        
        row = await db.fetchrow(query, key_hash)
        
        if not row:
            logger.warning("API key not found or inactive")
            return None
        
        # Check expiration
        if row["expires_at"] and row["expires_at"] < datetime.utcnow():
            logger.warning("API key expired", key_id=str(row["id"]))
            return None
        
        # Update last used
        await self._update_last_used(row["id"])
        
        logger.debug("API key verified", key_id=str(row["id"]))
        
        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "tier": row["tier"],
            "scopes": row["scopes"],
            "key_id": row["id"],
        }
    
    async def _update_last_used(self, key_id: UUID) -> None:
        """Update the last_used_at timestamp for a key."""
        db = await self._get_db()
        
        query = "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1"
        await db.execute(query, key_id)
    
    async def revoke_api_key(self, key_id: UUID, user_id: UUID) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: The key ID to revoke
            user_id: Owner user ID (for authorization)
            
        Returns:
            True if revoked, False if not found
        """
        db = await self._get_db()
        
        query = """
            UPDATE api_keys 
            SET status = 'revoked', revoked_at = NOW()
            WHERE id = $1 AND user_id = $2 AND status = 'active'
            RETURNING id
        """
        
        result = await db.fetchval(query, key_id, user_id)
        
        if result:
            logger.info("API key revoked", key_id=str(key_id))
            return True
        return False
    
    async def list_user_keys(self, user_id: UUID) -> list[dict]:
        """List all API keys for a user (without secrets)."""
        db = await self._get_db()
        
        query = """
            SELECT 
                id, key_prefix, name, scopes, status,
                last_used_at, created_at, expires_at
            FROM api_keys
            WHERE user_id = $1
            ORDER BY created_at DESC
        """
        
        rows = await db.fetch(query, user_id)
        
        return [
            {
                "id": row["id"],
                "key_prefix": row["key_prefix"],
                "name": row["name"],
                "scopes": row["scopes"],
                "status": row["status"],
                "last_used_at": row["last_used_at"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
            }
            for row in rows
        ]


# Global API key manager instance
_api_key_manager: APIKeyManager | None = None


async def get_api_key_manager() -> APIKeyManager:
    """Get or create the global API key manager."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# Convenience functions
def generate_api_key() -> tuple[str, str]:
    """Generate a new API key pair (key, hash)."""
    return APIKeyManager().generate_api_key()


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return APIKeyManager.hash_api_key(api_key)


async def verify_api_key(api_key: str) -> dict | None:
    """Verify an API key and return user info."""
    manager = await get_api_key_manager()
    return await manager.verify_api_key(api_key)


async def create_api_key(
    user_id: UUID,
    name: str,
    scopes: list[str] | None = None,
    expires_in_days: int | None = None,
) -> dict:
    """Create a new API key for a user."""
    manager = await get_api_key_manager()
    return await manager.create_api_key(user_id, name, scopes, expires_in_days)


async def list_user_api_keys(user_id: UUID) -> list[dict]:
    """List all API keys for a user."""
    manager = await get_api_key_manager()
    return await manager.list_user_keys(user_id)


async def revoke_api_key(key_id: UUID, user_id: UUID) -> bool:
    """Revoke an API key."""
    manager = await get_api_key_manager()
    return await manager.revoke_api_key(key_id, user_id)
