"""
Database Connection Manager

Async PostgreSQL connection with connection pooling via asyncpg.
Supports Supabase and any PostgreSQL with pgvector.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import asyncpg
import structlog
from asyncpg import Pool, Connection

from src.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class Database:
    """
    Async PostgreSQL database manager with connection pooling.
    
    Provides:
    - Connection pooling via asyncpg
    - Transaction support
    - Query execution helpers
    - pgvector support
    """
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._pool: Pool | None = None
        self._initialized = False
    
    async def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            logger.warning("Database pool already initialized")
            return
        
        logger.info(
            "Connecting to database",
            min_size=self.settings.db_pool_min_size,
            max_size=self.settings.db_pool_max_size,
        )
        
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self.settings.database_url.get_secret_value(),
                min_size=self.settings.db_pool_min_size,
                max_size=self.settings.db_pool_max_size,
                command_timeout=60,
                # Enable pgvector extension support
                init=self._init_connection,
            )
            self._initialized = True
            logger.info("Database connection pool established")
        except Exception as e:
            logger.error("Failed to connect to database", error=str(e))
            raise
    
    async def _init_connection(self, conn: Connection) -> None:
        """
        Initialize each connection with pgvector support.
        
        Called for every new connection in the pool.
        """
        # Register pgvector type codec
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        # Set up custom type codecs for vector type
        await conn.set_type_codec(
            'vector',
            encoder=self._encode_vector,
            decoder=self._decode_vector,
            schema='public',
            format='text',
        )
    
    @staticmethod
    def _encode_vector(vector: list[float]) -> str:
        """Encode Python list to pgvector string format."""
        return f"[{','.join(str(x) for x in vector)}]"
    
    @staticmethod
    def _decode_vector(data: str) -> list[float]:
        """Decode pgvector string to Python list."""
        # Remove brackets and split
        clean = data.strip('[]')
        if not clean:
            return []
        return [float(x) for x in clean.split(',')]
    
    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Database connection pool closed")
    
    @property
    def pool(self) -> Pool:
        """Get the connection pool."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Connection, None]:
        """
        Acquire a connection from the pool.
        
        Usage:
            async with db.acquire() as conn:
                await conn.fetch("SELECT * FROM users")
        """
        async with self.pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Connection, None]:
        """
        Acquire a connection and start a transaction.
        
        Usage:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO users ...")
                await conn.execute("INSERT INTO memories ...")
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> str:
        """
        Execute a query and return status.
        
        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout in seconds
            
        Returns:
            Status string (e.g., "INSERT 0 1")
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
    
    async def executemany(
        self,
        query: str,
        args: list[tuple[Any, ...]],
        timeout: float | None = None,
    ) -> None:
        """
        Execute a query multiple times with different arguments.
        
        Useful for batch inserts.
        """
        async with self.acquire() as conn:
            await conn.executemany(query, args, timeout=timeout)
    
    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> list[asyncpg.Record]:
        """
        Fetch multiple rows.
        
        Returns:
            List of Record objects
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> asyncpg.Record | None:
        """
        Fetch a single row.
        
        Returns:
            Record object or None if not found
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
    
    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        """
        Fetch a single value.
        
        Args:
            query: SQL query
            *args: Query parameters
            column: Column index to return
            timeout: Query timeout
            
        Returns:
            The value from the specified column
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)
    
    async def exists(self, query: str, *args: Any) -> bool:
        """Check if a query returns any results."""
        result = await self.fetchval(f"SELECT EXISTS({query})", *args)
        return result is True
    
    async def count(self, table: str, where: str = "1=1", *args: Any) -> int:
        """Count rows in a table."""
        result = await self.fetchval(
            f"SELECT COUNT(*) FROM {table} WHERE {where}",
            *args
        )
        return result or 0
    
    async def health_check(self) -> bool:
        """Check if database is healthy."""
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database instance
_database: Database | None = None


async def get_database() -> Database:
    """
    Get the global database instance.
    
    Creates and connects if not already done.
    """
    global _database
    
    if _database is None:
        _database = Database()
        await _database.connect()
    
    return _database


async def close_database() -> None:
    """Close the global database connection."""
    global _database
    
    if _database is not None:
        await _database.disconnect()
        _database = None


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[Connection, None]:
    """
    Convenience context manager for getting a database connection.
    
    Usage:
        async with get_db_connection() as conn:
            await conn.fetch("SELECT * FROM memories")
    """
    db = await get_database()
    async with db.acquire() as conn:
        yield conn
