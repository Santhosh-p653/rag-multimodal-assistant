# Multimodal RAG Assistant & Agentic Troubleshooting Engine

A production-ready **Multimodal Retrieval-Augmented Generation (RAG) Assistant** and **State-Guided Agentic Engine** designed to ingest technical manuals, perform context-aware hierarchical search, retrieve semantically relevant visual diagrams using vision-language embeddings, handle voice-based communications, execute multi-turn diagnostic troubleshooting workflows, and enforce strict security policies.

---

## 🚀 Key Features

* **📄 Multimodal Document Ingestion**: Converts uploads (`PDF`, `DOCX`, `PPTX`, `XLSX`, `TXT`) into Markdown using **Microsoft MarkItDown**, performing zero-shot product classification. Extracts raster images and natively renders vector diagrams (via PyMuPDF), associating them with text chunks using semantic cosine similarity.
* **🖼️ SigLIP 2 Vision Retrieval Pipeline**: Uses Google's **SigLIP 2** (`google/siglip-base-patch16-224`) vision-language model to embed both images and text queries into a shared 768-dimensional multimodal space. At query time, a text query is encoded and matched against stored image embeddings in the dedicated `manual_images` Qdrant collection, enabling true semantic image search independent of text chunk retrieval.
* **🔍 Hierarchical Hybrid Search**: Searches Qdrant using a 3-level priority hierarchy (Exact Match → Family Match → Global Match) combining dense (MiniLM-L6) and sparse (BM25) candidates using **Reciprocal Rank Fusion (RRF)**.
* **🧠 Context Reconstruction & Clarification**: Employs an LLM query-understanding layer to gauge user intent, reconstruct ambiguous follow-up queries using session state, and gracefully trigger clarification dialogues when input confidence is low.
* **🎙️ Hybrid Voice Layer**: Captures audio input and routes transcription based on language hint (local Whisper for English; remote Sarvam AI Saaras v3 API for Indic languages). Synthesizes speech outputs using **edge-tts** with Microsoft Neural voices.
* **🤖 Agentic Troubleshooting Engine**: Guides users through diagnostic trees tracking session parameters, history, and RAG context blocks across turns.
* **🦜 Unified Agentic Flow**: Uses LangGraph `StateGraph` to orchestrate ingestion, query analysis, fuzzy product ID resolution, RRF retrieval, image filtering, SigLIP vision retrieval, and LLM generation through a single robust pipeline.
* **🛡️ Security & Hardening**:
  * **Rate Limiting**: Integrated `slowapi` rate limits on all major endpoints.
  * **File Upload Guard**: Restricts upload sizes to `<= 25MB` and validates file MIME types/extensions.
  * **Prompt Injection Protection**: Employs regex guards (`prompt_guard.py`) to block jailbreak/override instructions.
  * **Isolated Prompts**: Isolates RAG system prompts, instructing the LLM to treat manual instructions strictly as data, not commands.
  * **Secrets & CI**: Never tracks `.env` keys. Includes GitHub Actions workflows for quality checks (`ruff`, `black`, `bandit`) and secret scanning (`detect-secrets`).
* **🧪 34-Test Suite**: Comprehensive mock-heavy unit, integration, security, and vision pipeline checks under `backend/tests/` covering the full stack from embeddings to Qdrant ingestion/search.

---

## 📁 Project Structure

```text
rag-multimodal-assistant/
├── docker-compose.yml         # Container configuration for Backend + Frontend
├── contributing.md            # Onboarding & Local Setup guide
├── architecture.md            # System architectures & Orchestration flowcharts
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt       # Hardened requirements (slowapi, pytest, bandit, etc.)
│   ├── .env.example           # Environment template file
│   └── app/
│       ├── main.py            # FastAPI Application routes & Rate limiter setup
│       ├── config.py          # Unified Settings manager using pathlib.Path
│       └── services/
│           ├── parser.py           # MarkItDown document parse & metadata extractor
│           ├── chunker.py          # Smart overlapping parser chunker
│           ├── embedder.py         # Local SentenceTransformer embeddings (384-dim)
│           ├── vector_store.py     # Qdrant interface: text + image collections
│           ├── hybrid_search.py    # In-memory BM25 sparse search and RRF
│           ├── retriever.py        # 3-level prioritized retriever + vision retrieval
│           ├── vision_embedder.py  # SigLIP 2 singleton (image & text encoding, 768-dim)
│           ├── vision_search.py    # Semantic image retrieval against manual_images
│           ├── metadata_resolver.py# Qdrant filter builder from query entities
│           ├── image_extractor.py  # PyMuPDF raster + vector image extraction
│           ├── image_filters.py    # Aspect ratio, area, pHash deduplication filters
│           ├── audio.py            # Speech Transcriber (Whisper/Sarvam) & TTS (edge-tts)
│           ├── prompt_guard.py     # Prompt injection filter
│           ├── prompt_builder.py   # Structured LLM prompt assembly
│           ├── agent_flow.py       # LangGraph unified ingestion & RAG graph
│           ├── troubleshooting_agent.py  # Multi-turn diagnostic agent
│           └── workflow_manager.py # Troubleshooting state machine
└── frontend/                  # Next.js UI app codebase
```

---

## 🏗️ Architecture & Documentation

For in-depth explanations, mermaid data flows, and state transition flowcharts, see the detailed documentation files:

1. **[Setup Instructions (setup.md)](setup.md)**: Detailed step-by-step instructions on how to configure API keys, install dependencies, and launch the application locally or via Docker.
2. **[Architecture Specifications (architecture.md)](architecture.md)**: Technical breakdown, Mermaid flowcharts, and schema definitions for the LangGraph state machine, SigLIP vision pipeline, fusion algorithm, and voice layer.
3. **[Project Context & Lifecycle (context.md)](context.md)**: A deep-dive micro-observation narrative detailing exactly what happens to a document from upload to ingestion, and how a user's prompt is validated, reconstructed, and executed.

---

## ⚙️ Configuration & Run

### 1. Setup Environment
Create a `backend/.env` file from the example template:
```bash
cp backend/.env.example backend/.env
```
Fill in the API keys:
```env
GROQ_API_KEY=your_groq_key
SAMBANOVA_API_KEY=your_sambanova_key
SARVAM_API_KEY=your_sarvam_key
```

### 2. Launch with Docker Compose
To build and run the entire ecosystem (FastAPI Backend + Next.js Frontend) locally:
```bash
docker compose up --build
```

### 3. Verification & Testing
To run the 34-test suite locally inside the backend directory:
```bash
cd backend
pytest -vv
```

---

## 🚀 Access Points
* **Frontend UI**: http://localhost:3000
* **Admin Upload Panel**: http://localhost:3000/admin
* **Backend Docs / API**: http://localhost:8000/docs
* **Unified Agent Flow**: `POST http://localhost:8000/agent/run`
* **Health endpoint**: http://localhost:8000/health
