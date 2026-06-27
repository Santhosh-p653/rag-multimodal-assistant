from typing import Optional
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.services.hybrid_search import BM25, rrf_merge
from app.config import TOP_K, SCORE_THRESHOLD


def retrieve_context(query: str, source_file: Optional[str] = None) -> list[dict]:
    """
    Retrieve relevant chunks from Qdrant using hybrid search:
      1. Fetch dense vector similarity search candidates
      2. Fetch sparse keyword search candidates (BM25)
      3. Merge using Reciprocal Rank Fusion (RRF)
      4. Return the top TOP_K chunks.
    """
    embedder = EmbedderService()
    vector_store = VectorStoreService()

    # 1. Dense Vector Search: Fetch top 50 candidates
    query_vector = embedder.embed_text(query)
    dense_hits = vector_store.search(query_vector, top_k=50, source_file=source_file)

    dense_candidates = []
    for hit in dense_hits:
        if hit.score >= SCORE_THRESHOLD:
            dense_candidates.append({
                "content":  hit.payload.get("content", ""),
                "score":    round(hit.score, 4),
                "source":   hit.payload.get("source_file", "unknown"),
                "chunk_id": hit.payload.get("chunk_id", ""),
            })

    # 2. Sparse BM25 Search: Fetch all candidate chunks (with optional filtering)
    all_chunks = vector_store.get_all_chunks(source_file=source_file)
    
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
            sparse_candidates.append({
                "content":  chunk["content"],
                "score":    round(score, 4),
                "source":   chunk["source_file"],
                "chunk_id": chunk["chunk_id"],
            })

    # 3. Reciprocal Rank Fusion (RRF): Merge dense and sparse candidate lists
    merged_results = rrf_merge(
        dense_results=dense_candidates,
        sparse_results=sparse_candidates,
        top_k=TOP_K,
    )

    return merged_results

