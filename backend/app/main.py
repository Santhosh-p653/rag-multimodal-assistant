"""
main.py — FastAPI application for the Multimodal RAG Assistant.
Phase 3: Full RAG pipeline — embed → retrieve → prompt → LLM → grounded answer.
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.services.parser import ParserService
from app.services.retriever import retrieve_context
from app.services.prompt_builder import build_prompt
from app.config import LLM_PROVIDER, LLM_MODEL, GROQ_API_KEY, SAMBANOVA_API_KEY

app = FastAPI(title="Multimodal RAG Assistant API", version="3.0.0")

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Eagerly initialize services (loads embedding model at startup)
parser_service = ParserService()

# ─── Pydantic Models ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    vectors_stored: int

class UploadResponse(BaseModel):
    filename: str
    markdown_file: str
    chunks_ingested: int
    status: str

# ─── LLM Helper ─────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    """Call the configured LLM provider and return the response text."""

    if LLM_PROVIDER == "groq":
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()

    elif LLM_PROVIDER == "sambanova":
        from openai import OpenAI
        client = OpenAI(
            api_key=SAMBANOVA_API_KEY,
            base_url="https://api.sambanova.ai/v1",
        )
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()

    else:
        raise RuntimeError(
            "No LLM API key configured. Add GROQ_API_KEY or SAMBANOVA_API_KEY to backend/.env"
        )

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    from app.services.vector_store import VectorStoreService
    vs = VectorStoreService()
    return {
        "status": "ok",
        "llm_provider": LLM_PROVIDER,
        "vectors_stored": vs.count(),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    RAG chat endpoint:
      1. Retrieve relevant chunks from Qdrant
      2. If no chunks found → return safe fallback
      3. Build grounded prompt
      4. Call LLM
      5. Return answer + unique source files
    """
    fallback = "I could not find that information in the uploaded manuals."

    # Step 1: Retrieve context
    chunks = retrieve_context(request.message)

    # Step 2: Fallback if nothing retrieved
    if not chunks:
        return ChatResponse(answer=fallback, sources=[])

    # Step 3: Build prompt
    prompt = build_prompt(chunks, request.message)

    # Step 4: Call LLM
    try:
        answer = call_llm(prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

    # Step 5: Collect unique sources
    normalized_answer = answer.strip().rstrip(".").lower()
    normalized_fallback = fallback.strip().rstrip(".").lower()
    if normalized_answer == normalized_fallback:
        sources = []
    else:
        sources = list(dict.fromkeys(c["source"] for c in chunks))

    return ChatResponse(answer=answer, sources=sources)


@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a document, convert it, chunk it, embed it, and store in Qdrant."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    if not parser_service.is_supported(file.filename):
        supported = ", ".join(sorted(parser_service.supported_extensions))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {supported}",
        )

    try:
        content = await file.read()
        result = parser_service.parse_file(file.filename, content)
        return UploadResponse(
            filename=file.filename,
            markdown_file=result["markdown_file"],
            chunks_ingested=result["chunks_ingested"],
            status="processed",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))