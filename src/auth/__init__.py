"""
Authentication Module

Provides OAuth 2.1 JWT authentication and API Key validation.
"""

from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    TokenData,
)
from src.auth.api_keys import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
)
from src.auth.middleware import (
    get_current_user,
    get_current_user_optional,
    require_auth,
)
from src.auth.models import (
    AuthUser,
    TokenResponse,
    APIKeyCreate,
    APIKeyResponse,
)

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "TokenData",
    # API Keys
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    # Middleware
    "get_current_user",
    "get_current_user_optional",
    "require_auth",
    # Models
    "AuthUser",
    "TokenResponse",
    "APIKeyCreate",
    "APIKeyResponse",
]
