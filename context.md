# OCTO-RAG Codebase Knowledge Base & Full Project Context

**Purpose:** This document serves as the complete, authoritative technical reference and inventory of **OCTO-RAG**. It details every component, service file, test module, benchmark result, data sandbox layout, and operational state currently present in the codebase.

---

## 1. System Status & Verification Benchmark Metrics

### Performance Benchmarks
- **Verification Test Suite**: **42 / 42 tests passing** (`pytest -vv`).
- **Precision @ 5**: **78.0%**
- **Recall @ 5**: **78.0%**
- **Mean Reciprocal Rank (MRR)**: **0.9167**
- **Hit Rate @ 5**: **100.0%**
- **Retrieval Cache Latency**: **< 5ms** (In-memory LRU dict cache)
- **Token Leakage Prevention**: **0 LLM API tokens** spent on off-topic requests (Pre-LLM Guardrail `is_out_of_domain`).
- **Core Engine Capabilities**: Grounded RAG with 3-level waterfall hybrid search (dense + BM25 RRF), FastMCP server (6 diagnostic, RAG, and agent tools over stdio & SSE), SigLIP 2 visual image search, PyMuPDF vector drawing extraction, LangGraph stateful graph execution, multi-turn troubleshooting state machine, hybrid STT/TTS voice layer, and pre-LLM security domain boundary.

---

## 2. Complete Technology Stack Matrix

| Subsystem | Technology | Role | Selection Rationale |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | Next.js 14 + React + TypeScript + Tailwind CSS | Technician Chat Console & Admin Portal | Static pre-rendering, responsive visual layout, accessible card components, zero dark neon gradients. |
| **Backend API** | FastAPI (Python 3.11) | Async REST API & security gateway | Fast Pydantic schema validation, native async IO execution, automatic OpenAPI Swagger generation. |
| **MCP Server** | FastMCP (`mcp>=1.2.0`) | Model Context Protocol diagnostic tools | Standard open protocol exposing 6 tools to Claude Desktop, IDEs, and external desktop AI clients over stdio & SSE (`/mcp/sse`). |
| **Agent Engine** | LangGraph (`StateGraph`) | Bounded query orchestration | Provides explicit control over node boundaries, MD5 version control, and conditional fallbacks. |
| **Vector DB** | Qdrant (Dual Collections) | High-speed vector indexing & search | Manages dual collections (`manuals` text & `manual_images` visual), fast payload filtering, lightweight local deployment. |
| **Text Embeddings**| SentenceTransformers (`all-MiniLM-L6-v2`) | 384-dim dense text vectorization | Lightweight (80MB), fast CPU inference, zero API cost, high technical domain performance. |
| **Vision Model** | Google SigLIP 2 (`google/siglip-base-patch16-224`) | 768-dim multimodal visual embeddings | Encodes raw images and text queries into a shared vector space for text-to-image retrieval. |
| **Document Parser**| Microsoft `MarkItDown` & PyMuPDF | Text parsing & vector region rendering | PyMuPDF renders CAD/vector graphics into PNGs; `MarkItDown` converts multi-format files to Markdown. |
| **Voice STT/TTS** | `faster-whisper`, Sarvam AI `Saaras v3`, `edge-tts` | Multilingual Speech-to-Text & Speech Synthesis | `faster-whisper` enables low-latency English STT; Sarvam AI handles Indic regional accents; `edge-tts` provides high-quality Microsoft neural speech synthesis. |
| **LLM Execution** | Groq / SambaNova (Llama 3 70B/8B) | Direct inference generation | Ultra-fast token generation speed (<200ms TTFT) essential for real-time interactive RAG and troubleshooting dialogues. |
| **Security Layer** | `slowapi` & `prompt_guard` | Rate limiting & domain boundary shield | Prevents DDoS attacks, drops prompt injection override attempts, and blocks non-refrigerator queries before calling LLM APIs (**0 token cost**). |

---

## 3. Exhaustive Project Directory & File Inventory

