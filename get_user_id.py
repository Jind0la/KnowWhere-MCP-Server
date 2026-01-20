import asyncio
from src.storage.database import get_database

async def get_user():
    db = await get_database()
    r = await db.fetch("SELECT id FROM users LIMIT 1")
    if r:
        print(r[0]["id"])
    else:
        print("No user found")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(get_user())
