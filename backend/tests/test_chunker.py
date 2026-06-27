import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.chunker import chunk_markdown


def test_chunk_markdown_structure():
    # Construct a test content string longer than CHUNK_SIZE (500 chars)
    text = "A" * 900
    metadata = {
        "product": "X100",
        "category": "Printer",
    }
    
    chunks = chunk_markdown(text, source_file="manual.txt", metadata=metadata)
    
    assert len(chunks) == 3  # 900 chars split into ~500 size chunks with overlap (0-500, 400-900, 800-900)
    
    for i, chunk in enumerate(chunks):
        assert chunk["source_file"] == "manual.txt"
        assert chunk["product"] == "X100"
        assert chunk["category"] == "Printer"
        assert chunk["chunk_id"] == f"manual.txt::chunk_{i}"
        assert len(chunk["content"]) <= 500
