import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def deduplicate():
    print("Connecting to database...")
    db = await get_database()
    
    print("\n--- Identifying Duplicates (>0.88 similarity) ---")
    
    # Fetch all pairs with high similarity
    # We select ID and CREATED_AT to decide which one to keep (keep oldest)
    query = """
        SELECT 
            m1.id as id1, m1.created_at as created1,
            m2.id as id2, m2.created_at as created2,
            1 - (m1.embedding <=> m2.embedding) as similarity,
            m1.content as content1, m2.content as content2
        FROM memories m1
        JOIN memories m2 ON m1.id < m2.id
        WHERE 1 - (m1.embedding <=> m2.embedding) > 0.88
        ORDER BY similarity DESC
    """
    
    rows = await db.fetch(query)
    
    if not rows:
        print("No duplicates found.")
        return

    to_delete = set()
    kept_count = 0
    
    print(f"Analyzing {len(rows)} high-similarity pairs...")
    
    for r in rows:
        id1 = str(r['id1'])
        id2 = str(r['id2'])
        
        # If one of them is already marked for deletion, skip this pair
        # (transitive property will handle it, or we handle simple pairs first)
        if id1 in to_delete and id2 in to_delete:
            continue
            
        # Determine victim
        if id1 in to_delete:
            # id1 is already gone, so we don't need to do anything with this pair relative to id1
            # But wait, if id2 is similar to a deleted item, maybe id2 should be deleted too?
            # For safety, let's only compare "alive" items.
            pass
        elif id2 in to_delete:
            pass
        else:
            # Both are currently "alive". Decide which one to kill.
            # Prefer keeping the older one.
            if r['created1'] <= r['created2']:
                victim = id2
                survivor = id1
            else:
                victim = id1
                survivor = id2
            
            to_delete.add(victim)
            print(f"Marking for deletion: {victim} (duplicate of {survivor})")
            print(f"  Survivor: {r['content1'][:50]}...")
            print(f"  Victim:   {r['content2'][:50]}...")
            print(f"  Sim:      {r['similarity']:.4f}")
            print("-" * 40)
            kept_count += 1

    print(f"\nFound {len(to_delete)} unique memories to delete.")
    
    if not to_delete:
        print("Nothing new to delete.")
        return

    # Batch delete
    confirm = input(f"Are you sure you want to PERMANENTLY delete {len(to_delete)} memories? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return
        
    for chunk in [list(to_delete)[i:i + 50] for i in range(0, len(to_delete), 50)]:
        placeholders = ",".join([f"'{uid}'" for uid in chunk])
        await db.execute(f"DELETE FROM memories WHERE id IN ({placeholders})")
        print(f"Deleted batch of {len(chunk)}...")
        
    print("Deduplication complete.")

if __name__ == "__main__":
    asyncio.run(deduplicate())
