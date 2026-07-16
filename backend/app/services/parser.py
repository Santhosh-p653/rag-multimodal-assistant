"""
parser.py — Document parsing service.
Saves raw uploaded files, converts them to markdown using MarkItDown,
then chunks the markdown and embeds + ingests it into the Qdrant vector store.
"""
import os
from markitdown import MarkItDown
from app.services.chunker import chunk_markdown
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.config import settings
from app.services.image_extractor import extract_and_filter_images
from app.services.image_filters import ASSOCIATION_MIN_SIMILARITY
import numpy as np


class ParserService:
    def __init__(self):
        self.input_dir = str(settings.INPUT_DIR)
        self.output_dir = str(settings.OUTPUT_DIR)

        # Ensure target directories exist
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.markitdown = MarkItDown()
        self.supported_extensions = {".pdf", ".docx", ".pptx", ".xlsx", ".txt"}

        # Shared singleton services
        self.embedder = EmbedderService()
        self.vector_store = VectorStoreService()

    def is_supported(self, filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in self.supported_extensions

    def parse_file(self, filename: str, content: bytes) -> dict:
        """
        Full ingestion pipeline:
          1. Save raw file to input_manuals/
          2. Convert to markdown with MarkItDown
          3. Save markdown to processed_markdown/
          4. Chunk markdown into overlapping segments
          5. Embed each chunk
          6. Upsert into Qdrant vector store

        Returns:
            { markdown_file, chunks_ingested }
        """
        filename = os.path.basename(filename)
        base_name, ext = os.path.splitext(filename)

        # 0. Re-ingestion Cleanup: Delete existing chunks and image metadata
        self.vector_store.delete_by_filename(filename)
        images_dir = os.path.join(self.output_dir, "images", base_name)
        if os.path.exists(images_dir):
            import shutil
            shutil.rmtree(images_dir, ignore_errors=True)

        # 1. Save original raw file
        raw_path = os.path.join(self.input_dir, filename)
        with open(raw_path, "wb") as f:
            f.write(content)

        # 1.5 Extract images if PDF
        extracted_images = []
        if ext.lower() == ".pdf":
            extracted_images = extract_and_filter_images(raw_path, base_name)

        # 2. Convert with MarkItDown
        try:
            result = self.markitdown.convert(raw_path)
            md_content = result.text_content
        except Exception as e:
            if os.path.exists(raw_path):
                os.remove(raw_path)
            raise RuntimeError(f"MarkItDown conversion failed: {str(e)}")

        # 3. Save markdown output
        md_filename = f"{base_name}.md"
        md_path = os.path.join(self.output_dir, md_filename)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Extract metadata from filename and sample content
        from app.services.product_identifier import identify_product
        sample_text = md_content[:1500]
        metadata = identify_product(f"File: {filename}\n{sample_text}")

        # 4. Chunk the markdown
        chunks = chunk_markdown(md_content, source_file=filename, metadata=metadata)

        # 5. Embed all chunks in one batch for efficiency
        texts = [chunk["content"] for chunk in chunks]
        embeddings = self.embedder.embed_batch(texts)

        # 6. Attach embeddings and associate images
        # Embed image nearby text/captions for similarity matching
        image_embeddings = []
        if extracted_images:
            image_texts = [img.get("nearby_text", "") for img in extracted_images]
            image_embeddings = self.embedder.embed_batch(image_texts)

        for chunk, chunk_embedding in zip(chunks, embeddings):
            chunk["embedding"] = chunk_embedding
            chunk["image_ids"] = []
            
            # Associate images based on cosine similarity
            if extracted_images:
                # Calculate cosine similarities
                c_emb = np.array(chunk_embedding)
                for i, img_emb in enumerate(image_embeddings):
                    i_emb = np.array(img_emb)
                    sim = np.dot(c_emb, i_emb) / (np.linalg.norm(c_emb) * np.linalg.norm(i_emb) + 1e-10)
                    if sim >= ASSOCIATION_MIN_SIMILARITY:
                        chunk["image_ids"].append(extracted_images[i]["image_id"])

        self.vector_store.ingest_chunks(chunks)

        return {
            "markdown_file": md_filename,
            "chunks_ingested": len(chunks),
        }
