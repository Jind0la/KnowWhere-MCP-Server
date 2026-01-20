import asyncio
import uuid
from src.config import init_container, get_container
from src.engine.shadow_listener import ShadowListener
from src.models.memory import MemoryStatus
import structlog

logger = structlog.get_logger(__name__)

async def verify():
    print("🚀 Initializing Shadow Listener Verification...")
    container = await init_container()
    listener = await container.resolve(ShadowListener)
    
    from src.storage.repositories.user_repo import UserRepository
    from src.storage.database import get_database
    
    db = await get_database()
    user_repo = UserRepository(db)
    
    from src.models.user import UserCreate
    
    # Create a real test user to satisfy foreign key
    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    user_create = UserCreate(email=test_email)
    user = await user_repo.create(user_create)
    user_id = user.id
    print(f"👤 Created Test User: {test_email} (ID: {user_id})")
    
    conversation_id = f"test-conv-{uuid.uuid4().hex[:8]}"
    
    # 1. Simulate conversation
    chunks = [
        ("user", "Hello! I am working on a new project called 'Antigravity'."),
        ("assistant", "That sounds interesting! What is it about?"),
        ("user", "It is an agentic AI coding assistant. I prefer using Python for the backend."),
        ("assistant", "Python is a great choice for AI. Anything else you'd like to share?"),
        ("user", "I live in Berlin and I'm a solo developer. I love vanilla CSS because it gives me full control."),
    ]
    
    print(f"📥 Sending {len(chunks)} chunks to Shadow Listener...")
    for role, content in chunks:
        print(f"  [{role.upper()}]: {content[:30]}...")
        await listener.listen(user_id, conversation_id, role, content)
        # Give some time for background tasks if any
        await asyncio.sleep(0.1)

    print("\n⏳ Waiting for background extraction (polling for 20s)...")
    
    from src.storage.repositories.memory_repo import MemoryRepository
    repo = MemoryRepository(db)
    
    # Check database for DRAFT memories with polling
    drafts = []
    for i in range(20):
        await asyncio.sleep(1)
        drafts = await repo.list_by_user(user_id, status=MemoryStatus.DRAFT)
        if len(drafts) > 0:
            print(f"✅ Found {len(drafts)} drafts after {i+1} seconds!")
            break
        if (i+1) % 5 == 0:
            print(f"  ...still waiting ({i+1}s)")

    print(f"\n📊 Results:")
    print(f"  Draft memories found: {len(drafts)}")
    for d in drafts:
        print(f"  - [{d.memory_type.value}] {d.content[:50]}... (Confidence: {d.confidence})")
        print(f"    Metadata: {d.metadata}")

    if len(drafts) > 0:
        print("\n✅ Shadow Listener successfully captured draft memories!")
    else:
        print("\n❌ No draft memories captured. Check heuristics or LLM output.")

if __name__ == "__main__":
    asyncio.run(verify())
