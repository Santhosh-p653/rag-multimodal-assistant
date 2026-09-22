import asyncio
from functools import lru_cache
from typing import Optional, Tuple, List, Dict, Any
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.services.hybrid_search import BM25, rrf_merge
from app.services.metadata_resolver import resolve_metadata_filter
from app.services.product_identifier import identify_product
from app.config import TOP_K, SCORE_THRESHOLD, RRF_HIGH_THRESHOLD, RRF_LOW_THRESHOLD


# Internal LRU cache for query context retrieval
_RETRIEVAL_CACHE: Dict[str, Tuple[List[Dict[str, Any]], str]] = {}
_MAX_CACHE_SIZE = 500


def clear_retrieval_cache():
    """Clear in-memory retrieval caches when index or documents change."""
    _RETRIEVAL_CACHE.clear()
    _PDF_PAGE_TEXT_CACHE.clear()



# Cached PDF page text mappings to resolve page numbers for chunks
_PDF_PAGE_TEXT_CACHE: Dict[str, List[Tuple[int, str]]] = {}


def resolve_chunk_page(source_file: str, content: str, default_page: Optional[int] = None) -> Optional[int]:
    """Resolve the page number for a chunk using PDF text layout if not in payload."""
    if default_page is not None:
        return default_page
    if not source_file or not source_file.lower().endswith(".pdf"):
        return None

    import os
    from app.config import settings
    pdf_path = os.path.join(str(settings.INPUT_DIR), os.path.basename(source_file))
    if not os.path.exists(pdf_path):
        return None

    if pdf_path not in _PDF_PAGE_TEXT_CACHE:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            pages = []
            for page_idx, page in enumerate(doc):
                pages.append((page_idx + 1, " ".join(page.get_text().lower().split())))
            _PDF_PAGE_TEXT_CACHE[pdf_path] = pages
        except Exception:
            return None

    pages = _PDF_PAGE_TEXT_CACHE.get(pdf_path, [])
    clean_chunk = " ".join(content.lower().split())
    if not clean_chunk:
        return None

    snippet = clean_chunk[:60]
    for page_num, ptext in pages:
        if snippet in ptext:
            return page_num

    if len(clean_chunk) > 50:
        mid_snippet = clean_chunk[30:80]
        for page_num, ptext in pages:
            if mid_snippet in ptext:
                return page_num

    words = [w for w in clean_chunk.split() if len(w) > 4][:10]
    best_page = None
    max_matches = 0
    for page_num, ptext in pages:
        matches = sum(1 for w in words if w in ptext)
        if matches > max_matches and matches >= 4:
            max_matches = matches
            best_page = page_num

    return best_page


