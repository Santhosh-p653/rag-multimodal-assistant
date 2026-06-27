"""
chunker.py — Splits markdown text into overlapping chunks for RAG ingestion.
Uses character-level splitting with configurable size and overlap.
"""
from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_markdown(text: str, source_file: str, metadata: dict = None) -> list[dict]:
    """
    Split a markdown string into overlapping chunks.

    Args:
        text:        The full markdown content.
        source_file: Original filename, stored in chunk metadata.
        metadata:    Dict containing document-level metadata (product, model, category, etc.)

    Returns:
        List of dicts: { chunk_id, content, source_file, ...metadata }
    """
    chunks = []
    start = 0
    chunk_index = 0
    text = text.strip()
    
    meta = metadata or {}

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end].strip()

        if chunk_text:
            chunk_data = {
                "chunk_id": f"{source_file}::chunk_{chunk_index}",
                "content": chunk_text,
                "source_file": source_file,
            }
            # Inject metadata fields
            chunk_data.update(meta)
            chunks.append(chunk_data)
            chunk_index += 1

        # Advance by (CHUNK_SIZE - CHUNK_OVERLAP) to create overlap
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks
