"""
Memory Engine - Business Logic Layer

Core components:
- MemoryProcessor: Processes different memory types
- ConsolidationEngine: Consolidates session transcripts into memories
- EntityExtractor: Extracts entities from content
- KnowledgeGraph: Manages relationships between memories
- DocumentProcessor: Processes PDFs, images, and text files
"""

from src.engine.memory_processor import MemoryProcessor
from src.engine.consolidation import ConsolidationEngine
from src.engine.entity_extractor import EntityExtractor
from src.engine.knowledge_graph import KnowledgeGraphManager
from src.engine.document_processor import DocumentProcessor, get_document_processor

__all__ = [
    "MemoryProcessor",
    "ConsolidationEngine",
    "EntityExtractor",
    "KnowledgeGraphManager",
    "DocumentProcessor",
    "get_document_processor",
]
