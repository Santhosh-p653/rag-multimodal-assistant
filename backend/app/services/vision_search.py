"""
vision_search.py — Service for semantic text-to-image and image-to-image retrieval using SigLIP 2 Vision Embeddings.
Queries the dedicated 'manual_images' Qdrant vector collection.
Supports:
1. Text query -> Image retrieval (Text-to-Image)
2. Image query -> Image retrieval (Image-to-Image nearest neighbor)
3. Multimodal query (Text + Image) -> Hybrid fusion retrieval
"""
import io
import base64
import logging
from typing import List, Dict, Any, Optional
from PIL import Image

from app.services.vision_embedder import VisionEmbedderService
from app.services.vector_store import VectorStoreService
from app.services.metadata_resolver import resolve_metadata_filter
from app.config import settings, VISION_TOP_K

logger = logging.getLogger(__name__)


def search_similar_images(
    query: Optional[str] = None,
    query_image_base64: Optional[str] = None,
    query_image_bytes: Optional[bytes] = None,
    top_k: int = VISION_TOP_K,
    source_file: Optional[str] = None,
    query_entities: Optional[dict] = None
) -> List[Dict[str, Any]]:
    """
    Search against the manual_images collection using SigLIP 2 embeddings.
    Accepts text query, image query (base64 or bytes), or both.
    Returns a list of dicts with matching image metadata and similarity scores.
    """
    if not settings.ENABLE_VISION_SEARCH:
        logger.info("[VisionSearch] Vision search is disabled in settings.")
        return []

    has_text = bool(query and query.strip())
    has_image = bool(query_image_base64 or query_image_bytes)

    if not has_text and not has_image:
        return []

    try:
        embedder = VisionEmbedderService()
        vector_store = VectorStoreService()

        # Resolve metadata filter if query entities are present
        query_filter = None
        if query_entities:
            query_filter = resolve_metadata_filter(query_entities, filter_level=1)
            if not query_filter:
                query_filter = resolve_metadata_filter(query_entities, filter_level=2)

        min_score = getattr(settings, "VISION_SCORE_THRESHOLD", 0.0)

        # ── Case A: Image-only or Multimodal (Image vector search) ───────────
        img_hits = []
        if has_image:
            try:
                raw_bytes = query_image_bytes
                if not raw_bytes and query_image_base64:
                    clean_b64 = query_image_base64
                    if "," in clean_b64:
                        clean_b64 = clean_b64.split(",", 1)[1]
                    raw_bytes = base64.b64decode(clean_b64)

                if raw_bytes:
                    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
                    img_vector = embedder.embed_image(pil_img)
                    if img_vector:
                        img_hits = vector_store.search_images(
                            query_vector=img_vector,
                            top_k=top_k,
                            source_file=source_file,
                            query_filter=query_filter
                        )
            except Exception as img_err:
                logger.warning(f"[VisionSearch] Image query embedding failed: {img_err}")

        # ── Case B: Text vector search ───────────────────────────────────────
        text_hits = []
        if has_text:
            text_vector = embedder.embed_text(query)
            if text_vector:
                text_hits = vector_store.search_images(
                    query_vector=text_vector,
                    top_k=top_k,
                    source_file=source_file,
                    query_filter=query_filter
                )

        # ── Case C: Reciprocal Rank Fusion (RRF) if both hits exist ──────────
        def _hit_to_dict(hit, score_override=None):
            return {
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
                "vision_score": round(score_override if score_override is not None else hit.score, 4),
            }

        if img_hits and text_hits:
            # Reciprocal rank fusion (k=60)
            k = 60
            scores: Dict[str, float] = {}
            hit_map = {}

            for rank, hit in enumerate(img_hits, start=1):
                key = hit.payload.get("image_id") or str(hit.id)
                scores[key] = scores.get(key, 0.0) + (1.0 / (k + rank))
                hit_map[key] = hit

            for rank, hit in enumerate(text_hits, start=1):
                key = hit.payload.get("image_id") or str(hit.id)
                scores[key] = scores.get(key, 0.0) + (1.0 / (k + rank))
                if key not in hit_map:
                    hit_map[key] = hit

            sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]
            results = [_hit_to_dict(hit_map[k], score_override=scores[k]) for k in sorted_keys]
        elif img_hits:
            results = [_hit_to_dict(hit) for hit in img_hits if not (min_score and hit.score < min_score)]
        elif text_hits:
            results = [_hit_to_dict(hit) for hit in text_hits if not (min_score and hit.score < min_score)]
        else:
            results = []

        logger.info(f"[VisionSearch] Found {len(results)} matching images (has_image={has_image}, has_text={has_text}).")
        return results

    except Exception as e:
        logger.error(f"[VisionSearch] Vision search failed gracefully: {e}")
        return []

