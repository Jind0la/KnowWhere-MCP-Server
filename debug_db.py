
import asyncio
import os
import json
from uuid import UUID
from src.config import get_settings, init_container
from src.storage.repositories.user_repo import UserRepository
from src.storage.database import get_database

async def debug_user():
    await init_container()
    db = await get_database()
    user_repo = UserRepository(db)
    
    email = "nimarm@me.com"
    user = await user_repo.get_by_email(email)
    
    if user:
        print(f"DEBUG: Found user by email: {email}")
        print(f"DEBUG: User ID in DB: {user.id}")
        
        # Count memories for this ID
        from src.storage.repositories.memory_repo import MemoryRepository
        mem_repo = MemoryRepository(db)
        stats = await mem_repo.get_memory_stats(user.id)
        print(f"DEBUG: Memory count for ID {user.id}: {stats['total_memories']}")
    else:
        print(f"DEBUG: User not found by email: {email}")

if __name__ == "__main__":
    asyncio.run(debug_user())
