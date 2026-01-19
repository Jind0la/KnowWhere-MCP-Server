import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def run_migration():
    print("Connecting to database...")
    db = await get_database()
    
    print("Applying migration: Add semantic fields...")
    queries = [
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS domain TEXT;",
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS category TEXT;",
        "CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain);",
        "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);"
    ]
    
    for q in queries:
        try:
            print(f"Executing: {q}")
            await db.execute(q)
        except Exception as e:
            print(f"Error executing {q}: {e}")
            
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(run_migration())
