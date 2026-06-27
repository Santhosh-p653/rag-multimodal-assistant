import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.vector_store import VectorStoreService


def test_vector_store_operations():
    # Initialize store
    service = VectorStoreService()
    service._collection_ready = True

    # Override instance client directly to avoid import timing issues
    mock_client = MagicMock()
    mock_client.count.return_value.count = 42

    mock_point = MagicMock()
    mock_point.score = 0.95
    mock_point.payload = {
        "chunk_id": "test_manual.pdf::chunk_0",
        "content": "Test content",
        "source_file": "test_manual.pdf",
    }
    mock_client.query_points.return_value.points = [mock_point]
    mock_client.scroll.return_value = ([mock_point], None)

    service.client = mock_client

    # Run checks
    assert service.count() == 42

    hits = service.search(query_vector=[0.1]*384, top_k=5)
    assert len(hits) == 1
    assert hits[0].score == 0.95

    chunks = service.get_all_chunks(source_file="test_manual.pdf")
    assert len(chunks) == 1
    assert chunks[0]["source_file"] == "test_manual.pdf"
