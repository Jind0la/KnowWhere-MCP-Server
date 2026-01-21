import asyncio
import uuid
import structlog
from src.services.llm import get_llm_service
from src.models.memory import MemoryType

async def test_meta_extraction():
    print("Testing Meta-Knowledge Extraction...")
    llm = await get_llm_service()
    
    # Transcript with clear meta-knowledge (feedback/calibration/learning)
    transcript = """
    User: Deine Erklärungen sind mir oft etwas zu langatmig. Bitte komm schneller zum Punkt.
    Assistant: Verstanden, ich werde mich kürzer fassen.
    User: Danke. Außerdem habe ich gemerkt, dass ich bei Datenbank-Konzepten eher visuelle Analogien brauche, um es wirklich zu verstehen.
    Assistant: Das ist ein guter Hinweis. Ich werde für DB-Themen mehr Analogien verwenden.
    User: Super! Ich arbeite übrigens gerade an der Optimierung meiner SQL-Queries, aber ich tue mich mit Indexen noch schwer.
    """
    
    claims = await llm.extract_claims(transcript)
    
    print(f"\nExtracted {len(claims)} claims:")
    meta_count = 0
    for c in claims:
        print(f"- Claim: {c.claim}")
        print(f"  Type: {c.claim_type}")
        print(f"  Importance: {c.importance}")
        if c.claim_type == MemoryType.META:
            meta_count += 1
            
    if meta_count > 0:
        print(f"\n✅ SUCCESS: Found {meta_count} meta-knowledge claims!")
    else:
        print("\n❌ FAILURE: No meta-knowledge claims found.")

if __name__ == "__main__":
    asyncio.run(test_meta_extraction())
