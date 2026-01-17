"""
Knowwhere Memory MCP Server

Main entry point for the FastMCP server with authentication,
rate limiting, and audit logging.
"""

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import structlog
import uvicorn
from fastmcp import FastMCP

from src.config import Settings, get_settings
from src.storage.database import close_database, get_database
from src.storage.cache import close_cache, get_cache
from src.auth.middleware import AuthContext, get_current_user
from src.auth.jwt import verify_token
from src.auth.api_keys import verify_api_key
from src.middleware.rate_limit import check_rate_limit, get_rate_limiter
from src.middleware.audit import AuditContext, close_audit_logger, get_audit_logger
from src.tools.remember import remember, REMEMBER_SPEC
from src.tools.recall import recall, RECALL_SPEC
from src.tools.consolidate import consolidate_session, CONSOLIDATE_SESSION_SPEC
from src.tools.analyze import analyze_evolution, ANALYZE_EVOLUTION_SPEC
from src.tools.export import export_memories, EXPORT_MEMORIES_SPEC
from src.tools.delete import delete_memory, DELETE_MEMORY_SPEC

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Get settings
settings = get_settings()

# Create FastMCP app
mcp = FastMCP(
    "Knowwhere Memory Server",
    version="1.0.0",
    description="Persistent, intelligent memory layer for AI agents",
)


# =============================================================================
# Lifecycle Management
# =============================================================================

@asynccontextmanager
async def lifespan():
    """Manage server lifecycle - connect/disconnect resources."""
    logger.info("Starting Knowwhere Memory MCP Server...")
    
    # Initialize connections
    try:
        db = await get_database()
        logger.info("Database connected")
        
        cache = await get_cache()
        if cache.is_connected:
            logger.info("Redis cache connected")
        else:
            logger.warning("Redis cache not available - continuing without cache")
        
        # Start audit logger
        audit_logger = await get_audit_logger()
        logger.info("Audit logger started")
        
        # Initialize rate limiter
        rate_limiter = await get_rate_limiter()
        logger.info("Rate limiter initialized")
        
    except Exception as e:
        logger.error("Failed to initialize connections", error=str(e))
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down Knowwhere Memory MCP Server...")
    await close_audit_logger()
    await close_database()
    await close_cache()
    logger.info("Shutdown complete")


# =============================================================================
# Authentication & Rate Limiting
# =============================================================================

async def authenticate_request(
    bearer_token: str | None = None,
    api_key: str | None = None,
) -> UUID | None:
    """
    Authenticate a request and return user_id.
    
    Tries bearer token first, then API key.
    Returns None if authentication fails.
    """
    # Try bearer token
    if bearer_token:
        if bearer_token.startswith("Bearer "):
            bearer_token = bearer_token[7:]
        
        token_data = verify_token(bearer_token, token_type="access")
        if token_data:
            user_id = UUID(token_data.sub)
            AuthContext.set_user_from_token(token_data)
            return user_id
    
    # Try API key
    if api_key:
        user_info = await verify_api_key(api_key)
        if user_info:
            user_id = user_info["user_id"]
            AuthContext.set_user_from_api_key(user_info)
            return user_id
    
    return None


async def check_rate_limit_for_user(user_id: UUID) -> tuple[bool, dict]:
    """Check if user is within rate limits."""
    return await check_rate_limit(str(user_id))


# =============================================================================
# MCP Context Extraction
# =============================================================================

# For development/testing - allows unauthenticated access
# In production, set REQUIRE_AUTH=true in environment
REQUIRE_AUTH = settings.debug is False
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_user_id_from_context(
    context: dict | None = None,
    metadata: dict | None = None,
) -> UUID:
    """
    Extract user_id from MCP context or metadata.
    
    Priority:
    1. AuthContext (set by authenticated request)
    2. Metadata user_id
    3. Context user_id
    4. Default (development only)
    """
    # Check AuthContext first (set by auth middleware)
    auth_user_id = AuthContext.get_user_id()
    if auth_user_id:
        return auth_user_id
    
    # Check metadata
    if metadata and "user_id" in metadata:
        return UUID(metadata["user_id"])
    
    # Check context
    if context and "user_id" in context:
        return UUID(context["user_id"])
    
    # Fall back to default (development only)
    if not REQUIRE_AUTH:
        logger.warning("Using default user_id - NOT FOR PRODUCTION")
        return DEFAULT_USER_ID
    
    raise ValueError("Authentication required: no user_id found in context")


