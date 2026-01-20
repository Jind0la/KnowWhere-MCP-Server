import asyncio
import uuid
import json
import httpx
from src.storage.database import get_database
from src.storage.repositories.user_repo import UserRepository
from src.models.user import UserCreate
from src.models.memory import MemoryStatus
import structlog
import logging

# Configure basic logging to catch everything
logging.basicConfig(level=logging.DEBUG)
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

async def verify_maturation():
    print("🚀 Starting End-to-End Maturation Verification")
    
    # 1. Setup - Create a fresh test user
    db = await get_database()
    user_repo = UserRepository(db)
    test_email = f"maturation-test-{uuid.uuid4().hex[:6]}@example.com"
    user = await user_repo.create(UserCreate(email=test_email))
    user_id = user.id
    print(f"👤 Created Test User: {test_email} (ID: {user_id})")

    # We need the user to be "logged in" or we use direct repository calls for simplicity in the simulation
    # Let's use httpx to hit the /listen/stream endpoint if available, or just use core logic
    # Since background extraction is async and involves LLM, we'll simulate it by calling MemoryProcessor directly
    
    from src.config import init_container, get_container
    await init_container()
    container = get_container()
    from src.engine.memory_processor import MemoryProcessor
    processor = await container.resolve(MemoryProcessor)
    
    content = "I am working on a secret project called 'Nebula'."
    
    print("\n1️⃣ Processing first instance of claim (should create DRAFT)...")
    memory, status_code = await processor.process_memory(
        user_id=user_id,
        content=content,
        status=MemoryStatus.DRAFT,
        confidence=0.4
    )
    print(f"   Stored memory status: {memory.status} (Confidence: {memory.confidence})")
    
    if memory.status != MemoryStatus.DRAFT:
        print("❌ Error: Memory should be DRAFT")
        return

    print("\n2️⃣ Processing second instance of similar claim (should consolidate & increase confidence)...")
    # Same user, similar content
    content_2 = "My main project right now is called Nebula."
    # We slightly vary content to test similarity
    memory_2, status_code_2 = await processor.process_memory(
        user_id=user_id,
        content=content_2,
        status=MemoryStatus.DRAFT,
        confidence=0.4 # New evidence
    )
    print(f"   Consolidated memory status: {memory_2.status} (Confidence: {memory_2.confidence})")
    
    if memory_2.id != memory.id:
        print("❌ Error: Should have consolidated into same memory ID")
        return

    print("\n3️⃣ Processing third instance (should RIPEN to ACTIVE)...")
    content_3 = "The Nebula project is almost done."
    memory_3, status_code_3 = await processor.process_memory(
        user_id=user_id,
        content=content_3,
        status=MemoryStatus.DRAFT,
        confidence=0.4
    )
    print(f"   Ripened memory status: {memory_3.status} (Confidence: {memory_3.confidence})")
    
    if memory_3.status == MemoryStatus.ACTIVE:
        print("\n✅ SUCCESS: Draft promoted to ACTIVE after maturation!")
    else:
        print(f"\n❌ FAILED: Memory status is still {memory_3.status}")

if __name__ == "__main__":
    asyncio.run(verify_maturation())
