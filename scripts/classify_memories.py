import asyncio
import os
import sys
from uuid import UUID

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import get_database
from src.services.llm import get_llm_service
from src.models.memory import Memory

async def classify_memories():
    print("Connecting to services...")
    db = await get_database()
    llm = await get_llm_service()
    
    total_updated = 0
    
    while True:
        # 1. Fetch unclassified memories
        print("Fetching unclassified memories...")
        records = await db.fetch(
            "SELECT id, content FROM memories WHERE domain IS NULL OR category IS NULL LIMIT 50"
        )
        
        if not records:
            print("No more unclassified memories found.")
            break
            
        print(f"Found {len(records)} memories to classify.")
    
        # 2. Process in batches
        batch_size = 10
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}...")
            
            # Parallel classification
            tasks = [llm.classify_content(r["content"]) for r in batch]
            results = await asyncio.gather(*tasks)
            
            # Update DB
            for record, form in zip(batch, results):
                domain = form.get("domain") or "Unclassified"
                category = form.get("category") or "General"
                
                try:
                    await db.execute(
                        """
                        UPDATE memories 
                        SET domain = $1, category = $2 
                        WHERE id = $3
                        """,
                        domain,
                        category,
                        record["id"]
                    )
                    print(f"Updated {record['id']} -> {domain}/{category}")
                    total_updated += 1
                except Exception as e:
                    print(f"Failed to update {record['id']}: {e}")
                    
    print(f"Classification complete. Updated {total_updated} memories.")

if __name__ == "__main__":
    asyncio.run(classify_memories())
