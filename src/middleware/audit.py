"""
Audit Logging Middleware

Logs all API access for compliance and analytics.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog

from src.storage.database import Database, get_database
import json
from uuid import UUID
from enum import Enum

class AuditJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for audit logs."""
    def default(self, obj: Any) -> Any:
        try:
            if isinstance(obj, UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Enum):
                return obj.value
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "__dict__"):
                return str(obj)
            return super().default(obj)
        except Exception:
            # Fallback for anything else to prevent audit crash
            return str(obj)

logger = structlog.get_logger(__name__)


class AuditLogger:
    """
    Asynchronous audit logger for API access.
    
    Logs:
    - User ID
    - Action/endpoint
    - Request details
    - Response status
    - Response time
    - IP address
    - Accessed resources
    
    Uses non-blocking async writes to avoid impacting response time.
    """
    
    def __init__(self, db: Database | None = None):
        self._db = db
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False
    
    async def _get_db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def start(self) -> None:
        """Start the background worker for processing logs."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Audit logger started")
    
    async def stop(self) -> None:
        """Stop the background worker."""
        self._running = False
        
        if self._worker_task:
            # Process remaining items
            while not self._queue.empty():
                await asyncio.sleep(0.1)
            
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Audit logger stopped")
    
    async def _worker(self) -> None:
        """Background worker that processes the log queue."""
        while self._running:
            try:
                # Wait for log entry with timeout
                try:
                    log_entry = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Write to database
                await self._write_log(log_entry)
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Audit worker error", error=str(e))
    
    async def _write_log(self, entry: dict) -> None:
        """Write a log entry to the database."""
        try:
            db = await self._get_db()
            
            query = """
                INSERT INTO access_logs (
                    user_id, request_id, operation, endpoint,
                    request_payload, response_status, response_time_ms,
                    accessed_memory_ids, accessed_file_ids,
                    user_agent, ip_address, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """
            
            await db.execute(
                query,
                entry.get("user_id"),
                entry.get("request_id"),
                entry.get("operation"),
                entry.get("endpoint"),
                entry.get("request_payload"),
                entry.get("response_status"),
                entry.get("response_time_ms"),
                entry.get("accessed_memory_ids"),
                entry.get("accessed_file_ids"),
                entry.get("user_agent"),
                entry.get("ip_address"),
                json.dumps(entry.get("metadata", {}), cls=AuditJSONEncoder, default=str),
            )
            
        except Exception as e:
            logger.error("Failed to write audit log", error=str(e), entry=entry)
    
    async def log(
        self,
        user_id: UUID | None,
        operation: str,
        endpoint: str | None = None,
        request_id: str | None = None,
        request_payload: dict | None = None,
        response_status: int = 200,
        response_time_ms: int = 0,
        accessed_memory_ids: list[UUID] | None = None,
        accessed_file_ids: list[UUID] | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Queue an audit log entry.
        
        Non-blocking - returns immediately after queuing.
        
        Args:
            user_id: User who made the request
            operation: Action performed (remember, recall, etc.)
            endpoint: HTTP endpoint
            request_id: Unique request identifier
            request_payload: Sanitized request data
            response_status: HTTP status code
            response_time_ms: Request duration
            accessed_memory_ids: Memory IDs accessed
            accessed_file_ids: File IDs accessed
            user_agent: Client user agent
            ip_address: Client IP
            metadata: Additional context
        """
        entry = {
            "user_id": user_id,
            "request_id": request_id,
            "operation": operation,
            "endpoint": endpoint,
            "request_payload": self._sanitize_payload(request_payload),
            "response_status": response_status,
            "response_time_ms": response_time_ms,
            "accessed_memory_ids": accessed_memory_ids,
            "accessed_file_ids": accessed_file_ids,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Non-blocking put
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            logger.warning("Audit log queue full, dropping entry")
    
    def _sanitize_payload(self, payload: dict | None) -> dict | None:
        """
        Sanitize request payload for logging.
        
        Removes sensitive fields like passwords, tokens, etc.
        """
        if payload is None:
            return None
        
        sensitive_fields = {
            "password", "token", "api_key", "secret",
            "authorization", "refresh_token", "access_token",
        }
        
        sanitized = {}
        for key, value in payload.items():
            if key.lower() in sensitive_fields:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_payload(value)
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate long strings
                sanitized[key] = value[:1000] + "...[truncated]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    async def log_tool_call(
        self,
        user_id: UUID,
        tool_name: str,
        input_params: dict | None = None,
        result: Any = None,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> None:
        """
        Log an MCP tool call.
        
        Convenience method for logging tool invocations.
        """
        await self.log(
            user_id=user_id,
            operation=f"tool:{tool_name}",
            request_payload=input_params,
            response_status=500 if error else 200,
            response_time_ms=duration_ms,
            metadata={
                "tool_name": tool_name,
                "has_result": result is not None,
                "error": error,
            },
        )


# Global audit logger instance
_audit_logger: AuditLogger | None = None


async def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
        await _audit_logger.start()
    return _audit_logger


async def close_audit_logger() -> None:
    """Close the global audit logger."""
    global _audit_logger
    if _audit_logger is not None:
        await _audit_logger.stop()
        _audit_logger = None


# Convenience context manager for timing requests
class AuditContext:
    """
    Context manager for auditing a request/operation.
    
    Usage:
        async with AuditContext(user_id, "remember") as ctx:
            result = await do_work()
            ctx.add_memory_id(result.id)
    """
    
    def __init__(
        self,
        user_id: UUID | None,
        operation: str,
        **kwargs,
    ):
        self.user_id = user_id
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = 0
        self.memory_ids: list[UUID] = []
        self.file_ids: list[UUID] = []
        self.error: str | None = None
        self.status = 200
    
    def add_memory_id(self, memory_id: UUID) -> None:
        """Add a memory ID that was accessed."""
        self.memory_ids.append(memory_id)
    
    def add_file_id(self, file_id: UUID) -> None:
        """Add a file ID that was accessed."""
        self.file_ids.append(file_id)
    
    def set_error(self, error: str, status: int = 500) -> None:
        """Set an error for the operation."""
        self.error = error
        self.status = status
    
    async def __aenter__(self) -> "AuditContext":
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = int((time.time() - self.start_time) * 1000)
        
        if exc_val:
            self.error = str(exc_val)
            self.status = 500
        
        audit_logger = await get_audit_logger()
        await audit_logger.log(
            user_id=self.user_id,
            operation=self.operation,
            response_status=self.status,
            response_time_ms=duration_ms,
            accessed_memory_ids=self.memory_ids if self.memory_ids else None,
            accessed_file_ids=self.file_ids if self.file_ids else None,
            metadata={"error": self.error} if self.error else None,
            **self.kwargs,
        )
