
import asyncio
from uuid import UUID
from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository
from collections import Counter

async def check():
    db = await get_database()
    repo = MemoryRepository(db)
    user_id = UUID('00000000-0000-0000-0000-000000000000') # Default test user
    
    # Check stats
    stats = await repo.get_memory_stats(user_id)
    print(f"Stats: {stats}")
    
    # Check all memories including non-active
    memories = await repo.list_by_user(user_id, limit=1000, status=None)
    statuses = [m.status.value for m in memories]
    print(f"Status distribution: {Counter(statuses)}")
    
    for m in memories:
        if m.status.value != 'active':
            print(f"Found non-active: {m.id} | {m.status.value} | {m.content[:50]}...")

if __name__ == "__main__":
    asyncio.run(check())
