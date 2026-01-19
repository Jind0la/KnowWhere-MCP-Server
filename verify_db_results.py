import asyncio
import os
import sys
from uuid import UUID

# Add project root to path
sys.path.append(os.path.abspath("."))

from src.config import init_container
from src.storage.database import get_database

async def verify_db():
    print("--- Connecting to DB ---")
    await init_container()
    db = await get_database()
    
    user_id = "21f38efd-0e43-4314-96f7-c4195fc8290c"
    
    print(f"--- Checking History for User {user_id} ---")
    history = await db.fetch(
        "SELECT id, status, new_memories_created, created_at, error_message FROM consolidation_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5",
        UUID(user_id)
    )
    
    for row in history:
        print(f"ID: {row['id']} | Status: {row['status']} | Memories: {row['new_memories_created']} | Created: {row['created_at']}")
        if row['error_message']:
            print(f"  Error: {row['error_message'][:100]}...")

    print(f"\n--- Checking Recent Memories for User {user_id} ---")
    memories = await db.fetch(
        "SELECT id, content, memory_type FROM memories WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5",
        UUID(user_id)
    )
    
    for row in memories:
        print(f"ID: {row['id']} | Type: {row['memory_type']} | Content: {row['content'][:50]}...")

if __name__ == "__main__":
    asyncio.run(verify_db())
