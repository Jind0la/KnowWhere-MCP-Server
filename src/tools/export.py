"""
MCP Tool: export_memories

Export user memories for backup or analysis.
"""

import csv
import io
import json
from datetime import datetime
from uuid import UUID

import structlog

from src.models.memory import MemoryType
from src.models.requests import ExportFormat, ExportInput, ExportOutput, RecallFilters
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository

logger = structlog.get_logger(__name__)


async def export_memories(
    user_id: UUID,
    format: str = "json",
    filters: dict | None = None,
    include_embeddings: bool = False,
) -> ExportOutput:
    """
    Export user memories for backup or analysis.
    
    This tool exports all or filtered memories in JSON or CSV format.
    Useful for:
    - Data portability (GDPR compliance)
    - Backup and recovery
    - Analysis in external tools
    
    Args:
        user_id: The user whose memories to export
        format: Export format ('json' or 'csv')
        filters: Optional filters to narrow export
        include_embeddings: Whether to include vector embeddings (large!)
        
    Returns:
        ExportOutput with exported data
    """
    logger.info(
        "Export memories tool called",
        user_id=str(user_id),
        format=format,
        include_embeddings=include_embeddings,
    )
    
    # Parse format
    try:
        export_format = ExportFormat(format.lower())
    except ValueError:
        export_format = ExportFormat.JSON
    
    # Get database
    db = await get_database()
    repo = MemoryRepository(db)
    
    # Parse filters
    memory_type = None
    if filters and "memory_type" in filters:
        try:
            memory_type = MemoryType(filters["memory_type"].lower())
        except ValueError:
            pass
    
    # Fetch memories
    memories = await repo.list_by_user(
        user_id=user_id,
        limit=10000,  # High limit for export
        memory_type=memory_type,
    )
    
    # Convert to export format
    if export_format == ExportFormat.JSON:
        data = _export_json(memories, include_embeddings)
    else:
        data = _export_csv(memories, include_embeddings)
    
    # Calculate size
    file_size = len(data.encode("utf-8")) if isinstance(data, str) else len(json.dumps(data).encode("utf-8"))
    
    logger.info(
        "Export completed",
        memories_count=len(memories),
        format=export_format.value,
        size_bytes=file_size,
    )
    
    return ExportOutput(
        format=export_format,
        count=len(memories),
        data=data,
        export_date=datetime.utcnow(),
        file_size_bytes=file_size,
    )


def _export_json(memories: list, include_embeddings: bool) -> list[dict]:
    """Export memories as JSON."""
    result = []
    
    for memory in memories:
        item = {
            "id": str(memory.id),
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "entities": memory.entities,
            "importance": memory.importance,
            "confidence": memory.confidence,
            "status": memory.status.value,
            "source": memory.source.value if hasattr(memory.source, 'value') else str(memory.source),
            "source_id": memory.source_id,
            "access_count": memory.access_count,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
            "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed else None,
            "metadata": memory.metadata,
        }
        
        if include_embeddings:
            item["embedding"] = memory.embedding
        
        result.append(item)
    
    return result


def _export_csv(memories: list, include_embeddings: bool) -> str:
    """Export memories as CSV."""
    output = io.StringIO()
    
    # Define headers
    headers = [
        "id", "content", "memory_type", "entities", "importance",
        "confidence", "status", "source", "source_id", "access_count",
        "created_at", "updated_at", "last_accessed",
    ]
    
    if include_embeddings:
        headers.append("embedding")
    
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    
    for memory in memories:
        row = {
            "id": str(memory.id),
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "entities": json.dumps(memory.entities),
            "importance": memory.importance,
            "confidence": memory.confidence,
            "status": memory.status.value,
            "source": memory.source.value if hasattr(memory.source, 'value') else str(memory.source),
            "source_id": memory.source_id or "",
            "access_count": memory.access_count,
            "created_at": memory.created_at.isoformat() if memory.created_at else "",
            "updated_at": memory.updated_at.isoformat() if memory.updated_at else "",
            "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed else "",
        }
        
        if include_embeddings:
            row["embedding"] = json.dumps(memory.embedding)
        
        writer.writerow(row)
    
    return output.getvalue()


# Tool specification for MCP
EXPORT_MEMORIES_SPEC = {
    "name": "export_memories",
    "description": "Export user memories for backup or analysis. Supports JSON and CSV formats.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["json", "csv"],
                "default": "json",
                "description": "Export format",
            },
            "filters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["episodic", "semantic", "preference", "procedural", "meta"],
                        "description": "Filter by memory type",
                    },
                },
            },
            "include_embeddings": {
                "type": "boolean",
                "default": False,
                "description": "Include vector embeddings (warning: significantly increases data size)",
            },
        },
    },
}
