"""
retriever.py — Retrieve relevant chunks from Qdrant for a given query.
Embeds the query, searches the vector store, and filters by score threshold.
"""
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.config import TOP_K, SCORE_THRESHOLD


def retrieve_context(query: str) -> list[dict]:
    """
    Embed the query, search Qdrant, filter by score threshold, and return
    a list of context dicts.

    Returns:
        [
            {
                "content":     "...",
                "score":       0.91,
                "source":      "manual_001.pdf",
                "chunk_id":    "manual_001.pdf::chunk_3"
            },
            ...
        ]
        Returns an empty list if no chunks pass the threshold.
    """
    embedder = EmbedderService()
    vector_store = VectorStoreService()

    # Embed the query
    query_vector = embedder.embed_text(query)

    # Search Qdrant
    results = vector_store.search(query_vector, top_k=TOP_K)

    # Filter by confidence threshold and format output
    context = []
    for hit in results:
        if hit.score >= SCORE_THRESHOLD:
            context.append({
                "content":  hit.payload.get("content", ""),
                "score":    round(hit.score, 4),
                "source":   hit.payload.get("source_file", "unknown"),
                "chunk_id": hit.payload.get("chunk_id", ""),
            })

    return context
