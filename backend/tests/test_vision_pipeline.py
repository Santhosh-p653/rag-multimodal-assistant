"""
test_vision_pipeline.py — Unit tests for SigLIP 2 Vision Embedding & Parallel Retrieval Pipeline.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

# Unmock qdrant_client and sentence_transformers if conftest mocked them globally
for mod_name in ["qdrant_client", "qdrant_client.models", "sentence_transformers"]:
    if mod_name in sys.modules and isinstance(sys.modules[mod_name], MagicMock):
        del sys.modules[mod_name]

import qdrant_client
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings
from app.services.retriever import retrieve_context, retrieve_context_with_vision
from app.services.vector_store import VectorStoreService
from app.services.vision_embedder import VisionEmbedderService
from app.services.vision_search import search_similar_images


@pytest.fixture(autouse=True)
def reset_vector_store_singleton():
    """Ensure clean real QdrantClient in-memory VectorStore instance."""
    for mod_name in ["qdrant_client", "qdrant_client.models"]:
        if mod_name in sys.modules and isinstance(sys.modules[mod_name], MagicMock):
            del sys.modules[mod_name]

    import qdrant_client
    import qdrant_client.models
    import app.services.metadata_resolver
    import app.services.vector_store
    import app.services.vision_search

    app.services.vector_store.QdrantClient = qdrant_client.QdrantClient
    app.services.vector_store.VectorParams = qdrant_client.models.VectorParams
    app.services.vector_store.Distance = qdrant_client.models.Distance
    app.services.vector_store.PointStruct = qdrant_client.models.PointStruct
    app.services.vector_store.Filter = qdrant_client.models.Filter
    app.services.vector_store.FieldCondition = qdrant_client.models.FieldCondition
    app.services.vector_store.MatchValue = qdrant_client.models.MatchValue

    app.services.metadata_resolver.Filter = qdrant_client.models.Filter
    app.services.metadata_resolver.FieldCondition = qdrant_client.models.FieldCondition
    app.services.metadata_resolver.MatchValue = qdrant_client.models.MatchValue

    app.services.vision_search.Filter = qdrant_client.models.Filter

    VectorStoreService._instance = None
    VectorStoreService(db_path=":memory:")

    yield

    if VectorStoreService._instance and hasattr(
        VectorStoreService._instance, "client"
    ):
        try:
            VectorStoreService._instance.client.close()
        except Exception:  # noqa: BLE001
            pass

    VectorStoreService._instance = None


@pytest.fixture
def sample_pil_image(tmp_path):
    img_path = str(tmp_path / "test_diagram.png")
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))

    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.text(
        (10, 10),
        "Cooling fan diagram printer rear",
        fill=(0, 0, 0),
    )
    draw.line(
        (0, 0, 300, 300),
        fill=(0, 0, 0),
        width=5,
    )
    img.save(img_path)

    return img_path


def test_vision_embedder_singleton():
    service1 = VisionEmbedderService()
    service2 = VisionEmbedderService()

    assert service1 is service2


def test_vision_embedder_text():
    embedder = VisionEmbedderService()
    vec = embedder.embed_text("Printer cooling fan troubleshooting diagram")

    assert isinstance(vec, list)
    assert len(vec) > 0

    # Vectors should be L2-normalized (magnitude approx 1.0)
    mag = sum(x**2 for x in vec) ** 0.5
    assert abs(mag - 1.0) < 1e-3


def test_vision_embedder_image(sample_pil_image):
    embedder = VisionEmbedderService()
    vec = embedder.embed_image(sample_pil_image)

    assert isinstance(vec, list)
    assert len(vec) > 0

    mag = sum(x**2 for x in vec) ** 0.5
    assert abs(mag - 1.0) < 1e-3


def test_vision_vector_store_ingestion_and_search(sample_pil_image):
    embedder = VisionEmbedderService()
    vector_store = VectorStoreService()

    img_vec = embedder.embed_text("Printer cooling fan diagram")

    test_record = {
        "image_id": "test_doc_p1_img1",
        "source_file": "test_vision_manual.pdf",
        "page_number": 1,
        "image_path": sample_pil_image,
        "nearby_text": "Figure 1: Printer rear cooling fan diagram",
        "caption": "Printer cooling fan diagram",
        "product": "X100",
        "model": "X100",
        "vision_embedding": img_vec,
    }

    # Ingest into manual_images collection
    vector_store.ingest_images([test_record])
    assert (
        vector_store.client.count("manual_images").count == 1
    ), "Image failed to upsert into Qdrant"

    # Search via vision_search service without filter first
    results_unfiltered = search_similar_images("cooling fan diagram")

    assert isinstance(results_unfiltered, list)
    assert len(results_unfiltered) > 0, "Unfiltered search returned empty"

    # Search with source_file filter
    results = search_similar_images(
        "cooling fan diagram",
        source_file="test_vision_manual.pdf",
    )

    assert isinstance(results, list)
    assert len(results) > 0, "Filtered search returned empty"
    assert results[0]["image_id"] == "test_doc_p1_img1"
    assert "vision_score" in results[0]

    # Clean up
    vector_store.delete_images_by_filename("test_vision_manual.pdf")


def test_retrieve_context_with_vision_compatibility(sample_pil_image):
    embedder = VisionEmbedderService()
    vector_store = VectorStoreService()

    # Setup dummy chunk and dummy vision image
    vector_store.ingest_chunks(
        [
            {
                "chunk_id": "test_vision_manual.pdf::chunk_0",
                "content": (
                    "To fix cooling fan Error E105 on X100, "
                    "replace rear cable."
                ),
                "source_file": "test_vision_manual.pdf",
                "product": "X100",
                "model": "X100",
                "embedding": [0.01] * 384,
            }
        ]
    )

    img_vec = embedder.embed_text("X100 cooling fan rear view")

    vector_store.ingest_images(
        [
            {
                "image_id": "test_doc_p1_vec1",
                "source_file": "test_vision_manual.pdf",
                "page_number": 1,
                "image_path": sample_pil_image,
                "nearby_text": "X100 cooling fan rear view",
                "product": "X100",
                "model": "X100",
                "vision_embedding": img_vec,
            }
        ]
    )

    # Execute extended retrieval
    chunks, conf, vision_hits = retrieve_context_with_vision(
        "cooling fan error",
        source_file="test_vision_manual.pdf",
    )

    assert isinstance(chunks, list)
    assert isinstance(conf, str)
    assert isinstance(vision_hits, list)

    # Cleanup
    vector_store.delete_by_filename("test_vision_manual.pdf")
    vector_store.delete_images_by_filename("test_vision_manual.pdf")