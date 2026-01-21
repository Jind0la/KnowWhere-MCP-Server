"""
Cleanup script to fix remaining invalid domains.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.database import get_database


async def cleanup_invalid_domains():
    """Fix remaining invalid domains by migrating to KnowWhere."""
    db = await get_database()
    
    # Domains to migrate to KnowWhere (with their current categories)
    invalid_domains = ["Infrastructure", "Knowledge", "Product", "Projects"]
    
    print("Cleaning up invalid domains...")
    
    for domain in invalid_domains:
        # Update: move domain to category prefix, set domain to KnowWhere
        update_query = """
            UPDATE memories 
            SET 
                category = CASE 
                    WHEN category IS NOT NULL AND category != '' 
                    THEN $1 || ' / ' || category 
                    ELSE $1 
                END,
                domain = 'KnowWhere'
            WHERE domain = $1 AND status = 'active'
            RETURNING id
        """
        result = await db.fetch(update_query, domain)
        print(f"  Migrated {len(result)} memories from '{domain}' to 'KnowWhere'")
    
    # Also fix NULL domains
    null_query = """
        UPDATE memories 
        SET domain = 'KnowWhere', category = COALESCE(category, 'General')
        WHERE domain IS NULL AND status = 'active'
        RETURNING id
    """
    null_result = await db.fetch(null_query)
    print(f"  Fixed {len(null_result)} memories with NULL domain")
    
    print("\n✅ Cleanup complete!")


if __name__ == "__main__":
    asyncio.run(cleanup_invalid_domains())
