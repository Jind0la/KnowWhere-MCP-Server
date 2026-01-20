import asyncio
import uuid
import httpx
from src.storage.database import get_database
from src.storage.repositories.user_repo import UserRepository
from src.models.user import UserCreate
from src.models.memory import MemoryStatus, MemoryCreate, MemorySource, MemoryType
from src.storage.repositories.memory_repo import MemoryRepository
from src.services.embedding import get_embedding_service

async def verify_feedback():
    print("🚀 Starting Feedback API Verification")
    
    # 1. Setup - Create a fresh test user
    db = await get_database()
    user_repo = UserRepository(db)
    test_email = f"feedback-test-{uuid.uuid4().hex[:6]}@example.com"
    user = await user_repo.create(UserCreate(email=test_email))
    user_id = user.id
    print(f"👤 Created Test User: {test_email}")

    repo = MemoryRepository(db)
    embed_svc = await get_embedding_service()
    
    test_content = "I like drinking green tea in the morning."
    embedding = await embed_svc.embed(test_content)
    
    # 2. Create a DRAFT memory
    memory_create = MemoryCreate(
        user_id=user_id,
        content=test_content,
        memory_type=MemoryType.PREFERENCE,
        status=MemoryStatus.DRAFT,
        source=MemorySource.CONVERSATION,
        confidence=0.5,
        embedding=embedding,
    )
    draft_mem = await repo.create(memory_create)
    print(f"📝 Created DRAFT memory: {draft_mem.id}")

    # 3. Simulate API call for APPROVE
    # We'll use the repository directly since we can't easily mock the 'get_current_user' dependency without a full server context
    # However, we can test the logic flow we implemented in web.py
    
    print("\n👍 Testing APPROVE action...")
    update_data = {"status": MemoryStatus.ACTIVE, "confidence": 1.0}
    # (Mimicking web.py logic)
    from src.models.memory import MemoryUpdate
    await repo.update(draft_mem.id, user_id, MemoryUpdate(**update_data))
    
    updated = await repo.get_by_id(draft_mem.id, user_id)
    print(f"   Memory status after approval: {updated.status}")
    if updated.status == MemoryStatus.ACTIVE:
        print("   ✅ Approve Success")
    else:
        print("   ❌ Approve Failure")

    # 4. Create another DRAFT for REJECT
    draft_mem_2 = await repo.create(memory_create)
    print(f"\n📝 Created second DRAFT memory: {draft_mem_2.id}")
    
    print("👎 Testing REJECT action...")
    # (Mimicking web.py logic)
    await repo.update(draft_mem_2.id, user_id, MemoryUpdate(status=MemoryStatus.DELETED))
    
    rejected = await repo.get_by_id(draft_mem_2.id, user_id)
    # Note: get_by_id might filter out deleted by default depending on implementation
    if not rejected or rejected.status == MemoryStatus.DELETED:
        print("   ✅ Reject Success")
    else:
        print(f"   ❌ Reject Failure (Status: {rejected.status})")

if __name__ == "__main__":
    asyncio.run(verify_feedback())
