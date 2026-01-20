import asyncio
import uuid
from src.engine.memory_processor import MemoryProcessor
from src.models.memory import MemoryType

async def verify_librarian():
    processor = MemoryProcessor()
    user_id = uuid.UUID("21f38efd-0e43-4314-96f7-c4195fc8290c")
    
    test_cases = [
        "Ich liebe Pizza mit Ananas", # Preference
        "Wie man eine Website mit React baut: 1. npx create-react-app...", # Procedural
        "Gestern war ich im Kino und habe Dune 2 gesehen", # Episodic
        "Die Hauptstadt von Frankreich ist Paris", # Semantic
    ]
    
    print("--- Testing Librarian Magic (Full Automation) ---")
    
    for content in test_cases:
        print(f"\nProcessing: '{content}'")
        # Simulate MCP / UI call without type/importance
        memory, status = await processor.process_memory(
            user_id=user_id,
            content=content,
            memory_type=None, 
            importance=None
        )
        print(f"Result: Type={memory.memory_type.value}, Importance={memory.importance}, Domain={memory.domain}, Category={memory.category}")
        print(f"Status: {status}")

if __name__ == "__main__":
    asyncio.run(verify_librarian())
