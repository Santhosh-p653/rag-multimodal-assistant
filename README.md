# Multimodal RAG Assistant

A production-ready **Multimodal Retrieval-Augmented Generation (RAG) Assistant** designed to ingest technical manuals and documents, ground LLM responses strictly on uploaded content, and prevent hallucinations using a robust retrieval pipeline.

This project focuses on **correct RAG engineering practices**, not just demo-level chatbot behavior.

---

## 🚀 Features (Current Status)

- 📄 **Multimodal Document Ingestion**
  - Supports: `PDF`, `DOCX`, `PPTX`, `XLSX`, `TXT`
  - Uses **Microsoft MarkItDown** to convert documents into clean Markdown

- ✂️ **Smart Chunking**
  - Character-based chunking with overlap for better semantic continuity

- 🧠 **Local Embeddings**
  - Uses `sentence-transformers/all-MiniLM-L6-v2`
  - 384-dimensional dense vectors
  - Cosine similarity search

- 📦 **In-Memory Vector Store**
  - Powered by **Qdrant**
  - Runs locally inside the backend process (fast dev iteration)

- 🔍 **Grounded RAG Pipeline**
  - Retrieves top-k relevant chunks
  - Injects only retrieved context into the LLM prompt
  - Strict system prompt prevents hallucination

- 🤖 **Multi-LLM Provider Support**
  - Primary: **Groq** (`llama-3.1-8b-instant`)
  - Fallback: **SambaNova** (`Meta-Llama-3.1-8B-Instruct`)
  - Auto-detection via environment variables

- 🧾 **Source Attribution**
  - Responses show document source badges
  - If no grounded answer is found, sources are suppressed

- 🐳 **Fully Dockerized**
  - Backend + Frontend orchestrated via Docker Compose
  - Embedding model is pre-cached during image build for fast startup

---

## 🏗️ Architecture Overview

## 📁 Project Structure


rag-multimodal-assistant/
├── docker-compose.yml
├── test_manual.txt
├── backend/
│ ├── Dockerfile
│ ├── requirements.txt
│ ├── .env
│ └── app/
│ ├── main.py
│ ├── config.py
│ └── services/
│ ├── parser.py
│ ├── chunker.py
│ ├── embedder.py
│ ├── vector_store.py
│ ├── retriever.py
│ └── prompt_builder.py
└── frontend/
├── Dockerfile
├── package.json
└── src/
├── components/
├── lib/
└── pages/


---

## ⚙️ Configuration

### Backend Environment Variables

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key
SAMBANOVA_API_KEY=your_sambanova_api_key
```

The backend automatically selects the available provider.

▶️ Running the Project

From the project root:

-  docker compose up --build
## Access Points
- Backend Health: http://localhost:8000/health
- Frontend UI: http://localhost:3000
- Admin Upload Panel: http://localhost:3000/admin
