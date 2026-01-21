"""
Phase D Verification Script
Tests the taxonomy consolidation and hierarchical recall implementation.
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.database import get_database


async def verify_taxonomy():
    """Verify the taxonomy structure in the database."""
    db = await get_database()
    
    print("=" * 60)
    print("PHASE D: TAXONOMY VERIFICATION")
    print("=" * 60)
    
    # 1. Check domain distribution
    print("\n📊 Domain Distribution:")
    domain_query = """
        SELECT domain, COUNT(*) as count 
        FROM memories 
        WHERE status = 'active'
        GROUP BY domain 
        ORDER BY count DESC
    """
    domains = await db.fetch(domain_query)
    for row in domains:
        print(f"   {row['domain']}: {row['count']} memories")
    
    # 2. Verify only valid domains exist
    print("\n✅ Valid Domains Check:")
    valid_domains = ["KnowWhere", "Personal", "General"]
    invalid_query = """
        SELECT DISTINCT domain 
        FROM memories 
        WHERE status = 'active' 
        AND domain NOT IN ('KnowWhere', 'Personal', 'General')
    """
    invalid_domains = await db.fetch(invalid_query)
    if invalid_domains:
        print(f"   ❌ FAIL: Found invalid domains: {[r['domain'] for r in invalid_domains]}")
    else:
        print("   ✅ PASS: All domains are valid (KnowWhere, Personal, General)")
    
    # 3. Check category patterns for KnowWhere
    print("\n📁 KnowWhere Category Patterns:")
    category_query = """
        SELECT category, COUNT(*) as count 
        FROM memories 
        WHERE domain = 'KnowWhere' AND status = 'active'
        GROUP BY category 
        ORDER BY count DESC
        LIMIT 15
    """
    categories = await db.fetch(category_query)
    for row in categories:
        print(f"   {row['category']}: {row['count']}")
    
    # 4. Verify hierarchical patterns (categories with "/")
    print("\n🔍 Hierarchical Categories (with '/'):")
    hierarchical_query = """
        SELECT category, COUNT(*) as count 
        FROM memories 
        WHERE status = 'active' AND category LIKE '%/%'
        GROUP BY category 
        ORDER BY count DESC
        LIMIT 10
    """
    hierarchical = await db.fetch(hierarchical_query)
    if hierarchical:
        for row in hierarchical:
            print(f"   {row['category']}: {row['count']}")
    else:
        print("   (No hierarchical categories found yet - normal for fresh migrations)")
    
    print("\n" + "=" * 60)
    print("Verification Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify_taxonomy())
