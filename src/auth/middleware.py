"""
Authentication Middleware

FastAPI dependencies for authentication and authorization.
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from src.auth.api_keys import verify_api_key as verify_api_key_func
from src.auth.jwt import verify_token
from src.auth.models import AuthUser

logger = structlog.get_logger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    request: Request,
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_header),
) -> AuthUser:
    """
    Get the current authenticated user.
    
    Supports both:
    - Bearer token (JWT) in Authorization header
    - API Key in X-API-Key header
    
    Raises HTTPException 401 if not authenticated.
    """
    # Try Bearer token first
    if bearer_credentials:
        token = bearer_credentials.credentials
        token_data = verify_token(token, token_type="access")
        
        if token_data:
            return AuthUser(
                id=UUID(token_data.sub),
                email=token_data.email or "",
                tier=token_data.tier or "free",
                scopes=token_data.scopes,
                auth_method="jwt",
            )
    
    # Try API Key
    if api_key:
        user_info = await verify_api_key_func(api_key)
        
        if user_info:
            return AuthUser(
                id=user_info["user_id"],
                email=user_info["email"],
                tier=user_info["tier"],
                scopes=user_info["scopes"],
                auth_method="api_key",
            )
    
    # No valid authentication found
    logger.warning(
        "Authentication failed",
        has_bearer=bearer_credentials is not None,
        has_api_key=api_key is not None,
    )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    request: Request,
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_header),
) -> AuthUser | None:
    """
    Get the current user if authenticated, None otherwise.
    
    Does not raise exception if not authenticated.
    """
    try:
        return await get_current_user(request, bearer_credentials, api_key)
    except HTTPException:
        return None


def require_scope(required_scope: str):
    """
    Dependency factory for requiring a specific scope.
    
    Usage:
        @app.post("/memories")
        async def create_memory(
            user: AuthUser = Depends(require_scope("memories:write"))
        ):
            ...
    """
    async def scope_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not user.has_scope(required_scope):
            logger.warning(
                "Scope check failed",
                user_id=str(user.id),
                required_scope=required_scope,
                user_scopes=user.scopes,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope}' required",
            )
        return user
    
    return scope_checker


def require_tier(min_tier: str):
    """
    Dependency factory for requiring a minimum subscription tier.
    
    Tier hierarchy: free < pro < enterprise
    
    Usage:
        @app.post("/consolidate")
        async def consolidate(
            user: AuthUser = Depends(require_tier("pro"))
        ):
            ...
    """
    tier_levels = {"free": 0, "pro": 1, "enterprise": 2}
    min_level = tier_levels.get(min_tier, 0)
    
    async def tier_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        user_level = tier_levels.get(user.tier, 0)
        
        if user_level < min_level:
            logger.warning(
                "Tier check failed",
                user_id=str(user.id),
                required_tier=min_tier,
                user_tier=user.tier,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Subscription tier '{min_tier}' or higher required",
            )
        return user
    
    return tier_checker


# Convenience dependency for requiring any authentication
require_auth = Depends(get_current_user)


class AuthContext:
    """
    Context manager for accessing auth info in MCP tools.
    
    Since MCP tools don't have FastAPI request context,
    this provides an alternative way to pass auth info.
    """
    
    _current_user: AuthUser | None = None
    
    @classmethod
    def set_user(cls, user: AuthUser | None) -> None:
        """Set the current user context."""
        cls._current_user = user
    
    @classmethod
    def set_user_from_token(cls, token_data) -> None:
        """Set user context from JWT token data."""
        from src.auth.models import TokenData
        
        if token_data:
            cls._current_user = AuthUser(
                id=UUID(token_data.sub),
                email=token_data.email or "",
                tier=token_data.tier or "free",
                scopes=token_data.scopes,
                auth_method="jwt",
            )
    
    @classmethod
    def set_user_from_api_key(cls, user_info: dict) -> None:
        """Set user context from API key validation result."""
        if user_info:
            cls._current_user = AuthUser(
                id=user_info["user_id"],
                email=user_info.get("email", ""),
                tier=user_info.get("tier", "free"),
                scopes=user_info.get("scopes", []),
                auth_method="api_key",
            )
    
    @classmethod
    def get_user(cls) -> AuthUser | None:
        """Get the current user context."""
        return cls._current_user
    
    @classmethod
    def get_user_id(cls) -> UUID | None:
        """Get the current user ID."""
        if cls._current_user:
            return cls._current_user.id
        return None
    
    @classmethod
    def require_user(cls) -> AuthUser:
        """Get current user or raise exception."""
        if cls._current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return cls._current_user
    
    @classmethod
    def clear(cls) -> None:
        """Clear the user context."""
        cls._current_user = None