async def with_auth_and_audit(
    tool_name: str,
    user_id: UUID,
    operation_func,
    **kwargs,
) -> dict[str, Any]:
    """
    Wrapper that handles rate limiting and audit logging for tool calls.
    """
    # Check rate limit
    is_allowed, rate_info = await check_rate_limit_for_user(user_id)
    
    if not is_allowed:
        logger.warning(
            "Rate limit exceeded",
            user_id=str(user_id),
            tool=tool_name,
        )
        return {
            "error": "Rate limit exceeded",
            "retry_after_seconds": rate_info.get("reset_at", 60) - int(time.time()),
            "limit": rate_info.get("limit"),
        }
    
    # Execute with audit logging
    async with AuditContext(user_id, f"tool:{tool_name}") as ctx:
        try:
            result = await operation_func(user_id=user_id, **kwargs)
            
            # Track accessed memory IDs if present in result
            if hasattr(result, "memory_id"):
                ctx.add_memory_id(result.memory_id)
            elif hasattr(result, "memories"):
                for mem in result.memories[:10]:  # Limit to first 10
                    if hasattr(mem, "id"):
                        ctx.add_memory_id(mem.id)
            
            return result.model_dump(mode="json")
            
        except Exception as e:
            ctx.set_error(str(e))
            raise


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def mcp_remember(
    content: str,
    memory_type: str,
    entities: list[str] | None = None,
    importance: int = 5,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Store a new memory in Knowwhere.
    
    Use this to remember facts, preferences, learnings, or procedures about the user.
    
    Args:
        content: The memory content (what to remember)
        memory_type: Type of memory (episodic, semantic, preference, procedural, meta)
        entities: Related entities/concepts (auto-extracted if not provided)
        importance: Importance level 1-10 (default: 5)
        metadata: Additional custom metadata
    """
    user_id = get_user_id_from_context(metadata=metadata)
    
    return await with_auth_and_audit(
        tool_name="remember",
        user_id=user_id,
        operation_func=remember,
        content=content,
        memory_type=memory_type,
        entities=entities,
        importance=importance,
        metadata=metadata,
    )


@mcp.tool()
async def mcp_recall(
    query: str,
    filters: dict | None = None,
    limit: int = 10,
    _metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Search and retrieve memories using semantic similarity.
    
    Use this to find relevant context about the user.
    
    Args:
        query: Search query (natural language)
        filters: Optional filters (memory_type, entity, date_range, importance_min)
        limit: Maximum number of results (1-50)
    """
    user_id = get_user_id_from_context(metadata=_metadata)
    
    return await with_auth_and_audit(
        tool_name="recall",
        user_id=user_id,
        operation_func=recall,
        query=query,
        filters=filters,
        limit=limit,
    )


@mcp.tool()
async def mcp_consolidate_session(
    session_transcript: str,
    session_date: str | None = None,
    conversation_id: str | None = None,
    _metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Process a conversation transcript and extract structured memories.
    
    This analyzes the conversation to find facts, preferences, and learnings,
    then stores them as memories.
    
    Args:
        session_transcript: Full conversation transcript to process
        session_date: When the session occurred (ISO 8601 format)
        conversation_id: Reference ID for the conversation
    """
    from datetime import datetime
    
    user_id = get_user_id_from_context(metadata=_metadata)
    
    # Parse session_date if provided
    parsed_date = None
    if session_date:
        try:
            parsed_date = datetime.fromisoformat(session_date)
        except ValueError:
            pass
    
    return await with_auth_and_audit(
        tool_name="consolidate_session",
        user_id=user_id,
        operation_func=consolidate_session,
        session_transcript=session_transcript,
        session_date=parsed_date,
        conversation_id=conversation_id,
    )


@mcp.tool()
async def mcp_analyze_evolution(
    entity_id: str | None = None,
    entity_name: str | None = None,
    time_window: str = "all_time",
    _metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Track how an entity, preference, or concept evolved over time.
    
    Use this to understand how the user's preferences or knowledge changed.
    
    Args:
        entity_id: UUID of a specific memory to track
        entity_name: Name of an entity to track (e.g., 'TypeScript', 'async/await')
        time_window: Time window for analysis (last_7_days, last_30_days, last_year, all_time)
    """
    user_id = get_user_id_from_context(metadata=_metadata)
    
    parsed_entity_id = None
    if entity_id:
        try:
            parsed_entity_id = UUID(entity_id)
        except ValueError:
            pass
    
    return await with_auth_and_audit(
        tool_name="analyze_evolution",
        user_id=user_id,
        operation_func=analyze_evolution,
        entity_id=parsed_entity_id,
        entity_name=entity_name,
        time_window=time_window,
    )


@mcp.tool()
async def mcp_export_memories(
    format: str = "json",
    filters: dict | None = None,
    include_embeddings: bool = False,
    _metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Export user memories for backup or analysis.
    
    Supports JSON and CSV formats.
    
    Args:
        format: Export format ('json' or 'csv')
        filters: Optional filters (memory_type)
        include_embeddings: Include vector embeddings (warning: large data size)
    """
    user_id = get_user_id_from_context(metadata=_metadata)
    
    return await with_auth_and_audit(
        tool_name="export_memories",
        user_id=user_id,
        operation_func=export_memories,
        format=format,
        filters=filters,
        include_embeddings=include_embeddings,
    )


@mcp.tool()
async def mcp_delete_memory(
    memory_id: str,
    hard_delete: bool = False,
    _metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Delete a specific memory.
    
    Performs soft-delete by default (GDPR-compliant with grace period).
    Use hard_delete for immediate permanent deletion.
    
    Args:
        memory_id: ID of the memory to delete
        hard_delete: Whether to permanently delete (vs soft-delete)
    """
    user_id = get_user_id_from_context(metadata=_metadata)
    
    return await with_auth_and_audit(
        tool_name="delete_memory",
        user_id=user_id,
        operation_func=delete_memory,
        memory_id=UUID(memory_id),
        hard_delete=hard_delete,
    )


# =============================================================================
# Health Check Endpoint
# =============================================================================

@mcp.resource("health://status")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    try:
        db = await get_database()
        db_healthy = await db.health_check()
    except Exception:
        db_healthy = False
    
    try:
        cache = await get_cache()
        cache_healthy = await cache.health_check()
    except Exception:
        cache_healthy = False
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "cache": "connected" if cache_healthy else "disconnected",
        "version": "1.0.0",
        "auth_required": REQUIRE_AUTH,
        "rate_limit_enabled": settings.rate_limit_enabled,
    }


# =============================================================================
# Entry Points
# =============================================================================

def main():
    """Main entry point for CLI."""
    logger.info(
        "Knowwhere Memory MCP Server starting",
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        auth_required=REQUIRE_AUTH,
    )
    
    # Run the MCP server
    mcp.run()


async def run_server():
    """Run the server programmatically."""
    async with lifespan():
        await mcp.run_async()


if __name__ == "__main__":
    main()
