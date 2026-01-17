"""
Mock Database

In-memory database implementation for testing without PostgreSQL.
"""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4


class MockRecord:
    """Mock database record that supports dict-like access."""
    
    def __init__(self, data: dict[str, Any]):
        self._data = data
    
    def __getitem__(self, key: str) -> Any:
        return self._data[key]
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
    
    def keys(self):
        return self._data.keys()
    
    def values(self):
        return self._data.values()
    
    def items(self):
        return self._data.items()


class MockConnection:
    """Mock database connection."""
    
    def __init__(self, db: "MockDatabase"):
        self._db = db
        self._in_transaction = False
        self._transaction_data: dict[str, list[dict]] | None = None
    
    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> str:
        """Execute a query."""
        return await self._db.execute(query, *args)
    
    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> list[MockRecord]:
        """Fetch multiple rows."""
        return await self._db.fetch(query, *args)
    
    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> MockRecord | None:
        """Fetch a single row."""
        return await self._db.fetchrow(query, *args)
    
    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        """Fetch a single value."""
        return await self._db.fetchval(query, *args, column=column)
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["MockConnection", None]:
        """Start a transaction."""
        self._in_transaction = True
        self._transaction_data = {k: list(v) for k, v in self._db._tables.items()}
        try:
            yield self
        except Exception:
            # Rollback on error
            if self._transaction_data:
                self._db._tables = self._transaction_data
            raise
        finally:
            self._in_transaction = False
            self._transaction_data = None


