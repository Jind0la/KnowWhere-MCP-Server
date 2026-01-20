import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Setup mocking before imports if possible, or just patch after
mock_llm = AsyncMock()
mock_llm.check_for_contradiction = AsyncMock(return_value=True)
mock_llm.classify_content = AsyncMock(return_value={"domain": "Test", "category": "Test"})

mock_embed = AsyncMock()
mock_embed.embed = AsyncMock(return_value=[0.1]*1408)

async def main():
    print("--- Starting Hygiene Verification ---")
    
    # We patch the service getters broadly
    with patch("src.services.llm.get_llm_service", return_value=mock_llm), \
         patch("src.services.embedding.get_embedding_service", return_value=mock_embed):
        
        from src.engine.memory_processor import MemoryProcessor
        from src.models.memory import Memory, MemoryType, MemoryStatus
        
        processor = MemoryProcessor()
        user_id = uuid4()
        
        # Mock Repo
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock(id=uuid4()))
        mock_repo.update = AsyncMock(return_value=MagicMock(id=uuid4()))
        
        # Case 1: Deduplication
        print("\nTesting Deduplication...")
        mock_sim = MagicMock()
        mock_sim.id = uuid4()
        mock_sim.similarity = 0.99
        mock_sim.access_count = 5
        mock_repo.search_similar = AsyncMock(return_value=[mock_sim])
        processor._get_memory_repo = AsyncMock(return_value=mock_repo)
        
        result = await processor.process_memory(user_id, "Duplicate", MemoryType.SEMANTIC)
        print(f"Deduplication result: {result.id == mock_sim.id}")
        
        # Case 2: Conflict
        print("\nTesting Conflict Resolution...")
        mock_sim.similarity = 0.85
        mock_sim.content = "I use Cursor"
        mock_sim.domain = "IDE"
        mock_sim.category = "Tools"
        
        # Patch Edge Repo and Entity Hub
        with patch("src.engine.memory_processor.EdgeRepository") as mock_edge_repo, \
             patch("src.engine.memory_processor.get_entity_hub_service") as mock_get_entity:
            
            mock_edge_instance = MagicMock()
            mock_edge_instance.create = AsyncMock()
            mock_edge_repo.return_value = mock_edge_instance
            
            mock_entity_hub = AsyncMock()
            mock_get_entity.return_value = mock_entity_hub
            
            result = await processor.process_memory(user_id, "I use Antigravity (contradict)", MemoryType.PREFERENCE)
            print(f"Conflict resolution triggered: {mock_edge_instance.create.called}")

    print("\n--- Verification Finished ---")

if __name__ == "__main__":
    asyncio.run(main())
