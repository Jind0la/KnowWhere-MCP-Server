import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.llm import get_llm_service

async def test_llm():
    print("Getting LLM service...")
    try:
        llm = await get_llm_service()
        print("LLM Service initialized.")
        
        print("Testing complete...")
        res = await llm.complete("Hello", "You are a test bot.")
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm())
