import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def verify_and_scan():
    print("Connecting to database...")
    db = await get_database()
    
    # 1. Verify specific deletion
    target_id = 'a9b34499-7c9b-490e-8fdc-33154d6f5d08'
    row = await db.fetchrow(f"SELECT id FROM memories WHERE id = '{target_id}'")
    if row:
        print(f"❌ CRITICAL: Memory {target_id} STILL EXISTS! Deduplication failed to commit/execute.")
    else:
        print(f"✅ Success: Memory {target_id} was successfully deleted.")

    # 2. Scan for remaining duplicates (lower threshold)
    print("\n--- Scanning for duplicates > 0.90 similarity ---")
    query = """
        SELECT 
            m1.id as id1, m1.content as content1,
            m2.id as id2, m2.content as content2,
            1 - (m1.embedding <=> m2.embedding) as similarity,
            m1.domain, m1.category
        FROM memories m1
        JOIN memories m2 ON m1.id < m2.id
        WHERE 1 - (m1.embedding <=> m2.embedding) > 0.90
        ORDER BY similarity DESC
        LIMIT 10
    """
    
    rows = await db.fetch(query)
    if not rows:
        print("No duplicates > 0.90 found.")
    else:
        print(f"Found {len(rows)} pairs > 0.90:")
        for r in rows:
            print(f"Sim: {r['similarity']:.4f}")
            print(f"1: {r['content1'][:60]}...")
            print(f"2: {r['content2'][:60]}...")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(verify_and_scan())
