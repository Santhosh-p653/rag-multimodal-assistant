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