### Backend Codebase (`backend/app/`)
- [backend/app/main.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/main.py) — FastAPI entrypoint, lifespan startup model pre-warming, `slowapi` rate limiters, route handlers (`/chat`, `/chat/stream`, `/upload`, `/troubleshoot`, `/agent/run`, `/transcribe`, `/speak`), and MCP SSE app mounting (`app.mount("/mcp", fridge_mcp_server.sse_app())`).
- [backend/app/config.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/config.py) — Global settings manager (`pathlib.Path` configuration, API keys, file size limits, max retries).
- [backend/app/mcp/__init__.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/mcp/__init__.py) — MCP package initialization.
- [backend/app/mcp/fridge_mcp_server.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/mcp/fridge_mcp_server.py) — FastMCP server exposing 6 diagnostic & agent tools (`search_fridge_manuals`, `lookup_error_code`, `get_thermistor_ohm_table`, `lookup_part_number`, `run_octo_agent`, `troubleshoot_appliance_turn`).
- [backend/app/mcp/mcp_client.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/mcp/mcp_client.py) — Programmatic client helper service for internal Python MCP invocations.
- [backend/app/services/parser.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/parser.py) — Microsoft `MarkItDown` document parser and file ingestion engine.
- [backend/app/services/image_extractor.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/image_extractor.py) — PyMuPDF raster and CAD vector drawing region extractor.
- [backend/app/services/image_filters.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/image_filters.py) — Aspect ratio and perceptual hash (`pHash`) decorative image deduplication filter.
- [backend/app/services/chunker.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/chunker.py) — Character sliding-window chunker (500 chars, 100 overlap) with section header propagation.
- [backend/app/services/embedder.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/embedder.py) — `SentenceTransformers` singleton with `@lru_cache` LRU vector caching.
- [backend/app/services/vision_embedder.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/vision_embedder.py) — Google SigLIP 2 multimodal vision embedder singleton.
- [backend/app/services/vision_search.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/vision_search.py) — SigLIP 2 visual diagram retrieval service against `manual_images` collection.
- [backend/app/services/vector_store.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/vector_store.py) — Qdrant client interface managing dual `manuals` and `manual_images` collections.
- [backend/app/services/hybrid_search.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/hybrid_search.py) — In-memory BM25 sparse keyword search and Reciprocal Rank Fusion (RRF, $k=60$).
- [backend/app/services/retriever.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/retriever.py) — 3-level waterfall hybrid search engine (Exact Product $\rightarrow$ Family Prefix $\rightarrow$ Global) run concurrently with parallel vision search.
- [backend/app/services/query_understanding.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/query_understanding.py) — Query confidence analyzer, product hint extractor, and intent classifier.
- [backend/app/services/context_reconstruction.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/context_reconstruction.py) — Multi-turn query rewriter for pending clarification turns.
- [backend/app/services/session_store.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/session_store.py) — SQLite multi-turn session state registry.
- [backend/app/services/prompt_guard.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/prompt_guard.py) — Security regex injection shield (`is_prompt_injection`) and pre-LLM domain boundary guard (`is_out_of_domain`).
- [backend/app/services/prompt_builder.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/prompt_builder.py) — Context-isolated prompt builder with refrigerator technical support persona.
- [backend/app/services/agent_flow.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/agent_flow.py) — LangGraph unified agentic `StateGraph` orchestrating URL scraping, version control, fuzzy product matching, and answer generation.
- [backend/app/services/workflow_manager.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/workflow_manager.py) — Multi-turn stateful troubleshooting state machine.
- [backend/app/services/audio.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/audio.py) — Hybrid STT (`faster-whisper` & Sarvam AI `Saaras v3`) and TTS (`edge-tts`).
- [backend/app/services/product_identifier.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/product_identifier.py) — Zero-shot entity metadata resolution.

---

