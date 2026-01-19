import asyncio
import os
import sys
import math

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

def cosine_similarity(v1, v2):
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0
    return dot_product / (magnitude1 * magnitude2)

async def analyze_specific():
    db = await get_database()
    print("Connecting...")
    
    # 1. Find "Favorite Project" memories
    query_fav = "SELECT id, content, embedding FROM memories WHERE content ILIKE '%favorite project%' OR content ILIKE '%Lieblingsprojekt%'"
    fav_rows = await db.fetch(query_fav)
    
    # 2. Find "Codebase stored" memories
    query_code = "SELECT id, content, embedding FROM memories WHERE content ILIKE '%stored their entire%' OR content ILIKE '%hat die gesamte%'"
    code_rows = await db.fetch(query_code)
    
    print(f"\nFound {len(fav_rows)} rows for 'Favorite Project'")
    print(f"Found {len(code_rows)} rows for 'Codebase Stored'")
    
    print("\n--- 'Favorite Project' Cluster ---")
    seen_pairs = set()
    for r1 in fav_rows:
        for r2 in fav_rows:
            if r1['id'] < r2['id']: # Avoid self-compare and duplicates
                sim = cosine_similarity(r1['embedding'], r2['embedding'])
                print(f"Sim: {sim:.4f}")
                print(f"A ({r1['id']}): {r1['content']}")
                print(f"B ({r2['id']}): {r2['content']}")
                print("-" * 20)

    print("\n--- 'Codebase Stored' Cluster ---")
    for r1 in code_rows:
        for r2 in code_rows:
            if r1['id'] < r2['id']:
                sim = cosine_similarity(r1['embedding'], r2['embedding'])
                print(f"Sim: {sim:.4f}")
                print(f"A ({r1['id']}): {r1['content']}")
                print(f"B ({r2['id']}): {r2['content']}")
                print("-" * 20)

if __name__ == "__main__":
    asyncio.run(analyze_specific())
