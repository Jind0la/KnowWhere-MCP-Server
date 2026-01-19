import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def reset_lazy_classifications():
    print("Connecting to database...")
    db = await get_database()
    
    # Target the lazy "Backend" bucket
    print("Resetting 'Knowwhere / Backend' classifications...")
    result = await db.execute("""
        UPDATE memories 
        SET domain = NULL, category = NULL 
        WHERE domain = 'Knowwhere' AND category = 'Backend'
    """)
    
    print(f"Reset complete. Result: {result}")

if __name__ == "__main__":
    asyncio.run(reset_lazy_classifications())