### Frontend Codebase (`frontend/src/`)
- [frontend/src/pages/index.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/pages/index.tsx) — Main Technician Chat Console (hero voice button, search input, quick topic chips, guided troubleshooting cards).
- [frontend/src/pages/admin.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/pages/admin.tsx) — Document Upload & Ingestion Portal (drag-and-drop zone, multi-stage upload progress, document library).
- [frontend/src/components/ChatWindow.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/components/ChatWindow.tsx) — Message stream container.
- [frontend/src/components/MessageBubble.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/components/MessageBubble.tsx) — Formatted answer cards, citations, confidence badges, audio read-aloud button.
- [frontend/src/components/VisualDisplay.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/components/VisualDisplay.tsx) — Technical diagram renderer and expanded modal zoom viewer.
- [frontend/src/components/ChatInput.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/components/ChatInput.tsx) — Text input bar and shortcuts.
- [frontend/src/components/AudioRecorder.tsx](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/frontend/src/components/AudioRecorder.tsx) — Voice recording component.

---

### Test Verification Matrix (42 Passing Tests Across 18 Modules)

| Test Module | Test Functions | Verification Focus | Status |
| :--- | :--- | :--- | :--- |
| `tests/security/test_file_uploads.py` | 5 tests | Max file size (25MB), allowed extensions, MIME validation | PASS (100%) |
| `tests/security/test_input_validation.py` | 3 tests | Empty query payloads, length bounds, Pydantic validation | PASS (100%) |
| `tests/security/test_prompt_injection.py` | 3 tests | Injection detection & pre-LLM domain boundary (`is_out_of_domain`) | PASS (100%) |
| `tests/security/test_rate_limits.py` | 1 test | `slowapi` rate limit HTTP 429 enforcement | PASS (100%) |
| `tests/test_api.py` | 2 tests | `/health` endpoint status, vector count payload | PASS (100%) |
| `tests/test_audio.py` | 2 tests | STT audio transcription and `edge-tts` speech synthesis | PASS (100%) |
| `tests/test_chunker.py` | 1 test | Sliding-window character chunking & overlap | PASS (100%) |
| `tests/test_embedder.py` | 1 test | `SentenceTransformers` 384-dim embedding shape & LRU cache | PASS (100%) |
| `tests/test_hybrid_search.py` | 2 tests | In-memory BM25 scoring & Reciprocal Rank Fusion (RRF) | PASS (100%) |
| `tests/test_image_association.py` | 2 tests | Manual chunk to visual image payload linking | PASS (100%) |
| `tests/test_image_extraction.py` | 2 tests | PyMuPDF raster image extraction & pHash filtering | PASS (100%) |
| `tests/test_mcp_integration.py` | 7 tests | FastMCP tools (`search`, `error_code`, `thermistor`, `part_number`, `run_agent`, `troubleshoot`) & `/mcp/sse` mount | PASS (100%) |
| `tests/test_parser.py` | 1 test | Microsoft `MarkItDown` document parsing | PASS (100%) |
| `tests/test_product_identifier.py` | 2 tests | Zero-shot product entity extraction | PASS (100%) |
| `tests/test_retriever.py` | 1 test | 3-level waterfall search strategy | PASS (100%) |
| `tests/test_troubleshooting_agent.py`| 1 test | Multi-turn state machine session turns | PASS (100%) |
| `tests/test_vector_store.py` | 1 test | Qdrant dual collection indexing & source deletion | PASS (100%) |
| `tests/test_vision_pipeline.py` | 5 tests | SigLIP 2 visual embeddings & joint text-image search | PASS (100%) |

---

## 4. Local Environment & Sandbox Storage Layout

```text
backend/data_sandbox/
├── registry.db                         # SQLite database tracking file/URL MD5 version hashes
├── qdrant_db/                          # Qdrant local storage directory
│   └── collection/
│       ├── manuals/                    # 384-dim dense text chunk vectors collection
│       └── manual_images/              # 768-dim SigLIP 2 visual image vectors collection
└── outputs/
    └── images/                         # Extracted CAD path diagrams and PNGs by document ID
        └── {document_id}/
            ├── metadata.json           # Image bounding box & page location index
            └── {image_id}.png          # Rendered PNG diagram file
```
