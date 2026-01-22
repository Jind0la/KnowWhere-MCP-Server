import asyncio
from uuid import UUID
from src.storage.database import Database

async def check_last_refine():
    db = Database()
    try:
        await db.connect()
        
        # Get the most recently updated memory that has a superseded_by link
        query = """
            SELECT id, status, content, superseded_by, updated_at 
            FROM memories 
            WHERE superseded_by IS NOT NULL 
            ORDER BY updated_at DESC 
            LIMIT 1
        """
        old_mem = await db.fetchrow(query)
        
        if not old_mem:
            print("No superseded memories found.")
            return

        new_mem_id = old_mem["superseded_by"]
        new_mem = await db.fetchrow("SELECT id, status, content, created_at FROM memories WHERE id = $1", new_mem_id)
        
        print(f"--- Original Memory ({old_mem['id']}) ---")
        print(f"Status: {old_mem['status']}")
        print(f"Content: {old_mem['content']}")
        print(f"Update Time: {old_mem['updated_at']}")
        print(f"Superseded By: {old_mem['superseded_by']}")
        
        if new_mem:
            print(f"\n--- Refined Memory ({new_mem['id']}) ---")
            print(f"Status: {new_mem['status']}")
            print(f"Content: {new_mem['content']}")
            print(f"Created At: {new_mem['created_at']}")
        else:
            print(f"\nRefined memory {new_mem_id} not found!")
            
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_last_refine())
