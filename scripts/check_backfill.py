import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def check_backfill():
    print("Checking database...")
    db = await get_database()
    
    total = await db.fetchval("SELECT COUNT(*) FROM memories")
    classified = await db.fetchval("SELECT COUNT(*) FROM memories WHERE domain IS NOT NULL")
    
    print(f"Total Memories: {total}")
    print(f"Classified Memories: {classified}")
    
    if classified > 0:
        sample = await db.fetchrow("SELECT content, domain, category FROM memories WHERE domain IS NOT NULL LIMIT 1")
        print(f"Sample: {sample}")

if __name__ == "__main__":
    asyncio.run(check_backfill())
