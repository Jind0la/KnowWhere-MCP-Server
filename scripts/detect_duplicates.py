import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def find_duplicates():
    print("Connecting to database...")
    db = await get_database()
    
    print("\n--- Searching for Semantic Duplicates (>0.95 similarity) ---")
    
    # Using <=> operator for cosine distance. Similarity = 1 - distance
    query = """
        SELECT 
            m1.id as id1, m1.content as content1, m1.domain as d1, m1.category as c1,
            m2.id as id2, m2.content as content2, m2.domain as d2, m2.category as c2,
            1 - (m1.embedding <=> m2.embedding) as similarity
        FROM memories m1
        JOIN memories m2 ON m1.id < m2.id
        WHERE 1 - (m1.embedding <=> m2.embedding) > 0.95
        ORDER BY similarity DESC
        LIMIT 20
    """
    
    rows = await db.fetch(query)
    
    if not rows:
        print("No duplicates found with >0.95 similarity.")
        return

    print(f"Found {len(rows)} potential duplicate pairs:\n")
    
    for r in rows:
        print(f"Similarity: {r['similarity']:.4f}")
        print(f"1 [{r['d1']}/{r['c1']}]: {r['content1'][:100]}...")
        print(f"2 [{r['d2']}/{r['c2']}]: {r['content2'][:100]}...")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(find_duplicates())
