import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database

async def consolidate_taxonomy():
    print("Connecting to database...")
    db = await get_database()
    
    # Define the mapping of domain migrations
    # Format: (Old Domain Pattern, New Domain Name, New Category if applicable)
    mappings = [
        ("Source Code", "KnowWhere", "Source Code"),
        ("Testing", "KnowWhere", "Testing"),
        ("Deployment", "KnowWhere", "Deployment"),
        ("Database", "KnowWhere", "Database"),
    ]
    
    print("\n--- Starting Domain Consolidation ---")
    
    for old_domain, new_domain, category_prefix in mappings:
        print(f"Merging domain '{old_domain}' -> '{new_domain}'...")
        
        # We move the old domain to the new domain, 
        # but we also update the category to include the old domain info to preserve context
        # Example: [Source Code] / Frontend -> [KnowWhere] / Source Code / Frontend
        
        # 1. First, update categories for the memories being moved
        update_cat_query = f"""
            UPDATE memories 
            SET category = '{category_prefix} / ' || category
            WHERE domain = '{old_domain}' AND category NOT LIKE '{category_prefix} / %'
        """
        await db.execute(update_cat_query)
        
        # 2. Then, move to the new domain
        update_dom_query = f"""
            UPDATE memories 
            SET domain = '{new_domain}' 
            WHERE domain = '{old_domain}'
        """
        result = await db.execute(update_dom_query)
        count = result.replace('UPDATE ', '')
        print(f"  ✅ Moved {count} memories.")

    # normalization: Remove redundant prefixes if they exist
    # e.g., if we had [KnowWhere] / Source Code and now it's [KnowWhere] / Source Code / Source Code
    print("\n--- Normalizing Categories ---")
    cleanup_query = """
        UPDATE memories 
        SET category = REPLACE(category, 'Source Code / Source Code', 'Source Code')
        WHERE category LIKE '%Source Code / Source Code%'
    """
    await db.execute(cleanup_query)

    # General Casing Fix for 'KnowWhere' just in case
    await db.execute("UPDATE memories SET domain = 'KnowWhere' WHERE domain ILIKE 'Knowwhere'")

    print("\nTaxonomy consolidation complete.")

if __name__ == "__main__":
    asyncio.run(consolidate_taxonomy())
