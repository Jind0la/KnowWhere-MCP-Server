import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.storage.database import get_database

async def run_migration():
    print("🐘 Applying migration 005_add_draft_status.sql...")
    db = await get_database()
    
    migration_file = "migrations/005_add_draft_status.sql"
    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        return

    with open(migration_file, "r") as f:
        sql = f.read()
    
    try:
        await db.execute(sql)
        print("✅ Migration successful!")
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_migration())
