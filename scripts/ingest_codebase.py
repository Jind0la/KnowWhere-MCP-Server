#!/usr/bin/env python3
"""
Codebase Ingestion Script

Reads all code files from a directory and stores them as memories in KnowWhere.
Each file is chunked intelligently (by functions/classes for Python, or by size).
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from uuid import UUID, uuid4

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Settings
from src.storage.database import Database
from src.storage.repositories.memory_repo import MemoryRepository
from src.services.embedding import EmbeddingService
from src.models.memory import MemoryCreate, MemoryType, MemorySource


# File extensions to process
CODE_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript', 
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
    '.rs': 'rust',
    '.go': 'go',
    '.java': 'java',
    '.cpp': 'cpp',
    '.c': 'c',
    '.h': 'c',
    '.hpp': 'cpp',
    '.md': 'markdown',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.json': 'json',
    '.toml': 'toml',
    '.sql': 'sql',
    '.sh': 'shell',
    '.bash': 'shell',
}

# Directories to skip
SKIP_DIRS = {
    '__pycache__', 'node_modules', '.git', '.venv', 'venv', 
    'env', '.env', 'dist', 'build', '.pytest_cache', 
    '.mypy_cache', 'htmlcov', '.tox', 'eggs', '*.egg-info',
    'supabase', '.cursor', '.idea', '.vscode'
}

# Max chunk size (characters)
MAX_CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200


def should_skip_dir(dirname: str) -> bool:
    """Check if directory should be skipped."""
    return dirname in SKIP_DIRS or dirname.startswith('.')


def extract_python_chunks(content: str, filepath: str) -> list[dict]:
    """Extract chunks from Python files by function/class."""
    chunks = []
    
    # Pattern to match function and class definitions
    pattern = r'^((?:async\s+)?def\s+\w+|class\s+\w+)'
    
    lines = content.split('\n')
    current_chunk = []
    current_name = filepath
    chunk_start = 0
    
    for i, line in enumerate(lines):
        match = re.match(pattern, line)
        
        if match and current_chunk:
            # Save previous chunk
            chunk_content = '\n'.join(current_chunk)
            if chunk_content.strip():
                chunks.append({
                    'content': chunk_content,
                    'name': current_name,
                    'start_line': chunk_start + 1,
                    'end_line': i,
                })
            current_chunk = []
            current_name = match.group(1)
            chunk_start = i
        
        current_chunk.append(line)
    
    # Don't forget last chunk
    if current_chunk:
        chunk_content = '\n'.join(current_chunk)
        if chunk_content.strip():
            chunks.append({
                'content': chunk_content,
                'name': current_name,
                'start_line': chunk_start + 1,
                'end_line': len(lines),
            })
    
    # If chunks are too big, split them further
    final_chunks = []
    for chunk in chunks:
        if len(chunk['content']) > MAX_CHUNK_SIZE:
            # Split by size with overlap
            text = chunk['content']
            for j in range(0, len(text), MAX_CHUNK_SIZE - CHUNK_OVERLAP):
                sub_content = text[j:j + MAX_CHUNK_SIZE]
                if sub_content.strip():
                    final_chunks.append({
                        'content': sub_content,
                        'name': f"{chunk['name']} (part {j // (MAX_CHUNK_SIZE - CHUNK_OVERLAP) + 1})",
                        'start_line': chunk['start_line'],
                        'end_line': chunk['end_line'],
                    })
        else:
            final_chunks.append(chunk)
    
    return final_chunks


def extract_generic_chunks(content: str, filepath: str) -> list[dict]:
    """Extract chunks from any file by size."""
    chunks = []
    
    if len(content) <= MAX_CHUNK_SIZE:
        return [{'content': content, 'name': filepath, 'start_line': 1, 'end_line': content.count('\n') + 1}]
    
    # Split by size with overlap
    for i in range(0, len(content), MAX_CHUNK_SIZE - CHUNK_OVERLAP):
        chunk_content = content[i:i + MAX_CHUNK_SIZE]
        if chunk_content.strip():
            chunks.append({
                'content': chunk_content,
                'name': f"{filepath} (part {i // (MAX_CHUNK_SIZE - CHUNK_OVERLAP) + 1})",
                'start_line': 1,
                'end_line': chunk_content.count('\n') + 1,
            })
    
    return chunks


def get_file_chunks(filepath: Path, base_path: Path) -> list[dict]:
    """Get chunks from a file."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return []  # Skip binary files
    
    if not content.strip():
        return []
    
    relative_path = str(filepath.relative_to(base_path))
    ext = filepath.suffix.lower()
    
    # Use Python-specific chunking for .py files
    if ext == '.py':
        chunks = extract_python_chunks(content, relative_path)
    else:
        chunks = extract_generic_chunks(content, relative_path)
    
    # Add metadata to each chunk
    for chunk in chunks:
        chunk['filepath'] = relative_path
        chunk['language'] = CODE_EXTENSIONS.get(ext, 'text')
        chunk['extension'] = ext
    
    return chunks