class MockDatabase:
    """
    In-memory database for testing.
    
    Simulates PostgreSQL behavior with in-memory storage.
    Supports basic CRUD operations used by the repositories.
    """
    
    @staticmethod
    def _encode_vector(vector: list[float]) -> str:
        """Encode a vector to pgvector format."""
        return "[" + ",".join(str(v) for v in vector) + "]"
    
    @staticmethod
    def _decode_vector(data: str) -> list[float]:
        """Decode a pgvector string to list."""
        if not data or data == "[]":
            return []
        # Remove brackets and split
        cleaned = data.strip("[]")
        if not cleaned:
            return []
        return [float(x.strip()) for x in cleaned.split(",")]
    
    def __init__(self):
        self._tables: dict[str, list[dict[str, Any]]] = {
            "users": [],
            "memories": [],
            "knowledge_edges": [],
            "api_keys": [],
            "consolidation_history": [],
            "access_logs": [],
        }
        self._connected = False
        self._pool = None
    
    async def connect(self) -> None:
        """Simulate connection."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
    
    @property
    def pool(self):
        """Get mock pool."""
        return self
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[MockConnection, None]:
        """Acquire a connection from the pool."""
        yield MockConnection(self)
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[MockConnection, None]:
        """Start a transaction."""
        conn = MockConnection(self)
        async with conn.transaction():
            yield conn
    
    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> str:
        """Execute a query and return status."""
        query_lower = query.lower().strip()
        
        if query_lower.startswith("insert"):
            return await self._handle_insert(query, args)
        elif query_lower.startswith("update"):
            return await self._handle_update(query, args)
        elif query_lower.startswith("delete"):
            return await self._handle_delete(query, args)
        elif query_lower.startswith("create"):
            return "CREATE"
        
        return "OK"
    
    async def executemany(
        self,
        query: str,
        args: list[tuple[Any, ...]],
        timeout: float | None = None,
    ) -> None:
        """Execute a query multiple times."""
        for arg_tuple in args:
            await self.execute(query, *arg_tuple)
    
    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> list[MockRecord]:
        """Fetch multiple rows."""
        table_name = self._extract_table_name(query)
        if not table_name or table_name not in self._tables:
            return []
        
        rows = self._tables[table_name]
        filtered = self._apply_filters(rows, query, args)
        
        # Apply LIMIT if present
        limit = self._extract_limit(query)
        if limit:
            filtered = filtered[:limit]
        
        # Add similarity score for vector search queries
        query_lower = query.lower()
        if "1 - (embedding <=> $" in query_lower or "similarity" in query_lower:
            # Add a fake similarity score to each row
            for row in filtered:
                row["similarity"] = 0.85
        
        return [MockRecord(row) for row in filtered]
    
    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> MockRecord | None:
        """Fetch a single row."""
        query_lower = query.lower().strip()
        
        # Handle INSERT...RETURNING
        if query_lower.startswith("insert") and "returning" in query_lower:
            return await self._handle_insert_returning(query, args)
        
        results = await self.fetch(query, *args)
        return results[0] if results else None
    
    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        """Fetch a single value."""
        # Handle SELECT 1 for health check
        if "select 1" in query.lower():
            return 1
        
        # Handle COUNT queries
        if "count(*)" in query.lower():
            table_name = self._extract_table_name(query)
            if table_name and table_name in self._tables:
                rows = self._tables[table_name]
                filtered = self._apply_filters(rows, query, args)
                return len(filtered)
            return 0
        
        # Handle EXISTS queries
        if "exists" in query.lower():
            row = await self.fetchrow(query, *args)
            return row is not None
        
        row = await self.fetchrow(query, *args)
        if row is None:
            return None
        
        keys = list(row.keys())
        if column < len(keys):
            return row[keys[column]]
        return None
    
    async def exists(self, query: str, *args: Any) -> bool:
        """Check if query returns results."""
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
        return self._connected
    
    # =========================================================================
    # Helper methods for CRUD operations
    # =========================================================================
    
    async def _handle_insert(self, query: str, args: tuple) -> str:
        """Handle INSERT queries."""
        await self._do_insert(query, args)
        return f"INSERT 0 1"
    
    async def _do_insert(self, query: str, args: tuple) -> dict:
        """Perform the insert and return the new record."""
        table_name = self._extract_table_name(query)
        if not table_name:
            return {}
        
        if table_name not in self._tables:
            self._tables[table_name] = []
        
        # Create new record with auto-generated fields
        new_record = {
            "id": uuid4(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        # Extract column names from query
        columns = self._extract_columns(query)
        
        # Map args to columns
        for i, col in enumerate(columns):
            if i < len(args):
                value = args[i]
                # Convert UUID to proper type
                if isinstance(value, UUID):
                    new_record[col] = value
                else:
                    new_record[col] = value
        
        # Add default values for memories table
        if table_name == "memories":
            new_record.setdefault("status", "active")
            new_record.setdefault("access_count", 0)
            new_record.setdefault("last_accessed", None)
            new_record.setdefault("deleted_at", None)
            new_record.setdefault("superseded_by", None)
        
        # Add default values for api_keys table
        if table_name == "api_keys":
            new_record.setdefault("revoked", False)
            new_record.setdefault("last_used", None)
        
        # Add default values for knowledge_edges table
        if table_name == "knowledge_edges":
            new_record.setdefault("causality", False)
            new_record.setdefault("bidirectional", False)
        
        self._tables[table_name].append(new_record)
        return new_record
    
    async def _handle_insert_returning(self, query: str, args: tuple) -> MockRecord | None:
        """Handle INSERT...RETURNING queries."""
        new_record = await self._do_insert(query, args)
        if not new_record:
            return None
        return MockRecord(new_record)
    
    async def _handle_update(self, query: str, args: tuple) -> str:
        """Handle UPDATE queries."""
        table_name = self._extract_table_name(query)
        if not table_name or table_name not in self._tables:
            return "UPDATE 0"
        
        rows = self._tables[table_name]
        updated = 0
        query_lower = query.lower()
        
        for row in rows:
            if self._row_matches_where(row, query, args):
                # Simple update logic - would need to parse SET clause properly
                row["updated_at"] = datetime.utcnow()
                
                # Handle status update for delete (soft delete)
                if "status = $" in query_lower:
                    # Find status value in args
                    for arg in args:
                        if arg in ["deleted", "active", "archived"]:
                            row["status"] = arg
                            if arg == "deleted":
                                row["deleted_at"] = datetime.utcnow()
                            break
                elif "status = 'deleted'" in query_lower:
                    row["status"] = "deleted"
                    row["deleted_at"] = datetime.utcnow()
                
                # Handle access count increment
                if "access_count = access_count + 1" in query:
                    row["access_count"] = row.get("access_count", 0) + 1
                    row["last_accessed"] = datetime.utcnow()
                
                updated += 1
        
        return f"UPDATE {updated}"
    
    async def _handle_delete(self, query: str, args: tuple) -> str:
        """Handle DELETE queries."""
        table_name = self._extract_table_name(query)
        if not table_name or table_name not in self._tables:
            return "DELETE 0"
        
        rows = self._tables[table_name]
        original_count = len(rows)
        
        self._tables[table_name] = [
            row for row in rows
            if not self._row_matches_where(row, query, args)
        ]
        
        deleted = original_count - len(self._tables[table_name])
        return f"DELETE {deleted}"
    
    def _extract_table_name(self, query: str) -> str | None:
        """Extract table name from query."""
        query_lower = query.lower()
        
        for keyword in ["from", "into", "update"]:
            if keyword in query_lower:
                parts = query_lower.split(keyword)
                if len(parts) > 1:
                    # Get the word after the keyword
                    remaining = parts[1].strip().split()[0]
                    # Clean up parentheses and other chars
                    table = remaining.strip("() \t\n")
                    return table
        
        return None
    
    def _extract_columns(self, query: str) -> list[str]:
        """Extract column names from INSERT query."""
        # Find the part between ( and ) after table name
        try:
            start = query.index("(") + 1
            end = query.index(")")
            columns_str = query[start:end]
            columns = [c.strip() for c in columns_str.split(",")]
            return columns
        except ValueError:
            return []
    
    def _extract_limit(self, query: str) -> int | None:
        """Extract LIMIT value from query."""
        query_lower = query.lower()
        if "limit" in query_lower:
            parts = query_lower.split("limit")
            if len(parts) > 1:
                try:
                    # Get the number after LIMIT
                    limit_part = parts[1].strip().split()[0]
                    return int(limit_part.strip("$"))
                except (ValueError, IndexError):
                    pass
        return None
    
    def _apply_filters(
        self,
        rows: list[dict],
        query: str,
        args: tuple,
    ) -> list[dict]:
        """Apply WHERE clause filters."""
        query_lower = query.lower()
        
        # No WHERE clause
        if "where" not in query_lower:
            return rows
        
        filtered = []
        for row in rows:
            if self._row_matches_where(row, query, args):
                filtered.append(row)
        
        return filtered
    
    def _row_matches_where(
        self,
        row: dict,
        query: str,
        args: tuple,
    ) -> bool:
        """Check if a row matches the WHERE clause."""
        import re
        query_lower = query.lower()
        
        # Extract WHERE clause
        if "where" not in query_lower:
            return True
        
        where_part = query_lower.split("where")[1].split("order")[0].split("limit")[0]
        
        # Find all parameter references ($1, $2, etc.) and their associated column names
        # Pattern: column_name = $N or column_name=$N
        param_matches = re.findall(r'(\w+)\s*=\s*\$(\d+)', where_part)
        
        for column_name, param_num in param_matches:
            param_idx = int(param_num) - 1  # $1 is args[0]
            if param_idx < len(args):
                expected_value = args[param_idx]
                actual_value = row.get(column_name)
                
                # Handle UUID comparison
                if actual_value != expected_value:
                    return False
        
        # Check literal status filter
        if "status = 'active'" in where_part:
            if row.get("status") != "active":
                return False
        elif "status = 'deleted'" in where_part:
            if row.get("status") != "deleted":
                return False
        
        return True
    
    # =========================================================================
    # Test helper methods
    # =========================================================================
    
    def add_user(self, user_id: UUID, email: str, tier: str = "free") -> dict:
        """Add a user directly for testing."""
        user = {
            "id": user_id,
            "email": email,
            "tier": tier,
            "email_verified": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        self._tables["users"].append(user)
        return user
    
    def add_memory(self, memory: dict) -> dict:
        """Add a memory directly for testing."""
        memory.setdefault("id", uuid4())
        memory.setdefault("created_at", datetime.utcnow())
        memory.setdefault("updated_at", datetime.utcnow())
        memory.setdefault("status", "active")
        memory.setdefault("access_count", 0)
        memory.setdefault("last_accessed", None)
        memory.setdefault("deleted_at", None)
        memory.setdefault("superseded_by", None)
        memory.setdefault("source_id", None)
        memory.setdefault("metadata", {})
        memory.setdefault("entities", [])
        memory.setdefault("importance", 5)
        memory.setdefault("confidence", 0.8)
        memory.setdefault("source", "manual")
        self._tables["memories"].append(memory)
        return memory
    
    def get_table(self, table_name: str) -> list[dict]:
        """Get all records from a table."""
        return self._tables.get(table_name, [])
    
    def clear_table(self, table_name: str) -> None:
        """Clear all records from a table."""
        if table_name in self._tables:
            self._tables[table_name] = []
    
    def clear_all(self) -> None:
        """Clear all tables."""
        for table_name in self._tables:
            self._tables[table_name] = []


# Convenience function to match the real database pattern
async def get_mock_database() -> MockDatabase:
    """Get a mock database instance."""
    db = MockDatabase()
    await db.connect()
    return db
