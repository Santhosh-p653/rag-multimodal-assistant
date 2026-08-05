"""
vision_search.py — Service for semantic text-to-image retrieval using SigLIP 2 Vision Embeddings.
Queries the dedicated 'manual_images' Qdrant vector collection.
"""
from typing import List, Dict, Any, Optional
from app.services.vision_embedder import VisionEmbedderService
from app.services.vector_store import VectorStoreService
from app.services.metadata_resolver import resolve_metadata_filter
from app.config import settings, VISION_TOP_K

def search_similar_images(
    query: str,
    top_k: int = VISION_TOP_K,
    source_file: Optional[str] = None,
    query_entities: Optional[dict] = None
) -> List[Dict[str, Any]]:
    """
    Encode the raw text query with SigLIP text encoder and search against the manual_images collection.
    Returns a list of dicts with matching image metadata and similarity scores.
    """
    if not settings.ENABLE_VISION_SEARCH:
        print("[VisionSearch] Vision search is disabled in settings.")
        return []

    if not query or not query.strip():
        return []

    try:
        embedder = VisionEmbedderService()
        vector_store = VectorStoreService()

        # 1. Encode text query using SigLIP 2 Text Encoder
        query_vector = embedder.embed_text(query)
        if not query_vector:
            return []

        # 2. Resolve metadata filter if query entities are present
        query_filter = None
        if query_entities:
            query_filter = resolve_metadata_filter(query_entities, filter_level=1)
            if not query_filter:
                query_filter = resolve_metadata_filter(query_entities, filter_level=2)

        # 3. Query Qdrant manual_images collection
        hits = vector_store.search_images(
            query_vector=query_vector,
            top_k=top_k,
            source_file=source_file,
            query_filter=query_filter
        )

        results = []
        min_score = getattr(settings, "VISION_SCORE_THRESHOLD", 0.0)
        for hit in hits:
            if min_score and min_score > 0 and hit.score < min_score:
                continue
            results.append({
                    "image_id":     hit.payload.get("image_id"),
                    "document_id":  hit.payload.get("source_file"),
                    "source_file":  hit.payload.get("source_file"),
                    "page_number":  hit.payload.get("page_number"),
                    "bounding_box": hit.payload.get("bounding_box"),
                    "image_path":   hit.payload.get("image_path"),
                    "nearby_text":  hit.payload.get("nearby_text", ""),
                    "caption":      hit.payload.get("caption", ""),
                    "product":      hit.payload.get("product"),
                    "model":        hit.payload.get("model"),
                    "image_type":   hit.payload.get("image_type", "raster"),
                    "vision_score": round(hit.score, 4),
                })

        print(f"[VisionSearch] Found {len(results)} vision matching images for query '{query[:30]}...'.")
        return results

    except Exception as e:
        print(f"[VisionSearch] Vision search failed gracefully: {e}")
        return []
