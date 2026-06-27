"""
vector_store.py — In-memory Qdrant vector store service.
Runs entirely as a Python library — no external process or Docker required.
Uses the qdrant-client 1.x API (query_points / create_collection).
"""
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.config import QDRANT_COLLECTION, TOP_K


class VectorStoreService:
    _instance = None

    def __new__(cls):
        # Singleton: share one in-memory client across the app
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = QdrantClient(":memory:")
            cls._instance._collection_ready = False
            cls._instance._vector_size = None
            print("[VectorStore] In-memory Qdrant client initialized.")
        return cls._instance

    def _ensure_collection(self, vector_size: int):
        """Create the collection on first use with the correct vector dimensions."""
        if not self._collection_ready:
            # Delete if exists (handles server restarts in same process)
            existing = [c.name for c in self.client.get_collections().collections]
            if QDRANT_COLLECTION in existing:
                self.client.delete_collection(QDRANT_COLLECTION)

            self.client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            self._collection_ready = True
            self._vector_size = vector_size
            print(f"[VectorStore] Collection '{QDRANT_COLLECTION}' created (dim={vector_size}).")

    def ingest_chunks(self, chunks: list[dict]):
        """
        Upsert a list of embedded chunks into Qdrant.
        Each chunk must have: { chunk_id, content, source_file, embedding }
        """
        if not chunks:
            return

        vector_size = len(chunks[0]["embedding"])
        self._ensure_collection(vector_size)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=chunk["embedding"],
                payload={
                    "chunk_id":    chunk["chunk_id"],
                    "content":     chunk["content"],
                    "source_file": chunk["source_file"],
                },
            )
            for chunk in chunks
        ]

        self.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        print(f"[VectorStore] Ingested {len(points)} chunks from '{chunks[0]['source_file']}'.")

    def search(
        self, 
        query_vector: list[float], 
        top_k: int = TOP_K, 
        source_file: str = None
    ) -> list:
        """
        Search the collection and return top-K results, optionally filtered by source_file.
        Uses query_points() API available in qdrant-client >= 1.7.
        Each result has .score and .payload attributes.
        """
        if not self._collection_ready:
            return []

        query_filter = None
        if source_file:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        # response.points is a list of ScoredPoint
        return response.points

    def get_all_chunks(self, source_file: str = None) -> list[dict]:
        """
        Retrieve all chunks from Qdrant, optionally filtered by source_file.
        Returns a list of dictionaries with 'chunk_id', 'content', and 'source_file'.
        """
        if not self._collection_ready:
            return []

        scroll_filter = None
        if source_file:
            scroll_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            )

        # Scroll to get all matching points (limit set high to fetch all chunks in memory)
        response = self.client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=scroll_filter,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        
        points, _ = response
        
        chunks = []
        for point in points:
            chunks.append({
                "chunk_id":    point.payload.get("chunk_id", ""),
                "content":     point.payload.get("content", ""),
                "source_file": point.payload.get("source_file", "unknown"),
            })
        return chunks

    def get_unique_sources(self) -> list[str]:
        """Retrieve all unique source filenames from the Qdrant database."""
        chunks = self.get_all_chunks()
        sources = list(set(c["source_file"] for c in chunks if c.get("source_file")))
        return sorted(sources)

    def count(self) -> int:
        """Return total number of vectors stored."""
        if not self._collection_ready:
            return 0
        return self.client.count(collection_name=QDRANT_COLLECTION).count
