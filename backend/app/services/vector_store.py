import os
import uuid
from typing import Optional
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.config import QDRANT_COLLECTION, TOP_K, VISION_COLLECTION

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class VectorStoreService:
    _instance = None

    def __new__(cls, db_path: str = "data_sandbox/qdrant_db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            if db_path == ":memory:":
                cls._instance.client = QdrantClient(":memory:")
                print("[VectorStore] In-memory Qdrant client initialized.")
            else:
                if not os.path.isabs(db_path):
                    db_path = str(BASE_DIR / db_path)
                cls._instance.client = QdrantClient(path=db_path)
                print(f"[VectorStore] Persistent Qdrant client initialized at: {db_path}")

            cls._instance._collection_ready = False
            cls._instance._vector_size = None
        return cls._instance

    def _ensure_collection(self, vector_size: int):
        """Create the collection on first use if it does not already exist."""
        if not self._collection_ready:
            if not self.client.collection_exists(QDRANT_COLLECTION):
                self.client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                print(f"[VectorStore] Collection '{QDRANT_COLLECTION}' created (dim={vector_size}).")
            else:
                print(f"[VectorStore] Collection '{QDRANT_COLLECTION}' already exists. Reusing it.")
            self._collection_ready = True
            self._vector_size = vector_size

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
                    "chunk_id":       chunk["chunk_id"],
                    "content":        chunk["content"],
                    "source_file":   chunk["source_file"],
                    "image_ids":      chunk.get("image_ids", []),
                    "product":        chunk.get("product"),
                    "model":          chunk.get("model"),
                    "category":       chunk.get("category"),
                    "version":        chunk.get("version"),
                    "section":        chunk.get("section"),
                    "page":           chunk.get("page"),
                    "product_family": chunk.get("product_family"),
                },
            )
            for chunk in chunks
        ]

        self.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        print(f"[VectorStore] Ingested {len(points)} chunks from '{chunks[0]['source_file']}' with metadata.")

    def search(
        self, 
        query_vector: list[float], 
        top_k: int = TOP_K, 
        source_file: str = None,
        query_filter: Filter = None
    ) -> list:
        """
        Search the collection and return top-K results.
        """
        if not self._collection_ready:
            return []

        if source_file:
            sf_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            )
            if query_filter:
                if not hasattr(query_filter, "must") or query_filter.must is None:
                    query_filter.must = []
                query_filter.must.extend(sf_filter.must)
            else:
                query_filter = sf_filter

        response = self.client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return response.points

    def get_all_chunks(self, source_file: str = None, scroll_filter: Filter = None) -> list[dict]:
        """
        Retrieve all chunks from Qdrant, optionally filtered.
        """
        if not self._collection_ready:
            return []

        if source_file:
            sf_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            )
            if scroll_filter:
                if not hasattr(scroll_filter, "must") or scroll_filter.must is None:
                    scroll_filter.must = []
                scroll_filter.must.extend(sf_filter.must)
            else:
                scroll_filter = sf_filter

        response = self.client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=scroll_filter,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        points = response[0] if isinstance(response, tuple) else response

        chunks = []
        for point in points:
            chunks.append({
                "chunk_id":       point.payload.get("chunk_id", ""),
                "content":        point.payload.get("content", ""),
                "source_file":   point.payload.get("source_file", ""),
                "image_ids":      point.payload.get("image_ids", []),
                "product":        point.payload.get("product"),
                "model":          point.payload.get("model"),
                "category":       point.payload.get("category"),
                "version":        point.payload.get("version"),
                "section":        point.payload.get("section"),
                "page":           point.payload.get("page"),
                "product_family": point.payload.get("product_family"),
            })
        return chunks

    def get_all_products(self) -> list[str]:
        """Retrieve all unique product names from the Qdrant database."""
        return self.get_unique_products()

    def get_unique_products(self) -> list[str]:
        """Retrieve all unique product names from the Qdrant database."""
        chunks = self.get_all_chunks()
        products = list(set(c["product"] for c in chunks if c.get("product")))
        return sorted(products)

    def get_unique_sources(self) -> list[str]:
        """Retrieve all unique source files loaded in the Qdrant database."""
        chunks = self.get_all_chunks()
        sources = list(set(c["source_file"] for c in chunks if c.get("source_file")))
        return sorted(sources)

    def delete_by_filename(self, filename: str):
        """Delete all points associated with a specific source filename from the Qdrant database."""
        if not self._collection_ready:
            return
        self.client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=filename)
                    )
                ]
            )
        )
        print(f"[VectorStore] Deleted existing chunks for file: {filename}")

    def count(self) -> int:
        """Return total number of vectors stored."""
        if not self._collection_ready:
            return 0
        return self.client.count(collection_name=QDRANT_COLLECTION).count

    # --- Vision Image Collection Operations ---

    def _ensure_image_collection(self, vector_size: int):
        """Create the vision image collection on first use if it does not already exist."""
        if not self.client.collection_exists(VISION_COLLECTION):
            self.client.create_collection(
                collection_name=VISION_COLLECTION,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            print(f"[VectorStore] Image collection '{VISION_COLLECTION}' created (dim={vector_size}).")

    def ingest_images(self, image_records: list[dict]):
        """
        Upsert a list of embedded image records into the manual_images Qdrant collection.
        """
        if not image_records:
            return

        vector_size = len(image_records[0]["vision_embedding"])
        self._ensure_image_collection(vector_size)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=record["vision_embedding"],
                payload={
                    "image_id":      record.get("image_id"),
                    "source_file":   record.get("source_file"),
                    "page_number":   record.get("page_number"),
                    "bounding_box":  record.get("bounding_box"),
                    "image_path":    record.get("image_path"),
                    "nearby_text":   record.get("nearby_text", ""),
                    "caption":       record.get("caption", ""),
                    "product":       record.get("product"),
                    "model":         record.get("model"),
                    "image_type":    record.get("image_type", "raster"),
                },
            )
            for record in image_records
            if record.get("vision_embedding")
        ]

        if points:
            self.client.upsert(collection_name=VISION_COLLECTION, points=points)
            print(f"[VectorStore] Ingested {len(points)} image vectors into '{VISION_COLLECTION}'.")

    def search_images(
        self,
        query_vector: list[float],
        top_k: int = TOP_K,
        source_file: str = None,
        query_filter: Filter = None
    ) -> list:
        """Search the manual_images collection and return top matching image points."""
        if not self.client.collection_exists(VISION_COLLECTION):
            return []

        if source_file:
            sf_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )
                ]
            )
            if query_filter:
                if not hasattr(query_filter, "must") or query_filter.must is None:
                    query_filter.must = []
                query_filter.must.extend(sf_filter.must)
            else:
                query_filter = sf_filter

        try:
            return self.client.search(
                collection_name=VISION_COLLECTION,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=-1.0,
                with_payload=True,
            )
        except Exception:
            response = self.client.query_points(
                collection_name=VISION_COLLECTION,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=-1.0,
                with_payload=True,
            )
            return response.points

    def delete_images_by_filename(self, filename: str):
        """Delete image vectors associated with source_file from manual_images collection."""
        if not self.client.collection_exists(VISION_COLLECTION):
            return
        self.client.delete(
            collection_name=VISION_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_file",
                        match=MatchValue(value=filename)
                    )
                ]
            )
        )
        print(f"[VectorStore] Deleted image vectors for file: {filename}")
