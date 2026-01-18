"""
Knowwhere Web API

FastAPI-based REST API for the web dashboard.
Provides endpoints for memories, stats, API keys, and user management.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import get_settings, init_container, close_container
from src.api.dependencies import get_current_user, CurrentUser
from src.storage.repositories.memory_repo import MemoryRepository
from src.storage.repositories.user_repo import UserRepository
from src.storage.repositories.edge_repo import EdgeRepository
from src.storage.database import get_database
from src.services.embedding import get_embedding_service
from src.models.memory import MemoryType, MemoryCreate, MemoryUpdate, MemoryStatus

logger = structlog.get_logger(__name__)
settings = get_settings()


# =============================================================================
# Request/Response Models
# =============================================================================

class MemoryCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    memory_type: str = Field(..., description="episodic, semantic, preference, procedural, meta")
    entities: list[str] = Field(default_factory=list)
    importance: int = Field(default=5, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    entities: list[str] | None = None
    importance: int | None = Field(default=None, ge=1, le=10)
    status: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=50)


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=lambda: ["memories:read", "memories:write"])
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


# =============================================================================
# Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage API lifecycle."""
    logger.info("Starting Knowwhere Web API...")
    await init_container()
    yield
    await close_container()
    logger.info("Web API shutdown complete")


# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="Knowwhere API",
    description="REST API for the Knowwhere Memory Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    os.getenv("FRONTEND_URL", ""),
]
origins = [o for o in origins if o]  # Remove empty strings

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import APIRouter
router = APIRouter(prefix="/api")


# =============================================================================
# Auth Endpoints
# =============================================================================

@router.get("/auth/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {
        "id": str(user.id),
        "email": user.email,
        "tier": user.tier,
        "full_name": user.full_name,
    }


# =============================================================================
# Memory Endpoints
# =============================================================================

@router.get("/memories")
async def list_memories(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    memory_type: str | None = Query(default=None),
    importance_min: int | None = Query(default=None, ge=1, le=10),
):
    """List user's memories with pagination and filtering."""
    db = await get_database()
    repo = MemoryRepository(db)

    # Get memories
    memories = await repo.list_by_user(user.id, limit=limit + 1, offset=offset)

    # Apply filters
    if memory_type:
        memories = [m for m in memories if m.memory_type.value == memory_type]
    if importance_min:
        memories = [m for m in memories if m.importance >= importance_min]

    # Check for more
    has_more = len(memories) > limit
    if has_more:
        memories = memories[:limit]

    # Get total count
    stats = await repo.get_memory_stats(user.id)

    return {
        "memories": [
            {
                "id": str(m.id),
                "content": m.content,
                "memory_type": m.memory_type.value,
                "entities": m.entities,
                "importance": m.importance,
                "confidence": m.confidence,
                "status": m.status.value,
                "source": m.source.value,
                "access_count": m.access_count,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
                "last_accessed": m.last_accessed.isoformat() if m.last_accessed else None,
            }
            for m in memories
        ],
        "total": stats["total_memories"],
        "has_more": has_more,
        "limit": limit,
        "offset": offset,
    }


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a specific memory by ID."""
    db = await get_database()
    repo = MemoryRepository(db)

    memory = await repo.get_by_id(memory_id)
    if not memory or memory.user_id != user.id:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Update access tracking
    await repo.update_access(memory_id)

    return {
        "id": str(memory.id),
        "content": memory.content,
        "memory_type": memory.memory_type.value,
        "entities": memory.entities,
        "importance": memory.importance,
        "confidence": memory.confidence,
        "status": memory.status.value,
        "source": memory.source.value,
        "source_id": memory.source_id,
        "access_count": memory.access_count + 1,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
        "last_accessed": datetime.utcnow().isoformat(),
        "metadata": memory.metadata,
    }


@router.post("/memories")
async def create_memory(
    data: MemoryCreateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new memory."""
    db = await get_database()
    repo = MemoryRepository(db)
    embedding_service = await get_embedding_service()

    # Generate embedding
    embedding = await embedding_service.embed(data.content)

    # Create memory
    memory_create = MemoryCreate(
        user_id=user.id,
        content=data.content,
        memory_type=MemoryType(data.memory_type),
        entities=data.entities,
        importance=data.importance,
        embedding=embedding,
        metadata=data.metadata,
    )

    memory = await repo.create(memory_create)

    return {
        "id": str(memory.id),
        "content": memory.content,
        "memory_type": memory.memory_type.value,
        "entities": memory.entities,
        "importance": memory.importance,
        "created_at": memory.created_at.isoformat(),
    }


