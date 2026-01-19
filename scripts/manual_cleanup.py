import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def manual_cleanup():
    db = await get_database()
    print("Connecting to database...")
    
    # Specific IDs identified from analysis
    ids_to_delete = [
        'c5017c57-bc54-40dc-bf2b-2a599b1081e8', # Lieblingsprojekt... (0.77 sim to English)
        '6475faa0-6e31-45d6-94f7-12f8c8fe3437', # User hat die gesamte... (0.77 sim to English)
    ]
    
    print(f"Deleting {len(ids_to_delete)} specific cross-lingual duplicates...")
    
    for mid in ids_to_delete:
        # Verify existence first
        exists = await db.fetchval(f"SELECT exists(SELECT 1 FROM memories WHERE id = '{mid}')")
        if exists:
            await db.execute(f"DELETE FROM memories WHERE id = '{mid}'")
            print(f"✅ Deleted {mid}")
        else:
            print(f"⚠️ Memory {mid} not found (already deleted?)")

if __name__ == "__main__":
    asyncio.run(manual_cleanup())
