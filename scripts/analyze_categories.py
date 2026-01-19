import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def analyze():
    print("Connecting to database...")
    db = await get_database()
    
    print("\n--- Domain/Category Distribution ---")
    rows = await db.fetch("""
        SELECT domain, category, COUNT(*) as c 
        FROM memories 
        GROUP BY domain, category 
        ORDER BY c DESC
    """)
    
    for r in rows:
        print(f"{r['domain']} / {r['category']}: {r['c']}")
        
    print(f"\nTotal Groups: {len(rows)}")

if __name__ == "__main__":
    asyncio.run(analyze())
