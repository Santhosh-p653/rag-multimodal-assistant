# Codebase Knowledge Base & Full Project Context

**Purpose:** This document is the "Brain of the Codebase". It contains the exhaustive end-to-end technical context of the Multimodal RAG Assistant project. If fed into an LLM, this file provides 100% of the operational logic, file routing, state management, and algorithmic decisions needed to understand, debug, or extend the repository.

---

## 1. Core Technology Stack
- **Backend Framework**: FastAPI (Python 3.10+).
- **Frontend Framework**: Next.js (React, TypeScript, Tailwind CSS, Lucide Icons).
- **Agent Orchestration**: LangGraph (`StateGraph`).
- **Vector Database**: Qdrant (Local In-Memory/Disk).
- **Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2` running offline).
- **Document Parsing**: Microsoft `MarkItDown` (Text) and `PyMuPDF/Fitz` (Images & Vectors).
- **Voice (STT/TTS)**: `faster-whisper` (Local English STT), Sarvam AI `Saaras v3` (Indic STT), `edge-tts` (Microsoft Neural TTS).
- **LLM Providers**: Groq / SambaNova.

---

## 2. Directory & File Breakdown

### Backend (`backend/app/`)
* **`main.py`**: The FastAPI entry point. Defines rate limiting (`slowapi`), API keys routing, file upload endpoint (`/upload`), LLM querying endpoint (`/agent/run`), audio TTS generation (`/tts`), and frontend static asset proxies.
* **`services/agent_flow.py`**: The central nervous system. Defines the LangGraph state machine routing all inputs through ingestion or retrieval nodes.
* **`services/parser.py`**: Orchestrates `MarkItDown` conversion, invokes the image extractor, calls chunking, and maps visual embeddings to text embeddings.
* **`services/image_extractor.py`**: Uses PyMuPDF to extract standard raster images AND render PDF vector paths (drawings) into PNGs. Applies perceptual hashing (`pHash`) to deduplicate repeating logos.
* **`services/chunker.py`**: Character-level sliding window chunker (500 size, 100 overlap). Injects metadata (product, version, page) into every chunk for context-grounding.
* **`services/embedder.py`**: Singleton wrapper around `SentenceTransformer`. Configured for offline loading via environment variables to prevent HuggingFace timeout blocks.
* **`services/vector_store.py`**: Qdrant client wrapper. Handles `upsert`, `delete_by_filename`, and payload scrolling. Note: Qdrant `query_points` omits vector retrieval by default.
* **`services/hybrid_search.py`**: Implements BM25 sparse scoring and Reciprocal Rank Fusion (RRF) math to combine dense/sparse candidates.
* **`services/retriever.py`**: Executes the 3-level waterfall search (Exact Product -> Family -> Global) and invokes the hybrid search.
* **`services/product_identifier.py`**: Zero-shot prompt sent to the LLM to extract product names and categories from raw text.
* **`services/query_understanding.py`**: Analyzes the raw prompt before retrieval to assign `input_confidence` (HIGH, MEDIUM, LOW) and extract ambiguities.
* **`services/context_reconstruction.py`**: Uses session memory (previous Q/A turns) to rewrite vague follow-up questions into standalone context-rich questions.
* **`services/session_store.py`**: SQLite database managing cross-turn state, including tracking whether the bot is currently awaiting clarification from the user.
* **`services/prompt_guard.py`**: Regex-based jailbreak detector guarding against common override attacks.
* **`services/audio.py`**: STT/TTS abstractions.

### Frontend (`frontend/src/`)
* **`pages/index.tsx`**: Main Chat UI. Manages React states for messages, recording audio, and displaying diagnostic history.
* **`components/MessageBubble.tsx`**: Renders chat messages. Critically, maps `message.images` to display diagrams beneath text, and uses an invisible HTML `<audio>` element for autoplaying TTS responses.
* **`lib/api.ts`**: The Axios/Fetch bridge. Interacts with `/agent/run` and parses the backend JSON into the `Message` interface.

---

## 3. The Lifecycle of a Document (Ingestion)

When a document (e.g., `test1.pdf`) is POSTed to `/upload`:
1. **Security Check**: `main.py` enforces a `<=25MB` constraint and checks MIME types.
2. **Qdrant Cleanup**: The system finds all existing chunks where `source_file == "test1.pdf"` and deletes them from Qdrant to prevent duplication.
3. **Image & Vector Harvesting**: `image_extractor.py` opens the PDF.
   * Extracts raster images.
   * Detects vector graphics (rectangles, lines). Clusters them, draws them onto a canvas, and exports as PNGs.
   * Runs strict filters: checks Aspect Ratio (ignoring 10:1 lines), page area percentage, and margin location.
   * Creates a perceptual hash (pHash). If the hash appears on >2 pages, it's flagged as a decorative logo and discarded.
4. **Text Extraction & Zero-Shot Meta**: `MarkItDown` parses text. The first 1500 chars are sent to the LLM to guess the Product Model (e.g., "X100").
5. **Chunking**: Text is split into `500` char chunks.
6. **Semantic Image Association**:
   * For every image extracted, the text physically closest to it in the PDF (`nearby_text`) is embedded into a 384-dimensional vector.
   * Every text chunk is embedded into a 384-dimensional vector.
   * A dot-product Cosine Similarity is calculated between every chunk and every image.
   * If similarity `>= 0.40`, the `image_id` is appended to the chunk's `image_ids` array.
7. **Storage**: The chunks (containing text, embedding, metadata, and `image_ids`) are saved to Qdrant. Images are saved to disk with a `metadata.json` registry.

---

## 4. The Lifecycle of a Query (Agentic Retrieval)

When a user submits a query to `/agent/run`, it traverses the LangGraph `StateGraph` defined in `agent_flow.py`:

### Node 1: Session & Context Reconstruction
- `check_clarification_node`: Checks `SessionStore`. Is the system waiting for the user to answer a clarifying question (e.g., "Which model?")?
- `reconstruct_context_node`: If yes, the LLM fuses the user's short answer ("The X100") with the previous context to yield a `resolved_query` ("How do I fix the X100?").

### Node 2: Query Analysis
- `analyze_input_node`: Evaluates the query for intent. Generates an `input_confidence`.
- `input_confidence_router`: If HIGH (clear), proceeds to product identification. If LOW/MEDIUM with ambiguities, routes to `clarify_or_fallback_node` to demand more details from the user.

### Node 3: Product Matching & Mode Classification
- `identify_product`: Uses fuzzy matching against Qdrant's unique product index.
- `classify_mode`: LLM classifies the query as either `qa` (general knowledge) or `troubleshoot` (diagnostic error).

### Node 4: Hierarchical RRF Retrieval
- `retrieve`: Executes the search against Qdrant. 
   - Level 1: Filter by Exact Product.
   - Level 2: Filter by Family.
   - Level 3: Global (No filter).
- Combines Dense (cosine) and Sparse (BM25) results using **Reciprocal Rank Fusion**: `Score = 1 / (60 + DenseRank) + 1 / (60 + SparseRank)`.
- Generates a `retrieval_confidence` (HIGH if RRF score is strong, LOW if weak).

### Node 5: Strict Visual Information Filtering
- `image_filtering_node`: Looks at the `image_ids` in the retrieved chunks.
- If `retrieval_confidence == "HIGH"`, up to 3 images are appended to the response.
- **CRITICAL**: If `retrieval_confidence == "MEDIUM"`, the system assumes a high risk of hallucination. It re-embeds the chunk text and dynamically checks it against the image's text. The image is ONLY permitted if the Cosine Similarity `>= 0.65`.

### Node 6: LLM Generation
- `generate`: 
  - If `retrieval_confidence == "MEDIUM"`, injects a prompt instruction forcing the LLM to hedge its answer (e.g., "The documentation partially mentions...").
  - If mode is `qa`, the LLM outputs plain text.
  - If mode is `troubleshoot`, the LLM outputs a strictly formatted JSON object containing an `answer` string and a `steps` array of diagnostic actions.

### Node 7: Output Formatting
- `format_response`: Assembles the final state. Constructs the URL for the frontend to fetch the diagrams (`/document-images/{doc_id}/{img_id}`).

---

## 5. Security Policies

1. **slowapi Rate Limiting**: `main.py` enforces strict limits (e.g., 5 requests/minute for heavy LLM endpoints, 10/minute for uploads).
2. **File Validation**: `magic` library ensures uploaded files are genuinely PDFs/Docs, preventing malicious payloads disguised by extensions.
3. **PromptGuard Regex**: Pre-execution filters block queries containing words like "ignore previous instructions", "system prompt", or "bypass".
4. **Isolated Context Prompting**: RAG context chunks are encapsulated in strict delimiters `--- Source ---`. The system prompt rigidly instructs the LLM to treat anything within delimiters as data, never as commands.