@router.patch("/memories/{memory_id}")
async def update_memory(
    memory_id: UUID,
    data: MemoryUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Update a memory."""
    db = await get_database()
    repo = MemoryRepository(db)

    # Check ownership
    memory = await repo.get_by_id(memory_id)
    if not memory or memory.user_id != user.id:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Build update
    update_data = MemoryUpdate()
    if data.content is not None:
        update_data.content = data.content
    if data.memory_type is not None:
        update_data.memory_type = MemoryType(data.memory_type)
    if data.entities is not None:
        update_data.entities = data.entities
    if data.importance is not None:
        update_data.importance = data.importance
    if data.status is not None:
        update_data.status = MemoryStatus(data.status)

    # Update
    updated = await repo.update(memory_id, update_data)

    return {
        "id": str(updated.id),
        "content": updated.content,
        "memory_type": updated.memory_type.value,
        "entities": updated.entities,
        "importance": updated.importance,
        "status": updated.status.value,
        "updated_at": updated.updated_at.isoformat(),
    }


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    hard: bool = Query(default=False),
):
    """Delete a memory (soft or hard delete)."""
    db = await get_database()
    repo = MemoryRepository(db)

    # Check ownership
    memory = await repo.get_by_id(memory_id)
    if not memory or memory.user_id != user.id:
        raise HTTPException(status_code=404, detail="Memory not found")

    if hard:
        success = await repo.hard_delete(memory_id)
    else:
        success = await repo.soft_delete(memory_id)

    return {"success": success, "deleted_id": str(memory_id)}


@router.post("/memories/search")
async def search_memories(
    data: SearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Semantic search across memories."""
    db = await get_database()
    repo = MemoryRepository(db)
    embedding_service = await get_embedding_service()

    # Generate query embedding
    query_embedding = await embedding_service.embed(data.query)

    # Search
    memories = await repo.search_by_vector(
        user_id=user.id,
        embedding=query_embedding,
        limit=data.limit,
        memory_type=data.filters.get("memory_type"),
        min_importance=data.filters.get("importance_min"),
    )

    return {
        "memories": [
            {
                "id": str(m.id),
                "content": m.content,
                "memory_type": m.memory_type.value,
                "entities": m.entities,
                "importance": m.importance,
                "similarity": m.similarity,
                "created_at": m.created_at.isoformat(),
            }
            for m in memories
        ],
        "total": len(memories),
        "query": data.query,
    }


# =============================================================================
# Stats Endpoints
# =============================================================================

@router.get("/stats")
async def get_stats(user: CurrentUser = Depends(get_current_user)):
    """Get memory statistics for dashboard."""
    db = await get_database()
    repo = MemoryRepository(db)

    stats = await repo.get_memory_stats(user.id)

    # Get recent memories for activity
    recent = await repo.list_by_user(user.id, limit=10)

    # Get top entities
    entities = await repo.get_entities_for_user(user.id)
    entity_counts: dict[str, int] = {}
    for mem in await repo.list_by_user(user.id, limit=100):
        for entity in mem.entities:
            entity_counts[entity] = entity_counts.get(entity, 0) + 1

    top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Calculate by_importance distribution
    importance_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for mem in await repo.list_by_user(user.id, limit=500):
        if mem.importance <= 2:
            importance_counts["low"] += 1
        elif mem.importance <= 5:
            importance_counts["medium"] += 1
        elif mem.importance <= 8:
            importance_counts["high"] += 1
        else:
            importance_counts["critical"] += 1

    return {
        "total_memories": stats["total_memories"],
        "by_type": stats["by_type"],
        "by_importance": importance_counts,
        "recent_activity": [
            {
                "date": m.created_at.date().isoformat(),
                "id": str(m.id),
                "content_preview": m.content[:100],
                "type": m.memory_type.value,
            }
            for m in recent
        ],
        "top_entities": [{"entity": e, "count": c} for e, c in top_entities],
        "avg_importance": stats["avg_importance"],
        "last_7_days": 0,  # TODO: Calculate from date range
        "last_30_days": 0,  # TODO: Calculate from date range
    }


# =============================================================================
# Knowledge Graph Endpoints
# =============================================================================

@router.get("/graph/edges")
async def get_graph_edges(
    user: CurrentUser = Depends(get_current_user),
    memory_id: UUID | None = Query(default=None),
):
    """Get knowledge graph edges for visualization."""
    db = await get_database()
    edge_repo = EdgeRepository(db)
    memory_repo = MemoryRepository(db)

    if memory_id:
        # Get edges connected to a specific memory
        edges = await edge_repo.get_edges_for_memory(memory_id, user.id)
        # Get connected memory IDs
        memory_ids = set()
        for e in edges:
            memory_ids.add(e.from_node_id)
            memory_ids.add(e.to_node_id)
    else:
        # Get all edges for user
        edges = await edge_repo.get_all_for_user(user.id, limit=200)
        memory_ids = set()
        for e in edges:
            memory_ids.add(e.from_node_id)
            memory_ids.add(e.to_node_id)

    # Get memory details for nodes
    nodes = []
    for mid in memory_ids:
        mem = await memory_repo.get_by_id(mid, user.id)
        if mem:
            nodes.append({
                "id": str(mem.id),
                "content": mem.content[:100],
                "memory_type": mem.memory_type.value,
                "importance": mem.importance,
            })

    return {
        "edges": [
            {
                "id": str(e.id),
                "from_node_id": str(e.from_node_id),
                "to_node_id": str(e.to_node_id),
                "edge_type": e.edge_type.value,
                "strength": e.strength,
                "confidence": e.confidence,
            }
            for e in edges
        ],
        "nodes": nodes,
    }


# =============================================================================
# API Keys Endpoints
# =============================================================================

@router.get("/keys")
async def list_api_keys(user: CurrentUser = Depends(get_current_user)):
    """List user's API keys."""
    from src.auth.api_keys import list_user_api_keys

    keys = await list_user_api_keys(user.id)
    return {
        "keys": [
            {
                "id": str(k["id"]),
                "key_prefix": k["key_prefix"],
                "name": k["name"],
                "scopes": k["scopes"],
                "status": k["status"],
                "last_used_at": k["last_used_at"].isoformat() if k["last_used_at"] else None,
                "created_at": k["created_at"].isoformat(),
                "expires_at": k["expires_at"].isoformat() if k["expires_at"] else None,
            }
            for k in keys
        ]
    }


@router.post("/keys")
async def create_api_key(
    data: ApiKeyCreateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new API key."""
    from src.auth.api_keys import create_api_key as create_key

    result = await create_key(
        user_id=user.id,
        name=data.name,
        scopes=data.scopes,
        expires_in_days=data.expires_in_days,
    )

    return {
        "id": str(result["id"]),
        "key": result["key"],  # Only returned once!
        "key_prefix": result["key_prefix"],
        "name": data.name,
        "scopes": data.scopes,
    }


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Revoke an API key."""
    from src.auth.api_keys import revoke_api_key as revoke_key

    success = await revoke_key(key_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"success": True, "revoked_id": str(key_id)}


# Register router
app.include_router(router)


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "knowwhere-api"}


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
