# Setup Guide

This document outlines every micro-step required to configure, initialize, and execute the Multimodal RAG Assistant project either natively on your machine or via Docker.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your machine:
1. **Python 3.10+**: Required for the backend services, PyMuPDF, and machine learning models.
2. **Node.js 18+**: Required for the Next.js frontend UI.
3. **Docker Desktop** (Optional): Only required if you wish to run the containerized deployment.

---

## 🖥️ Method 1: Local Native Execution (Recommended for Development)

### Step 1: Backend Setup & Configuration

1. **Navigate to the backend directory:**
   ```powershell
   cd rag-multimodal-assistant\backend
   ```

2. **Create a Python Virtual Environment:**
   ```powershell
   python -m venv venv
   ```

3. **Activate the Virtual Environment:**
   * On Windows: `.\venv\Scripts\activate`
   * On macOS/Linux: `source venv/bin/activate`

4. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Configure Environment Variables:**
   Create a `.env` file inside the `backend/` folder by duplicating `.env.example`:
   ```powershell
   cp .env.example .env
   ```
   Open `.env` in a text editor and fill in your API keys:
   ```env
   # Required for LLM Generation
   GROQ_API_KEY="your_groq_api_key" 
   
   # Optional (Required only for Indic Voice Translation)
   SARVAM_API_KEY="your_sarvam_key"
   ```

6. **Start the Backend Server:**
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Note: On the first boot, the SentenceTransformers `all-MiniLM-L6-v2` embedding model will download to your local cache. HuggingFace network checks have been disabled to ensure offline stability.*

---

### Step 2: Frontend Setup

1. **Open a new terminal and navigate to the frontend directory:**
   ```powershell
   cd rag-multimodal-assistant\frontend
   ```

2. **Install Node Modules:**
   ```powershell
   npm install
   ```

3. **Start the Development Server:**
   ```powershell
   npm run dev
   ```

4. **Access the Application:**
   Open your browser and navigate to **`http://localhost:3000`**.

---

## 🐳 Method 2: Docker Deployment

If you prefer to run the application in isolated containers without installing Python or Node.js locally, use Docker Compose.

1. **Ensure Docker Desktop is Running:**
   Open Docker Desktop from your start menu and wait for the engine icon to indicate it is ready.

2. **Configure Environment Variables:**
   Ensure your `backend/.env` file is created and populated with your API keys (as described in Step 1.5 above).

3. **Build and Launch the Containers:**
   From the root `rag-multimodal-assistant` directory, run:
   ```powershell
   docker compose up --build
   ```

4. **Access the Application:**
   * UI: `http://localhost:3000`
   * Backend API: `http://localhost:8000`

---

## 🧪 Testing the Pipeline

To verify the logic and security configurations, a comprehensive pytest suite is available.
1. Navigate to the `backend/` folder.
2. Ensure your virtual environment is active.
3. Run the test suite:
   ```powershell
   pytest -vv
   ```
