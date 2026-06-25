"""
config.py — Central configuration for the Multimodal RAG Assistant backend.
Loads environment variables from backend/.env using python-dotenv.
"""
import os
from dotenv import load_dotenv

# Load .env file from the backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# --- LLM Provider ---
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
SAMBANOVA_API_KEY: str = os.getenv("SAMBANOVA_API_KEY", "")

# Auto-detect which provider to use (Groq preferred)
if GROQ_API_KEY:
    LLM_PROVIDER = "groq"
    LLM_MODEL = "llama-3.1-8b-instant"       # Fast Groq model
elif SAMBANOVA_API_KEY:
    LLM_PROVIDER = "sambanova"
    LLM_MODEL = "Meta-Llama-3.1-8B-Instruct"  # SambaNova model
else:
    LLM_PROVIDER = "none"
    LLM_MODEL = ""

# --- Embeddings ---
EMBED_MODEL: str = "all-MiniLM-L6-v2"        # Local sentence-transformers model (~90MB)

# --- Qdrant Vector Store ---
QDRANT_COLLECTION: str = "manuals"

# --- RAG Parameters ---
TOP_K: int = 5                                 # Number of chunks to retrieve
SCORE_THRESHOLD: float = 0.0                  # Min cosine similarity score to use a chunk

# --- Chunking ---
CHUNK_SIZE: int = 500                          # Characters per chunk
CHUNK_OVERLAP: int = 100                       # Character overlap between chunks
