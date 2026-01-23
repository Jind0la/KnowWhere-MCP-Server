"""
JWT Token Handling

Implements JWT token creation and validation using RS256 or HS256.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import structlog
from jose import JWTError, jwt
from pydantic import ValidationError

from src.auth.models import TokenData
from src.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class JWTHandler:
    """
    JWT Token Handler.
    
    Supports both HS256 (symmetric) and RS256 (asymmetric) algorithms.
    Uses HS256 by default for simplicity, configurable via settings.
    """
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._algorithm = self.settings.jwt_algorithm
        self._secret_key = self._get_secret_key()
        self._access_token_expire_hours = self.settings.jwt_expiration_hours
        self._refresh_token_expire_days = 30
    
    def _get_secret_key(self) -> str:
        """Get the secret key for JWT signing."""
        if self.settings.jwt_secret_key:
            return self.settings.jwt_secret_key.get_secret_value()
        # Fallback to a generated key (not recommended for production)
        logger.warning("JWT_SECRET_KEY not set, using fallback (NOT FOR PRODUCTION)")
        return "fallback-secret-key-change-in-production"
    
    def create_access_token(
        self,
        user_id: str,
        email: str | None = None,
        tier: str = "free",
        scopes: list[str] | None = None,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            user_id: User UUID as string
            email: User email
            tier: Subscription tier
            scopes: Permission scopes
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=self._access_token_expire_hours)
        
        now = datetime.utcnow()
        expire = now + expires_delta
        
        # Default scopes based on tier
        if scopes is None:
            scopes = self._get_default_scopes(tier)
        
        payload = {
            "sub": user_id,
            "email": email,
            "tier": tier,
            "scopes": scopes,
            "iat": now,
            "exp": expire,
            "jti": str(uuid4()),  # Unique token ID for revocation
            "type": "access",
        }
        
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        
        logger.debug(
            "Access token created",
            user_id=user_id,
            expires_at=expire.isoformat(),
        )
        
        return token
    
    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        Create a JWT refresh token.
        
        Refresh tokens have longer expiry and limited payload.
        
        Args:
            user_id: User UUID as string
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT refresh token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self._refresh_token_expire_days)
        
        now = datetime.utcnow()
        expire = now + expires_delta
        
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expire,
            "jti": str(uuid4()),
            "type": "refresh",
        }
        
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        
        logger.debug(
            "Refresh token created",
            user_id=user_id,
            expires_at=expire.isoformat(),
        )
        
        return token
    
    def verify_token(self, token: str, token_type: str = "access") -> TokenData | None:
        """
        Verify and decode a JWT token.
        
        Args:
            token: The JWT token to verify
            token_type: Expected token type (access, refresh)
            
        Returns:
            TokenData if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm, "HS256", "RS256"], # Allow common algs to prevent noise
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(
                    "Token type mismatch",
                    expected=token_type,
                    got=payload.get("type"),
                )
                return None
            
            # Extract data
            token_data = TokenData(
                sub=payload.get("sub"),
                email=payload.get("email"),
                tier=payload.get("tier"),
                scopes=payload.get("scopes", []),
                exp=datetime.fromtimestamp(payload.get("exp", 0)),
                iat=datetime.fromtimestamp(payload.get("iat", 0)),
                jti=payload.get("jti"),
            )
            
            return token_data
            
        except JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            return None
        except ValidationError as e:
            logger.warning("Token data validation failed", error=str(e))
            return None
    
    def _get_default_scopes(self, tier: str) -> list[str]:
        """Get default scopes based on subscription tier."""
        base_scopes = ["memories:read", "memories:write"]
        
        if tier == "free":
            return base_scopes
        
        if tier == "pro":
            return base_scopes + [
                "memories:delete",
                "consolidate:execute",
                "export:execute",
            ]
        
        if tier == "enterprise":
            return base_scopes + [
                "memories:delete",
                "consolidate:execute",
                "export:execute",
                "admin:manage",
            ]
        
        return base_scopes


# Global JWT handler instance
_jwt_handler: JWTHandler | None = None


def get_jwt_handler() -> JWTHandler:
    """Get or create the global JWT handler."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    return _jwt_handler


# Convenience functions
def create_access_token(
    user_id: str,
    email: str | None = None,
    tier: str = "free",
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    return get_jwt_handler().create_access_token(
        user_id=user_id,
        email=email,
        tier=tier,
        scopes=scopes,
        expires_delta=expires_delta,
    )


def create_refresh_token(
    user_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token."""
    return get_jwt_handler().create_refresh_token(
        user_id=user_id,
        expires_delta=expires_delta,
    )


def verify_token(token: str, token_type: str = "access") -> TokenData | None:
    """Verify and decode a JWT token."""
    return get_jwt_handler().verify_token(token, token_type)
