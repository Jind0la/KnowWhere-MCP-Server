#!/usr/bin/env python3
"""
Migrate Existing Memories to Zettelkasten Entity System

This script:
1. Fetches all existing memories
2. Re-extracts entities using the new Zettelkasten system
3. Updates the memory's entities field
4. Creates memory_entity_links for graph navigation

Usage:
    python scripts/migrate_entities.py [--user-id UUID] [--dry-run] [--limit N]
"""

import asyncio
import argparse
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.database import get_database
from src.storage.repositories.memory_repo import MemoryRepository
from src.services.entity_hub_service import get_entity_hub_service
from src.models.memory import MemoryStatus


async def migrate_memories(
    user_id: UUID | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    batch_size: int = 10,
):
    """
    Migrate existing memories to use the new Zettelkasten entity system.
    """
    print("🚀 Starting Entity Migration...")
    print(f"   Dry run: {dry_run}")
    print(f"   User filter: {user_id or 'ALL USERS'}")
    print(f"   Limit: {limit or 'No limit'}")
    print()
    
    db = await get_database()
    memory_repo = MemoryRepository(db)
    entity_hub_service = await get_entity_hub_service()
    
    # Get all users if no specific user
    if user_id:
        user_ids = [user_id]
    else:
        query = "SELECT DISTINCT user_id FROM memories WHERE status = 'active'"
        rows = await db.fetch(query)
        user_ids = [row["user_id"] for row in rows]
    
    print(f"📊 Found {len(user_ids)} user(s) to process")
    
    total_processed = 0
    total_entities_created = 0
    total_links_created = 0
    errors = []
    
    for uid in user_ids:
        print(f"\n👤 Processing user: {uid}")
        
        # Get all memories for this user
        memories = await memory_repo.list_by_user(
            user_id=uid,
            limit=limit or 10000,
            status=MemoryStatus.ACTIVE,
        )
        
        print(f"   Found {len(memories)} memories")
        
        for i, memory in enumerate(memories):
            try:
                print(f"   [{i+1}/{len(memories)}] Processing memory {memory.id}...")
                
                # Extract entities with new system
                result = await entity_hub_service.extract_and_learn(
                    user_id=uid,
                    content=memory.content,
                )
                
                new_entities = [e.name for e in result.entities]
                
                print(f"      Old entities: {memory.entities[:3]}..." if len(memory.entities) > 3 else f"      Old entities: {memory.entities}")
                print(f"      New entities: {new_entities}")
                print(f"      (Dictionary: {len(result.from_dictionary)}, LLM: {len(result.from_llm)})")
                
                if not dry_run:
                    # Update memory's entities field
                    update_query = """
                        UPDATE memories 
                        SET entities = $1::jsonb, updated_at = NOW()
                        WHERE id = $2 AND user_id = $3
                    """
                    import json
                    await db.execute(
                        update_query,
                        json.dumps(new_entities),
                        memory.id,
                        uid,
                    )
                    
                    # Create memory-entity links
                    links = await entity_hub_service.link_memory_to_entities(
                        memory=memory,
                        entities=result.entities,
                    )
                    total_links_created += links
                
                total_processed += 1
                total_entities_created += len(result.from_llm)
                
            except Exception as e:
                error_msg = f"Memory {memory.id}: {str(e)}"
                print(f"      ❌ Error: {e}")
                errors.append(error_msg)
                continue
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETE")
    print("=" * 60)
    print(f"   Memories processed: {total_processed}")
    print(f"   New entities learned: {total_entities_created}")
    print(f"   Links created: {total_links_created}")
    print(f"   Errors: {len(errors)}")
    
    if errors:
        print("\n❌ Errors encountered:")
        for err in errors[:10]:
            print(f"   - {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more")
    
    if dry_run:
        print("\n⚠️  DRY RUN - No changes were made to the database")


async def main():
    parser = argparse.ArgumentParser(description="Migrate memories to Zettelkasten entity system")
    parser.add_argument("--user-id", type=str, help="Specific user ID to migrate")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just show what would happen")
    parser.add_argument("--limit", type=int, help="Limit number of memories per user")
    
    args = parser.parse_args()
    
    user_id = UUID(args.user_id) if args.user_id else None
    
    await migrate_memories(
        user_id=user_id,
        dry_run=args.dry_run,
        limit=args.limit,
    )


if __name__ == "__main__":
    asyncio.run(main())
