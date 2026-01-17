"""
Document Processor

Handles extraction and processing of multimodal documents (PDFs, images).
"""

import asyncio
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import structlog

from src.config import Settings, get_settings
from src.services.embedding import EmbeddingService, get_embedding_service
from src.storage.database import Database, get_database

logger = structlog.get_logger(__name__)


@dataclass
class DocumentChunk:
    """A chunk of extracted document content."""
    
    id: UUID = field(default_factory=uuid4)
    content: str = ""
    chunk_index: int = 0
    start_page: int | None = None
    end_page: int | None = None
    chunk_type: str = "text"  # text, table, image_description
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class ProcessedDocument:
    """Result of document processing."""
    
    file_id: UUID
    filename: str
    mime_type: str
    chunks: list[DocumentChunk] = field(default_factory=list)
    total_pages: int = 0
    total_chars: int = 0
    extraction_metadata: dict = field(default_factory=dict)
    processing_time_ms: int = 0


class DocumentProcessor:
    """
    Processes documents into memory-ready chunks.
    
    Supports:
    - PDF text extraction
    - PDF table extraction
    - Image OCR
    - Text chunking with overlap
    
    Flow:
    1. Extract content from document
    2. Split into semantic chunks
    3. Generate embeddings for each chunk
    4. Store chunks in database
    """
    
    def __init__(
        self,
        settings: Settings | None = None,
        db: Database | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.settings = settings or get_settings()
        self._db = db
        self._embedding_service = embedding_service
        self._chunk_size = self.settings.document_chunk_size
        self._chunk_overlap = self.settings.document_chunk_overlap
    
    async def _get_db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self._db = await get_database()
        return self._db
    
    async def _get_embedding_service(self) -> EmbeddingService:
        """Get embedding service instance."""
        if self._embedding_service is None:
            self._embedding_service = await get_embedding_service()
        return self._embedding_service
    
    async def process_pdf(
        self,
        file_id: UUID,
        user_id: UUID,
        file_data: bytes,
        filename: str,
    ) -> ProcessedDocument:
        """
        Process a PDF document.
        
        Args:
            file_id: Database file ID
            user_id: Owner user ID
            file_data: PDF file content
            filename: Original filename
            
        Returns:
            ProcessedDocument with extracted chunks
        """
        start_time = asyncio.get_event_loop().time()
        
        # Import pypdf lazily
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.error("pypdf not installed. Install with: pip install pypdf")
            raise
        
        # Try pdfplumber for tables
        try:
            import pdfplumber
            has_pdfplumber = True
        except ImportError:
            has_pdfplumber = False
            logger.warning("pdfplumber not installed, table extraction disabled")
        
        # Parse PDF
        pdf_stream = io.BytesIO(file_data)
        reader = PdfReader(pdf_stream)
        
        total_pages = len(reader.pages)
        all_text = []
        tables_extracted = 0
        
        # Extract text from each page
        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text:
                all_text.append({
                    "text": page_text,
                    "page": page_num,
                    "type": "text",
                })
        
        # Extract tables with pdfplumber
        if has_pdfplumber:
            pdf_stream.seek(0)
            with pdfplumber.open(pdf_stream) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if table:
                            # Convert table to markdown format
                            table_md = self._table_to_markdown(table)
                            if table_md:
                                all_text.append({
                                    "text": table_md,
                                    "page": page_num,
                                    "type": "table",
                                    "table_index": table_idx,
                                })
                                tables_extracted += 1
        
        # Combine all text
        full_text = "\n\n".join(item["text"] for item in all_text)
        
        # Chunk the text
        chunks = await self._create_chunks(
            full_text,
            source_items=all_text,
        )
        
        # Generate embeddings for chunks
        embedding_service = await self._get_embedding_service()
        chunk_texts = [c.content for c in chunks]
        
        if chunk_texts:
            embeddings = await embedding_service.embed_batch(chunk_texts)
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
        
        # Calculate processing time
        end_time = asyncio.get_event_loop().time()
        processing_time_ms = int((end_time - start_time) * 1000)
        
        result = ProcessedDocument(
            file_id=file_id,
            filename=filename,
            mime_type="application/pdf",
            chunks=chunks,
            total_pages=total_pages,
            total_chars=len(full_text),
            extraction_metadata={
                "tables_extracted": tables_extracted,
                "pages_with_text": len([t for t in all_text if t["type"] == "text"]),
            },
            processing_time_ms=processing_time_ms,
        )
        
        # Store chunks in database
        await self._store_chunks(file_id, user_id, chunks)
        
        logger.info(
            "PDF processed",
            file_id=str(file_id),
            pages=total_pages,
            chunks=len(chunks),
            time_ms=processing_time_ms,
        )
        
        return result
    
    async def process_image(
        self,
        file_id: UUID,
        user_id: UUID,
        file_data: bytes,
        filename: str,
        mime_type: str,
    ) -> ProcessedDocument:
        """
        Process an image with OCR.
        
        Args:
            file_id: Database file ID
            user_id: Owner user ID
            file_data: Image file content
            filename: Original filename
            mime_type: Image MIME type
            
        Returns:
            ProcessedDocument with OCR results
        """
        start_time = asyncio.get_event_loop().time()
        
        # Import dependencies lazily
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.error("pytesseract/Pillow not installed")
            raise
        
        # Configure tesseract path if set
        if self.settings.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_path
        
        # Load image
        image = Image.open(io.BytesIO(file_data))
        
        # Run OCR
        ocr_text = pytesseract.image_to_string(image)
        
        # Create chunks
        chunks = await self._create_chunks(ocr_text) if ocr_text.strip() else []
        
        # Generate embeddings
        if chunks:
            embedding_service = await self._get_embedding_service()
            chunk_texts = [c.content for c in chunks]
            embeddings = await embedding_service.embed_batch(chunk_texts)
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
        
        end_time = asyncio.get_event_loop().time()
        processing_time_ms = int((end_time - start_time) * 1000)
        
        result = ProcessedDocument(
            file_id=file_id,
            filename=filename,
            mime_type=mime_type,
            chunks=chunks,
            total_pages=1,
            total_chars=len(ocr_text),
            extraction_metadata={
                "ocr_confidence": "high" if len(ocr_text) > 50 else "low",
                "image_size": f"{image.width}x{image.height}",
            },
            processing_time_ms=processing_time_ms,
        )
        
        # Store chunks
        await self._store_chunks(file_id, user_id, chunks)
        
        logger.info(
            "Image processed",
            file_id=str(file_id),
            ocr_chars=len(ocr_text),
            chunks=len(chunks),
        )
        
        return result
    
    async def process_text(
        self,
        file_id: UUID,
        user_id: UUID,
        file_data: bytes,
        filename: str,
    ) -> ProcessedDocument:
        """Process a plain text or markdown file."""
        start_time = asyncio.get_event_loop().time()
        
        # Decode text
        try:
            text = file_data.decode("utf-8")
        except UnicodeDecodeError:
            text = file_data.decode("latin-1")
        
        # Create chunks
        chunks = await self._create_chunks(text)
        
        # Generate embeddings
        if chunks:
            embedding_service = await self._get_embedding_service()
            chunk_texts = [c.content for c in chunks]
            embeddings = await embedding_service.embed_batch(chunk_texts)
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
        
        end_time = asyncio.get_event_loop().time()
        processing_time_ms = int((end_time - start_time) * 1000)
        
        result = ProcessedDocument(
            file_id=file_id,
            filename=filename,
            mime_type="text/plain",
            chunks=chunks,
            total_pages=1,
            total_chars=len(text),
            extraction_metadata={},
            processing_time_ms=processing_time_ms,
        )
        
        await self._store_chunks(file_id, user_id, chunks)
        
        return result
    
    async def _create_chunks(
        self,
        text: str,
        source_items: list[dict] | None = None,
    ) -> list[DocumentChunk]:
        """
        Split text into semantic chunks.
        
        Uses overlapping chunks to preserve context.
        """
        if not text.strip():
            return []
        
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self._chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end
                search_start = max(start + self._chunk_size - 100, start)
                sentence_ends = [
                    text.rfind('. ', search_start, end + 50),
                    text.rfind('! ', search_start, end + 50),
                    text.rfind('? ', search_start, end + 50),
                    text.rfind('\n', search_start, end + 50),
                ]
                best_end = max(e for e in sentence_ends if e > 0) if any(e > 0 for e in sentence_ends) else -1
                
                if best_end > start:
                    end = best_end + 1
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Determine page info if available
                start_page = None
                end_page = None
                chunk_type = "text"
                
                if source_items:
                    # Find which source items this chunk covers
                    char_pos = 0
                    for item in source_items:
                        item_len = len(item["text"]) + 2  # +2 for \n\n separator
                        if char_pos <= start < char_pos + item_len:
                            start_page = item.get("page")
                            chunk_type = item.get("type", "text")
                        if char_pos <= end < char_pos + item_len:
                            end_page = item.get("page")
                        char_pos += item_len
                
                chunks.append(DocumentChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_page=start_page,
                    end_page=end_page,
                    chunk_type=chunk_type,
                ))
                chunk_index += 1
            
            # Move start with overlap
            start = end - self._chunk_overlap
            if start >= end:  # Prevent infinite loop
                start = end
        
        return chunks
    
    def _table_to_markdown(self, table: list[list]) -> str:
        """Convert a table to markdown format."""
        if not table or not table[0]:
            return ""
        
        lines = []
        
        # Header
        header = table[0]
        lines.append("| " + " | ".join(str(cell or "").strip() for cell in header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        
        # Rows
        for row in table[1:]:
            cells = [str(cell or "").strip() for cell in row]
            lines.append("| " + " | ".join(cells) + " |")
        
        return "\n".join(lines)
    
    async def _store_chunks(
        self,
        file_id: UUID,
        user_id: UUID,
        chunks: list[DocumentChunk],
    ) -> None:
        """Store chunks in the database."""
        if not chunks:
            return
        
        db = await self._get_db()
        
        query = """
            INSERT INTO document_chunks (
                id, file_id, user_id, content, chunk_index,
                start_page, end_page, embedding, embedding_generated, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        
        async with db.transaction() as conn:
            for chunk in chunks:
                await conn.execute(
                    query,
                    chunk.id,
                    file_id,
                    user_id,
                    chunk.content,
                    chunk.chunk_index,
                    chunk.start_page,
                    chunk.end_page,
                    chunk.embedding,
                    chunk.embedding is not None,
                    chunk.metadata,
                )
            
            # Update file processing status
            await conn.execute(
                """
                UPDATE files 
                SET processing_status = 'completed',
                    processed_at = NOW(),
                    total_chunks = $2,
                    chunks_processed = $2
                WHERE id = $1
                """,
                file_id,
                len(chunks),
            )
        
        logger.debug(f"Stored {len(chunks)} chunks for file {file_id}")


# Global processor instance
_processor: DocumentProcessor | None = None


async def get_document_processor() -> DocumentProcessor:
    """Get the global document processor instance."""
    global _processor
    
    if _processor is None:
        _processor = DocumentProcessor()
    
    return _processor
