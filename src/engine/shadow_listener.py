"""
Shadow Listener Engine

Proactively listens to conversation streams and extracts memories in the background.
"""

import asyncio
from typing import Dict, List, Optional
from uuid import UUID
import structlog
from datetime import datetime

from src.models.memory import MemoryType, MemoryStatus, MemorySource
from src.engine.memory_processor import MemoryProcessor
from src.services.llm import LLMService

logger = structlog.get_logger(__name__)

class ThoughtBuffer:
    """
    Accumulates conversation chunks until semantic stability is reached.
    """
    def __init__(self, ttl_seconds: int = 300):
        self.buffers: Dict[str, List[Dict]] = {}
        self.last_update: Dict[str, datetime] = {}
        self.ttl = ttl_seconds

    def add_chunk(self, conversation_id: str, role: str, content: str):
        if conversation_id not in self.buffers:
            self.buffers[conversation_id] = []
        
        self.buffers[conversation_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow()
        })
        self.last_update[conversation_id] = datetime.utcnow()

    def get_full_text(self, conversation_id: str) -> str:
        chunks = self.buffers.get(conversation_id, [])
        return "\n".join([f"{c['role'].upper()}: {c['content']}" for c in chunks])

    def clear(self, conversation_id: str):
        self.buffers.pop(conversation_id, None)
        self.last_update.pop(conversation_id, None)

    async def cleanup_loop(self):
        """Periodically cleanup stale buffers."""
        while True:
            now = datetime.utcnow()
            stale_ids = [
                cid for cid, last in self.last_update.items()
                if (now - last).total_seconds() > self.ttl
            ]
            for cid in stale_ids:
                logger.debug("Cleaning up stale thought buffer", conversation_id=cid)
                self.clear(cid)
            await asyncio.sleep(60)

class ShadowListener:
    """
    Background listener that processes thought buffers and manages memory maturation.
    """
    def __init__(self, processor: MemoryProcessor, llm_service: LLMService):
        self.processor = processor
        self.llm = llm_service
        self.buffer = ThoughtBuffer()
        self._processing_lock = asyncio.Lock()

    async def listen(self, user_id: UUID, conversation_id: str, role: str, chunk: str):
        """
        Main entry point for incoming conversation chunks.
        """
        self.buffer.add_chunk(conversation_id, role, chunk)
        
        # Heuristic: Process every 3-5 chunks or if we see signs of completion
        # For simplicity in first version, we process on potential "Librarian moments"
        if self._is_ripe_for_extraction(chunk):
            asyncio.create_task(self._extract_memories(user_id, conversation_id))

    def _is_ripe_for_extraction(self, chunk: str) -> bool:
        """
        Heuristic to decide if we should run extraction now.
        """
        markers = ["?", "!", ".", "\n"]
        # If it's a decent sized chunk and ends with punctuation
        return len(chunk) > 20 and any(chunk.strip().endswith(m) for m in markers)

    async def _extract_memories(self, user_id: UUID, conversation_id: str):
        """
        Runs the extraction logic on the accumulated buffer.
        """
        async with self._processing_lock:
            context = self.buffer.get_full_text(conversation_id)
            if not context:
                return

            logger.info("Shadow Listener running extraction", conversation_id=conversation_id)
            
            # 1. Ask LLM to extract "User Claims" vs "Assistant Context"
            extractions = await self._analyze_conversation(context)
            
            for ext in extractions:
                content = ext.get("content")
                if not content: continue
                
                # Role-based confidence
                base_confidence = 0.5 if ext.get("role") == "user" else 0.3
                
                # 2. Process via MemoryProcessor as DRAFT
                memory, status = await self.processor.process_memory(
                    user_id=user_id,
                    content=content,
                    status=MemoryStatus.DRAFT,
                    confidence=base_confidence,
                    source=MemorySource.CONVERSATION,
                    source_id=conversation_id,
                    metadata={
                        "shadow_extracted": True,
                        "extraction_role": ext.get("role"),
                        "original_context_tail": context[-200:]
                    }
                )
                logger.info("Shadow Listener created draft memory", memory_id=str(memory.id), user_id=str(user_id))

    async def _analyze_conversation(self, context: str) -> List[Dict]:
        """
        Uses LLM to find potential memories in the stream.
        """
        system_prompt = (
            "You are the KnowWhere Librarian. Your job is to listen to the conversation "
            "and extract things the user said about themselves (facts, preferences) "
            "or things learned during the session. "
            "Return a JSON list of objects: {\"content\": \"...\", \"role\": \"user|assistant\", \"reason\": \"...\"}"
        )
        
        # We use a concise prompt to minimize latency
        user_prompt = f"Analyze this conversation snippet and extract key memories:\n\n{context}\n\nStrict JSON output only."
        
        try:
            # Note: complete() should handle JSON parsing or we do it here.
            # Assuming LLMService.complete returns a string.
            response = await self.llm.complete(user_prompt, system_prompt)
            # Simple parser or let's assume it works for now
            import json
            import re
            
            # Clean possible markdown wrap
            match = re.search(r"\[.*\]", response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return []
        except Exception as e:
            logger.error("Shadow Listener LLM extraction failed", error=str(e))
            return []
