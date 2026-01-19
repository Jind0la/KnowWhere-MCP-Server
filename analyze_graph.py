
import asyncio
import os
from uuid import UUID
from dotenv import load_dotenv
import asyncpg
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def analyze():
    conn = await asyncpg.connect(DATABASE_URL)
    
    user_id = '1c582f6d-ff9b-44c2-9e3d-fba1bf610481'
    
    # 1. Get total counts
    mem_count = await conn.fetchval("SELECT COUNT(*) FROM memories WHERE user_id = $1", user_id)
    edge_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_edges WHERE user_id = $1", user_id)
    
    print(f"Total Memories: {mem_count}")
    print(f"Total Edges: {edge_count}")
    print("-" * 50)
    
    # 2. Sample memories
    print("SAMPLE MEMORIES (First 15):")
    memories = await conn.fetch(
        "SELECT id, content, memory_type, entities FROM memories WHERE user_id = $1 LIMIT 15", 
        user_id
    )
    for m in memories:
        content_preview = m['content'][:150].replace('\n', ' ')
        print(f"ID: {m['id']} | Type: {m['memory_type']} | Entities: {m['entities']}")
        print(f"Content: {content_preview}...")
        print("-" * 20)
    
    # 3. Sample edges and their reasons
    print("\nSAMPLE EDGES (First 15):")
    edges = await conn.fetch(
        """
        SELECT e.edge_type, e.strength, e.reason, m1.content as from_content, m2.content as to_content
        FROM knowledge_edges e
        JOIN memories m1 ON e.from_node_id = m1.id
        JOIN memories m2 ON e.to_node_id = m2.id
        WHERE e.user_id = $1
        LIMIT 15
        """,
        user_id
    )
    for e in edges:
        from_pre = e['from_content'][:50].replace('\n', ' ')
        to_pre = e['to_content'][:50].replace('\n', ' ')
        print(f"Type: {e['edge_type']} | Strength: {e['strength']}")
        print(f"Reason: {e['reason']}")
        print(f"Connection: [{from_pre}...] -> [{to_pre}...]")
        print("-" * 20)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze())