async def ingest_codebase(
    codebase_path: str,
    user_email: str = "codebase@knowwhere.ai",
    project_name: str = "codebase",
):
    """Ingest a codebase into KnowWhere."""
    
    print(f"🚀 Starting codebase ingestion: {codebase_path}")
    print(f"   Project: {project_name}")
    print(f"   User: {user_email}")
    
    base_path = Path(codebase_path)
    if not base_path.exists():
        print(f"❌ Path does not exist: {codebase_path}")
        return
    
    # Initialize services
    settings = Settings()
    db = Database(settings)
    await db.connect()
    
    # Create/get user
    user_id = uuid4()
    await db.execute('''
        INSERT INTO users (id, email, tier)
        VALUES ($1, $2, $3)
        ON CONFLICT (email) DO UPDATE SET updated_at = NOW()
        RETURNING id
    ''', user_id, user_email, 'pro')
    
    # Get actual user ID
    user_row = await db.fetchrow("SELECT id FROM users WHERE email = $1", user_email)
    user_id = user_row['id']
    print(f"👤 User ID: {user_id}")
    
    embedding_service = EmbeddingService(settings=settings)
    repo = MemoryRepository(db)
    
    # Collect all files
    all_chunks = []
    file_count = 0
    
    for root, dirs, files in os.walk(base_path):
        # Filter directories
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        
        for filename in files:
            filepath = Path(root) / filename
            ext = filepath.suffix.lower()
            
            if ext not in CODE_EXTENSIONS:
                continue
            
            chunks = get_file_chunks(filepath, base_path)
            if chunks:
                all_chunks.extend(chunks)
                file_count += 1
    
    print(f"📁 Found {file_count} files with {len(all_chunks)} chunks")
    
    # Process chunks in batches
    batch_size = 10
    stored_count = 0
    
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        
        # Generate embeddings for batch
        texts = [f"{c['filepath']}: {c['name']}\n\n{c['content']}" for c in batch]
        
        try:
            embeddings = await embedding_service.embed_batch(texts)
        except Exception as e:
            print(f"⚠️ Embedding error: {e}")
            continue
        
        # Store each chunk
        for chunk, embedding in zip(batch, embeddings):
            try:
                memory = await repo.create(MemoryCreate(
                    user_id=user_id,
                    content=f"[{chunk['language'].upper()}] {chunk['filepath']}\n\n{chunk['content']}",
                    memory_type=MemoryType.SEMANTIC,  # Code is semantic/factual knowledge
                    embedding=embedding,
                    entities=[project_name, chunk['language'], chunk['filepath'].split('/')[0] if '/' in chunk['filepath'] else project_name],
                    importance=5,
                    source=MemorySource.DOCUMENT,
                    metadata={
                        'filepath': chunk['filepath'],
                        'language': chunk['language'],
                        'chunk_name': chunk['name'],
                        'start_line': chunk['start_line'],
                        'end_line': chunk['end_line'],
                        'project': project_name,
                    }
                ))
                stored_count += 1
            except Exception as e:
                print(f"⚠️ Store error for {chunk['filepath']}: {e}")
        
        print(f"   Processed {min(i + batch_size, len(all_chunks))}/{len(all_chunks)} chunks...")
    
    await db.disconnect()
    
    print(f"\n✅ Ingestion complete!")
    print(f"   📁 Files processed: {file_count}")
    print(f"   📝 Chunks stored: {stored_count}")
    print(f"   🔍 You can now search your codebase with semantic queries!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest a codebase into KnowWhere")
    parser.add_argument("path", help="Path to codebase directory")
    parser.add_argument("--project", "-p", default="codebase", help="Project name for tagging")
    parser.add_argument("--user", "-u", default="codebase@knowwhere.ai", help="User email")
    
    args = parser.parse_args()
    
    asyncio.run(ingest_codebase(args.path, args.user, args.project))
