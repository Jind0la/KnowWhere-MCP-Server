"""
Normalizes the taxonomy data to strictly follow the hierarchical structure.
Moves categories like 'Testing', 'Database' under 'Source Code / ...' if Domain is 'KnowWhere'.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.database import get_database


async def normalize_taxonomy():
    """Normalize existing categories in the KnowWhere domain."""
    db = await get_database()
    
    print("Starting taxonomy normalization...")
    
    # 1. Categories to move under "Source Code / "
    source_code_modules = [
        "Testing", "Database", "Auth", "API", "Frontend", 
        "Backend", "Config", "Services", "Core Engine", "Tests"
    ]
    
    for module in source_code_modules:
        # Move flat category to Source Code hierarchy
        update_query = """
            UPDATE memories 
            SET category = 'Source Code / ' || $1
            WHERE domain = 'KnowWhere' 
              AND category = $1 
              AND status = 'active'
            RETURNING id
        """
        result = await db.fetch(update_query, module)
        if result:
            print(f"  ✅ Migrated {len(result)} memories: '{module}' -> 'Source Code / {module}'")

    # 2. Cleanup redundant slashes or minor casing issues if any
    cleanup_query = """
        UPDATE memories 
        SET category = REPLACE(category, 'Source Code / Source Code /', 'Source Code /')
        WHERE domain = 'KnowWhere' AND category LIKE 'Source Code / Source Code /%'
    """
    await db.execute(cleanup_query)
    
    # 3. Consolidate "Testing" vs "Tests" if necessary (optional - let's keep them distinct for now if they mean different things)
    
    # 4. Final Count
    print("\n📊 Normalization Summary:")
    count_query = """
        SELECT category, COUNT(*) as count 
        FROM memories 
        WHERE domain = 'KnowWhere' AND status = 'active'
        GROUP BY category 
        ORDER BY count DESC
        LIMIT 10
    """
    rows = await db.fetch(count_query)
    for row in rows:
        print(f"   {row['category']}: {row['count']}")
        
    print("\n✅ Normalization complete!")


if __name__ == "__main__":
    asyncio.run(normalize_taxonomy())
