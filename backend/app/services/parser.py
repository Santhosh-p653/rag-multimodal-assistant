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


class ParserService:
    def __init__(self):
        self.input_dir = "data_sandbox/input_manuals"
        self.output_dir = "data_sandbox/processed_markdown"

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
        base_name, _ = os.path.splitext(filename)

        # 1. Save original raw file
        raw_path = os.path.join(self.input_dir, filename)
        with open(raw_path, "wb") as f:
            f.write(content)

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

        # 4. Chunk the markdown
        chunks = chunk_markdown(md_content, source_file=filename)

        # 5. Embed all chunks in one batch for efficiency
        texts = [chunk["content"] for chunk in chunks]
        embeddings = self.embedder.embed_batch(texts)

        # 6. Attach embeddings and upsert into Qdrant
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        self.vector_store.ingest_chunks(chunks)

        return {
            "markdown_file": md_filename,
            "chunks_ingested": len(chunks),
        }