def retrieve_context(
    query: str, 
    source_file: Optional[str] = None,
    query_entities: Optional[dict] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Retrieve relevant chunks from Qdrant using hierarchical hybrid search:
      - Level 1: Exact product/model match filter
      - Level 2: Product family match filter
      - Level 3: Global manuals (no metadata filter)
    Includes in-memory LRU query caching for sub-5ms repeated search performance.
    """
    cache_key = f"{query.strip().lower()}||{source_file or ''}||{str(query_entities)}"
    if cache_key in _RETRIEVAL_CACHE:
        return _RETRIEVAL_CACHE[cache_key]

    embedder = EmbedderService()
    vector_store = VectorStoreService()

    # Identify query entities if not pre-extracted
    if not query_entities:
        query_entities = identify_product(query)

    query_vector = embedder.embed_text(query)

    # Hierarchical search loop (Levels 1, 2, 3)
    for level in [1, 2, 3]:
        q_filter = resolve_metadata_filter(query_entities, filter_level=level) if query_entities else None

        # Skip level if filter is expected but not resolved (e.g. no product detected)
        if level < 3 and not q_filter:
            continue

        # 1. Dense Vector Search: Fetch top 50 candidates
        dense_hits = vector_store.search(
            query_vector, 
            top_k=50, 
            source_file=source_file, 
            query_filter=q_filter
        )

        dense_candidates = []
        for hit in dense_hits:
            if hit.score >= SCORE_THRESHOLD:
                c_content = hit.payload.get("content", "")
                c_source = hit.payload.get("source_file", "unknown")
                c_page = resolve_chunk_page(c_source, c_content, hit.payload.get("page"))
                dense_candidates.append({
                    "content":   c_content,
                    "score":     round(hit.score, 4),
                    "source":    c_source,
                    "chunk_id":  hit.payload.get("chunk_id", ""),
                    "image_ids": hit.payload.get("image_ids", []),
                    "embedding": hit.payload.get("embedding", []),
                    "page":      c_page,
                    "product":   hit.payload.get("product"),
                })

        # 2. Sparse BM25 Search: Fetch matching candidate chunks
        all_chunks = vector_store.get_all_chunks(source_file=source_file, scroll_filter=q_filter)
        
        sparse_candidates = []
        if all_chunks:
            bm25 = BM25(all_chunks)
            scores = bm25.get_scores(query)

            # Pair chunks with their scores
            chunk_scores = []
            for chunk, score in zip(all_chunks, scores):
                if score > 0:  # Only keep chunks with some keyword matching
                    chunk_scores.append((chunk, score))

            # Sort descending by score and pick top 50 candidates
            chunk_scores.sort(key=lambda x: x[1], reverse=True)
            top_sparse = chunk_scores[:50]

            for chunk, score in top_sparse:
                c_content = chunk["content"]
                c_source = chunk["source_file"]
                c_page = resolve_chunk_page(c_source, c_content, chunk.get("page"))
                sparse_candidates.append({
                    "content":   c_content,
                    "score":     round(score, 4),
                    "source":    c_source,
                    "chunk_id":  chunk["chunk_id"],
                    "image_ids": chunk.get("image_ids", []),
                    "embedding": chunk.get("embedding", []),
                    "page":      c_page,
                    "product":   chunk.get("product"),
                })

        # 3. Reciprocal Rank Fusion (RRF): Merge dense and sparse candidate lists
        merged_results = rrf_merge(
            dense_results=dense_candidates,
            sparse_results=sparse_candidates,
            top_k=TOP_K,
        )

        if merged_results:
            for item in merged_results:
                if item.get("page") is None:
                    item["page"] = resolve_chunk_page(item.get("source", ""), item.get("content", ""))

        # Return results if any are found at this hierarchy level
        if merged_results:
            print(f"[Retriever] Found {len(merged_results)} chunks at retrieval Level {level} (filter: {q_filter is not None}).")
            top_rrf_score = merged_results[0].get("rrf_score", 0.0)
            print(f"[Retriever] Top RRF score: {top_rrf_score}")
            if top_rrf_score >= RRF_HIGH_THRESHOLD:
                retrieval_confidence = "HIGH"
            elif top_rrf_score >= RRF_LOW_THRESHOLD:
                retrieval_confidence = "MEDIUM"
            else:
                retrieval_confidence = "LOW"

            # Cache result in LRU dict (maintain max capacity)
            if len(_RETRIEVAL_CACHE) >= _MAX_CACHE_SIZE:
                _RETRIEVAL_CACHE.pop(next(iter(_RETRIEVAL_CACHE)))
            _RETRIEVAL_CACHE[cache_key] = (merged_results, retrieval_confidence)

            return merged_results, retrieval_confidence

    return [], "LOW"


async def retrieve_context_with_vision_async(
    query: str,
    source_file: Optional[str] = None,
    query_entities: Optional[dict] = None
) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, Any]]]:
    """
    Parallel hybrid retrieval executing text RRF search and SigLIP vision search concurrently.
    """
    from app.services.vision_search import search_similar_images

    # Run text retrieval and vision search concurrently
    text_task = asyncio.to_thread(retrieve_context, query, source_file, query_entities)
    vision_task = asyncio.to_thread(search_similar_images, query, 5, source_file, query_entities)

    (merged_results, retrieval_confidence), vision_results = await asyncio.gather(text_task, vision_task)

    return merged_results, retrieval_confidence, vision_results


def retrieve_context_with_vision(
    query: str,
    source_file: Optional[str] = None,
    query_entities: Optional[dict] = None
) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, Any]]]:
    """
    Synchronous wrapper for parallel hybrid + vision retrieval.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Running inside async event loop (e.g. FastAPI / Uvicorn)
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(retrieve_context_with_vision_async(query, source_file, query_entities))
    else:
        return asyncio.run(retrieve_context_with_vision_async(query, source_file, query_entities))



