import asyncio
import os
import sys
from uuid import UUID
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath("."))

from src.tools.consolidate import consolidate_session
from src.engine.consolidation import get_consolidation_engine
from src.config import init_container

async def test_mcp_mimic():
    print("--- Initializing Container ---")
    await init_container()
    
    # Use the valid test user ID
    user_id = UUID("21f38efd-0e43-4314-96f7-c4195fc8290c")
    
    transcript = """
    User: Ich möchte heute über mein Projekt 'Knowwhere' sprechen.
    Assistant: Gerne, erzähl mir mehr.
    User: Wir nutzen Python und Supabase. Sarah macht das Design in Next.js.
    Assistant: Klingt gut.
    User: Das Ziel ist ein Zettelkasten-System. Max Mustermann hilft bei der Graphentheorie.
    """
    
    print(f"--- Running Consolidation for User {user_id} ---")
    try:
        # Mocking what main.py/FastMCP would pass or how it would look if called 
        # But wait, consolidate_session in tools/consolidate.py is just a function.
        # However, it expects a Context or uses dependency injection.
        # Actually, let's just use the engine and THEN manual mapping to ConsolidateOutput
        # to verify that mapping works.
        from src.models.requests import ConsolidateOutput, NewMemorySummary
        
        engine = await get_consolidation_engine()
        result = await engine.consolidate(
            user_id=user_id,
            session_transcript=transcript,
            conversation_id="test_mimic_123"
        )
        
        print(f"Engine Status: {result.status}")
        print(f"Engine Error: {result.error_message}")
        
        # Test mapping logic as found in consolidate_session tool
        output = ConsolidateOutput(
            consolidation_id=result.consolidation_id,
            new_memories_count=result.new_memories_count,
            new_memories=[], # simplified for test
            merged_count=result.merged_count,
            conflicts_resolved=result.conflicts_resolved,
            edges_created=result.edges_created,
            patterns_detected=result.patterns_detected,
            processing_time_ms=result.processing_time_ms,
            status=result.status.value,
            error_message=result.error_message,
        )
        
        print("--- Tool Output Mapping ---")
        print(output.model_dump_json(indent=2))
        
    except Exception as e:
        import traceback
        print(f"CRASH: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_mimic())
