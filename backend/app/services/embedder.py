"""
embedder.py — Singleton embedding service using sentence-transformers.
Loads the model once at startup and reuses it for all embedding calls.
"""
from sentence_transformers import SentenceTransformer
from app.config import EMBED_MODEL


class EmbedderService:
    _instance = None

    def __new__(cls):
        # Singleton: only load model once
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print(f"[Embedder] Loading model: {EMBED_MODEL} ...")
            cls._instance.model = SentenceTransformer(EMBED_MODEL)
            print("[Embedder] Model ready.")
        return cls._instance

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a dense vector."""
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in one pass for efficiency."""
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]
