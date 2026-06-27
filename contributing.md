# Contributing to Multimodal RAG Assistant

Welcome to the **Multimodal RAG Assistant**! This guide will help you set up the project locally for development, understand the architecture, and contribute new features.

---

## 🏗️ Project Architecture

The project is structured as a decoupled monorepo:
* **`backend/`**: A FastAPI application.
  * **Parser**: Converts PDFs, Word files, slides, and sheets using Microsoft MarkItDown into clean Markdown.
  * **Embeddings**: Uses `sentence-transformers/all-MiniLM-L6-v2` locally for dense embeddings (384 dimensions).
  * **Vector Database**: Runs an in-memory instance of Qdrant.
  * **Hybrid Search**: Merges dense search scores and keyword BM25 retrieval using Reciprocal Rank Fusion (RRF) with optional metadata filtering by document source.
  * **LLM Engine**: Automatically routes requests to Groq or SambaNova based on your configured API keys.
  * **Voice Integration**: Implements local Whisper STT (via `faster-whisper`), remote Sarvam AI STT, and free Microsoft Neural Voice text-to-speech (via `edge-tts`).
* **`frontend/`**: A Next.js Web App built with React, TailwindCSS, and Lucide React.
  * Responsive chat layout with inline voice recording controls, manual selector dropdown, and automatic TTS playback.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:
- **Python**: version `3.11.x`
- **Node.js**: version `18.x` or higher
- **FFmpeg**: Required for audio transcoding (installed in Docker, but must be in your local system PATH for local non-Docker development)
- **Docker**: (Optional) For running everything containerized

---

## 🚀 Local Development Setup

Follow these steps to set up the project locally:

### 1. Backend Setup

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend/` directory:
   ```env
   GROQ_API_KEY=your-groq-api-key
   SAMBANOVA_API_KEY=your-sambanova-api-key
   SARVAM_API_KEY=your-sarvam-api-key
   ```
5. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   The backend API will be available at `http://localhost:8000`. You can access the API docs at `http://localhost:8000/docs`.

### 2. Frontend Setup

1. Navigate to the `frontend/` directory:
   ```bash
   cd ../frontend
   ```
2. Install the node modules:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The frontend UI will be available at `http://localhost:3000`.

---

## 🐳 Docker Compose Setup

If you prefer to run the entire stack inside containers:

1. Create a `backend/.env` file with the required API keys.
2. Run the following command from the project root:
   ```bash
   docker compose up --build
   ```
3. The frontend is accessible at `http://localhost:3000` and the backend at `http://localhost:8000`.

---

## 🤝 Contribution Guidelines

1. **Branch Naming Conventions**:
   - Features: `feature/your-feature-name`
   - Bug fixes: `bugfix/your-bug-name`
   - Hotfixes: `hotfix/your-hotfix-name`
2. **Linting and Formatting**:
   - Backend: Keep code clean, type annotated, and structured within modular services.
   - Frontend: Use TypeScript, ensure correct styling with Tailwind CSS, and keep components modular.
3. **Commit Messages**:
   - Write clear, concise commit messages outlining the "what" and "why" (e.g., `feat: add BM25 hybrid search and RRF`).
