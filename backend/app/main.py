"""
main.py — FastAPI application for the Multimodal RAG Assistant.
Phase 3: Full RAG pipeline — embed → retrieve → prompt → LLM → grounded answer.
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app.services.parser import ParserService
from app.services.retriever import retrieve_context
from app.services.prompt_builder import build_prompt
from app.config import settings, LLM_PROVIDER, LLM_MODEL, GROQ_API_KEY, SAMBANOVA_API_KEY
from app.services.prompt_guard import is_prompt_injection, is_out_of_domain

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize PostgreSQL schema
    try:
        from app.database.postgres import init_postgres_db
        await init_postgres_db()
    except Exception as e:
        print(f"[Startup] PostgreSQL init notice: {e}")

    # Pre-warm embedding models into RAM on server startup to eliminate cold-start upload/chat delay
    try:
        print("[Startup] Pre-warming text and vision embedding models...")
        from app.services.embedder import EmbedderService
        from app.services.vision_embedder import VisionEmbedderService
        EmbedderService()
        VisionEmbedderService()
        print("[Startup] Embedding models ready in RAM.")
    except Exception as e:
        print(f"[Startup] Model pre-warming warning: {e}")
    yield

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="OCTO-RAG Assistant API", version="3.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.mcp.fridge_mcp_server import mcp as fridge_mcp_server
from app.mcp.auto_mcp_server import mcp as auto_mcp_server

# Mount MCP Servers (Server-Sent Events transport at /mcp/sse and /auto_mcp/sse)
app.mount("/mcp", fridge_mcp_server.sse_app())
app.mount("/auto_mcp", auto_mcp_server.sse_app())

# Eagerly initialize services (loads embedding model at startup)
parser_service = ParserService()

# ─── Pydantic Models ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    source_file: Optional[str] = None
    session_id: Optional[str] = None
    language: Optional[str] = "auto"
    image_base64: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    needs_clarification: bool = False
    clarification_question: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    vectors_stored: int
    postgres_connected: bool = False
    postgres_status: str = "disconnected"
    postgres_stats: dict = {}

class UploadResponse(BaseModel):
    filename: str
    markdown_file: str
    chunks_ingested: int
    status: str

class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    language: Optional[str] = "auto"

class TroubleshootRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)

class AgentRequest(BaseModel):
    query: str
    source_input: Optional[str] = None
    session_id: Optional[str] = None
    language: Optional[str] = "auto"
    image_base64: Optional[str] = None

class AgentResponse(BaseModel):
    answer: str
    steps: list[str] = []
    sources: list[dict] = []
    product_id: Optional[str] = None
    clarification_needed: bool = False
    version_info: Optional[str] = None
    clarification_question: Optional[str] = None
    status: Optional[str] = None
    images: list[dict] = []

from app.services.llm_provider import generate, llm_provider

# ─── LLM Helper ─────────────────────────────────────────────────────────────

def call_llm(
    prompt: str,
    task: str = "chat",
    system_prompt: Optional[str] = None,
    **kwargs,
) -> str:
    """Call the unified LLM provider (Ollama primary with automatic cloud fallback)."""
    return generate(prompt, task=task, system_prompt=system_prompt, **kwargs)

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    from app.services.vector_store import VectorStoreService
    from app.database.postgres import check_postgres_health
    vs = VectorStoreService()
    active_provider = (
        "ollama" if (llm_provider.ollama_enabled and llm_provider.last_provider_used == "ollama")
        else (llm_provider.last_provider_used if llm_provider.last_provider_used != "none" else ("ollama" if llm_provider.ollama_enabled else LLM_PROVIDER))
    )
    pg_ok, pg_status, pg_stats = await check_postgres_health()
    return {
        "status": "ok",
        "llm_provider": active_provider,
        "vectors_stored": vs.count(),
        "postgres_connected": pg_ok,
        "postgres_status": pg_status,
        "postgres_stats": pg_stats,
    }


@app.get("/health/llm")
async def health_llm():
    """Detailed LLM and PostgreSQL provider telemetry."""
    from app.database.postgres import check_postgres_health
    status = llm_provider.get_status()
    pg_ok, pg_status, pg_stats = await check_postgres_health()
    status["postgres"] = {
        "connected": pg_ok,
        "status": pg_status,
        "telemetry": pg_stats
    }
    return status


@app.get("/files")
async def get_files():
    """Retrieve all unique source files loaded in storage, PostgreSQL registry, and vector store."""
    from app.services.vector_store import VectorStoreService
    from app.database.postgres import list_registered_manuals
    from pathlib import Path
    vs = VectorStoreService()
    try:
        sources = set(vs.get_unique_sources())
        pg_manuals = await list_registered_manuals()
        for m in pg_manuals:
            if m.get("filename"):
                sources.add(m["filename"])

        input_dir = Path(settings.INPUT_DIR)
        if input_dir.exists():
            for f in input_dir.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    sources.add(f.name)
        return {"files": sorted(list(sources)), "registry": pg_manuals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """
    Delete a manual completely:
    1. Remove raw file from input_manuals/
    2. Remove processed markdown from processed_markdown/
    3. Remove extracted figures/images from processed_markdown/images/{base_name}
    4. Remove vector embeddings from Qdrant 'manuals' collection
    5. Remove image embeddings from Qdrant 'manual_images' collection
    6. Remove entry from PostgreSQL manual_registry
    7. Remove entry from SQLite registry.db (backward compatibility)
    """
    import os
    import shutil
    import sqlite3
    from pathlib import Path
    from app.services.vector_store import VectorStoreService
    from app.database.postgres import delete_registered_manual

    safe_filename = os.path.basename(filename)
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    base_name, _ = os.path.splitext(safe_filename)

    # 1. Remove raw file
    raw_path = Path(settings.INPUT_DIR) / safe_filename
    if raw_path.exists():
        try:
            raw_path.unlink()
        except Exception as e:
            logger.error(f"Error removing raw file {raw_path}: {e}")

    # 2. Remove markdown file
    md_path = Path(settings.OUTPUT_DIR) / f"{base_name}.md"
    if md_path.exists():
        try:
            md_path.unlink()
        except Exception as e:
            logger.error(f"Error removing markdown file {md_path}: {e}")

    # 3. Remove extracted images folder
    images_dir = Path(settings.OUTPUT_DIR) / "images" / base_name
    if images_dir.exists():
        try:
            shutil.rmtree(images_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Error removing images dir {images_dir}: {e}")

    # 4. Remove vectors from Qdrant
    vs = VectorStoreService()
    try:
        vs.delete_by_filename(safe_filename)
        vs.delete_images_by_filename(safe_filename)
    except Exception as e:
        logger.error(f"Error deleting vectors for {safe_filename}: {e}")

    # 5. Remove from PostgreSQL manual_registry
    try:
        await delete_registered_manual(safe_filename)
    except Exception as e:
        logger.error(f"Error clearing PostgreSQL registry for {safe_filename}: {e}")

    # 6. Remove from SQLite registry.db
    reg_path = Path(settings.INPUT_DIR).parent / "registry.db"
    if reg_path.exists():
        try:
            conn = sqlite3.connect(str(reg_path))
            c = conn.cursor()
            c.execute("DELETE FROM registry WHERE filepath = ? OR filepath = ?", (safe_filename, f"{base_name}.md"))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error clearing registry for {safe_filename}: {e}")

    try:
        from app.services.retriever import clear_retrieval_cache
        clear_retrieval_cache()
    except Exception:
        pass

    return {"status": "deleted", "filename": safe_filename}


@app.post("/admin/reset")
def reset_all_manuals():
    """Wipe all manuals, markdown, extracted images, Qdrant vectors, and registry."""
    import shutil
    import sqlite3
    from pathlib import Path
    from app.services.vector_store import VectorStoreService

    input_dir = Path(settings.INPUT_DIR)
    if input_dir.exists():
        for f in input_dir.iterdir():
            if f.is_file():
                f.unlink()

    output_dir = Path(settings.OUTPUT_DIR)
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir() and item.name == "images":
                shutil.rmtree(item, ignore_errors=True)

    vs = VectorStoreService()
    vs.clear_all()

    reg_path = Path(settings.INPUT_DIR).parent / "registry.db"
    if reg_path.exists():
        conn = sqlite3.connect(str(reg_path))
        c = conn.cursor()
        c.execute("DELETE FROM registry")
        conn.commit()
        conn.close()

    return {"status": "ok", "message": "All manuals and index data successfully wiped."}

@app.get("/debug_qdrant")
def debug_qdrant():
    from app.services.vector_store import VectorStoreService, QDRANT_COLLECTION
    vs = VectorStoreService()
    res, _ = vs.client.scroll(collection_name=QDRANT_COLLECTION, limit=500, with_payload=True)
    sources = {}
    for p in res:
        sf = p.payload.get("source_file") or p.payload.get("source") or "unknown"
        sources[sf] = sources.get(sf, 0) + 1
    return {"total": len(res), "sources_count": sources}


@app.get("/products")
def get_products():
    """Retrieve all unique product names loaded in the vector store."""
    from app.services.vector_store import VectorStoreService
    vs = VectorStoreService()
    try:
        products = vs.get_unique_products()
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list products: {str(e)}")


def build_clarification_from_ambiguity(raw: str) -> str:
    """
    Validates an LLM-produced ambiguity string before serving it to the user.
    Falls back to a constructed generic-but-topic-aware question if the
    raw string doesn't look like a real question.
    """
    if not raw or not isinstance(raw, str):
        return "Could you clarify what you're referring to?"

    cleaned = raw.strip()

    # Minimum sanity checks — not full NLP validation, just guard against
    # empty strings, junk tokens, or non-question fragments.
    if len(cleaned) < 10:
        return "Could you clarify what you're referring to?"
    if not cleaned.endswith("?"):
        # Doesn't look like a question — still usable as context, but
        # wrap it rather than serve it raw.
        return f"Could you clarify: {cleaned}"

    return cleaned


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(payload: ChatRequest, request: Request):
    """
    Phase 1 & 2 RAG chat endpoint with Query Understanding, Relevance Guard, and Stateful Clarification.
    """
    if is_prompt_injection(payload.message):
        raise HTTPException(status_code=400, detail="Potential prompt injection detected.")
    if is_out_of_domain(payload.message):
        raise HTTPException(
            status_code=400,
            detail="I am specialized strictly in automotive and vehicle technical diagnostics. Please ask a query related to your vehicle service manual, OBD-II error codes, or mechanical troubleshooting."
        )

    from app.config import MAX_CLARIFICATION_ATTEMPTS
    session_id = payload.session_id
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    from app.services.session_store import SessionStore
    session_store = SessionStore()
    session = session_store.get(session_id)

    user_message = payload.message

    # --- Phase 2: Context Reconstruction ---
    if session.get("pending_clarification"):
        session["clarification_attempts"] = session.get("clarification_attempts", 0) + 1
        if session["clarification_attempts"] > MAX_CLARIFICATION_ATTEMPTS:
            session["pending_clarification"] = False
            session["clarification_attempts"] = 0
            session_store.save(session_id, session)
            return ChatResponse(
                answer="I'm still having trouble understanding. Could you please state the product model and the issue you're facing in one complete sentence?",
                sources=[],
                needs_clarification=False
            )
        
        from app.services.context_reconstruction import reconstruct_query
        resolved_query, res_conf = reconstruct_query(
            original_query=session.get("last_valid_user_query", ""),
            clarification_question=session.get("clarification_question", ""),
            user_followup=user_message,
            product_hint=session.get("product")
        )

        if is_prompt_injection(resolved_query):
            raise HTTPException(status_code=400, detail="Potential prompt injection detected in reconstructed query.")
        if is_out_of_domain(resolved_query):
            raise HTTPException(
                status_code=400,
                detail="I am specialized strictly in automotive and vehicle technical diagnostics. Please ask a query related to your vehicle service manual, OBD-II error codes, or mechanical troubleshooting."
            )

        if res_conf == "LOW":
            # If the follow-up makes no sense, trigger another clarification immediately
            session_store.save(session_id, session)
            return ChatResponse(
                answer=f"I didn't quite catch that. {session.get('clarification_question', 'Could you clarify?')}",
                sources=[],
                needs_clarification=True,
                clarification_question=session.get("clarification_question")
            )

        # Replace user_message with the semantically resolved query
        user_message = resolved_query
        session["pending_clarification"] = False
        session["clarification_attempts"] = 0

    # --- Record user turn in PostgreSQL ---
    from app.database.postgres import record_session_turn
    try:
        await record_session_turn(
            session_id=session_id,
            sender="user",
            message_text=payload.message,
            equipment_model=session.get("product"),
            status="ACTIVE"
        )
    except Exception as e:
        logger.warning(f"[PostgreSQL] Failed to record chat user turn: {e}")

    fallback = "I could not find that information in the uploaded manuals."

    from app.services.query_understanding import understand_query
    understood = understand_query(user_message)

    # Step 3: Direct Retrieval - Always search manuals first
    chunks, retrieval_confidence = retrieve_context(
        understood.get("normalized_query", user_message),
        source_file=payload.source_file,
        query_entities=understood.get("entities", {})
    )

    # Step 4: Route on retrieval_confidence
    if retrieval_confidence == "LOW":
        # Extend fallback for LOW relevance or zero results
        low_fallback = fallback + " The query might be too vague or unrelated to the manuals."
        try:
            await record_session_turn(
                session_id=session_id,
                sender="assistant",
                message_text=low_fallback,
                equipment_model=session.get("product"),
                status="NO_RESULTS"
            )
        except Exception:
            pass
        return ChatResponse(answer=low_fallback, sources=[])
        
    elif retrieval_confidence == "MEDIUM":
        # Check product match if hint provided
        product_hint = understood.get("product_hint")
        if product_hint and chunks:
            top_chunk_product = chunks[0].get("product", "")
            if top_chunk_product and product_hint.lower() not in top_chunk_product.lower():
                # Ask clarifying question if product mismatch
                clarification_q = f"I found some information for {top_chunk_product}, but you asked about {product_hint}. Should I proceed with the details for {top_chunk_product}?"
                try:
                    await record_session_turn(
                        session_id=session_id,
                        sender="assistant",
                        message_text=clarification_q,
                        question=clarification_q,
                        equipment_model=top_chunk_product,
                        status="NEED_CLARIFICATION"
                    )
                except Exception:
                    pass
                return ChatResponse(
                    answer=clarification_q,
                    sources=[],
                    needs_clarification=True,
                    clarification_question=clarification_q
                )
        
        # Build prompt instructing to hedge
        base_prompt = build_prompt(chunks, payload.message)
        prompt = base_prompt + "\n\nNote: The context provided may only partially cover the question. Please hedge your answer and note any uncertainty."
    else:
        # HIGH confidence
        prompt = build_prompt(chunks, payload.message)

    # Step 5: Call LLM
    from starlette.concurrency import run_in_threadpool
    try:
        answer = await run_in_threadpool(call_llm, prompt, task="chat")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

    # Collect unique sources
    normalized_answer = answer.strip().rstrip(".").lower()
    normalized_fallback = fallback.strip().rstrip(".").lower()
    if normalized_answer == normalized_fallback or normalized_answer.startswith("i could not find"):
        sources = []
    else:
        sources = list(dict.fromkeys(c["source"] for c in chunks))

    # Successful turn, save product state if extracted
    if understood.get("product_hint"):
        session["product"] = understood.get("product_hint")
    session_store.save(session_id, session)

    # Record assistant turn in PostgreSQL
    try:
        await record_session_turn(
            session_id=session_id,
            sender="assistant",
            message_text=answer,
            equipment_model=session.get("product"),
            status="ANSWERED"
        )
    except Exception as e:
        logger.warning(f"[PostgreSQL] Failed to record chat assistant turn: {e}")

    return ChatResponse(answer=answer, sources=sources)


@app.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(request: Request, payload: ChatRequest):
    """
    Streaming endpoint returning Server-Sent Events (SSE) for low TTFT response streaming.
    """
    from fastapi.responses import StreamingResponse
    import asyncio

    # Prompt injection check
    if is_prompt_injection(payload.message):
        raise HTTPException(status_code=400, detail="Security Violation: Invalid input detected.")
    if is_out_of_domain(payload.message):
        raise HTTPException(
            status_code=400,
            detail="I am specialized strictly in automotive and vehicle technical diagnostics. Please ask a query related to your vehicle service manual, OBD-II error codes, or mechanical troubleshooting."
        )

    chunks, confidence = retrieve_context(payload.message, source_file=payload.source_file)
    if confidence == "LOW" or not chunks:
        async def fallback_generator():
            yield "data: I could not find relevant technical manual documentation to answer your query.\n\n"
        return StreamingResponse(fallback_generator(), media_type="text/event-stream")

    prompt = build_prompt(chunks, payload.message)
    full_answer = call_llm(prompt, task="chat")

    async def token_generator():
        # Stream response tokens/words incrementally for real-time UI rendering
        words = full_answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0.015)
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")


@app.post("/upload", response_model=UploadResponse)
@limiter.limit("60/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Upload a document, convert it, chunk it, embed it, and store in Qdrant."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    # Validate file size (25MB limit)
    MAX_FILE_SIZE = 25 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Max size allowed is 25MB."
        )

    # Validate file extension
    allowed_extensions = {".pdf", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"}
    import os
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_extensions:
        supported = ", ".join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {supported}",
        )

    # Validate MIME type
    allowed_mime_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.ms-excel",
        "text/plain"
    }
    if file.content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type '{file.content_type}' is not allowed.",
        )

    # Check duplicate in PostgreSQL manual_registry via MD5 hash
    from app.database.postgres import check_manual_duplicate_by_hash, register_manual
    duplicate = await check_manual_duplicate_by_hash(content)
    if duplicate:
        logger.info(f"[PostgreSQL] Duplicate upload skipped: {file.filename} matches existing hash for {duplicate.get('filename')}")
        return UploadResponse(
            filename=file.filename,
            markdown_file=f"{os.path.splitext(file.filename)[0]}.md",
            chunks_ingested=duplicate.get("chunks_count", 0),
            status="skipped_duplicate",
        )

    try:
        result = parser_service.parse_file(file.filename, content)

        # Register in PostgreSQL manual_registry
        try:
            await register_manual(
                filename=file.filename,
                file_bytes=content,
                equipment_type="industrial",
                chunks_count=result["chunks_ingested"]
            )
        except Exception as pg_err:
            logger.warning(f"[PostgreSQL] Failed to register {file.filename}: {pg_err}")

        # Sync legacy SQLite registry with ingested file hash
        try:
            import hashlib
            import sqlite3
            from pathlib import Path
            reg_path = Path(settings.INPUT_DIR).parent / "registry.db"
            if reg_path.exists():
                content_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()
                conn = sqlite3.connect(str(reg_path))
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO registry (filepath, hash, version) VALUES (?, ?, 1)", (file.filename, content_hash))
                conn.commit()
                conn.close()
        except Exception as reg_err:
            logger.warning(f"Failed to update SQLite registry for {file.filename}: {reg_err}")

        return UploadResponse(
            filename=file.filename,
            markdown_file=result["markdown_file"],
            chunks_ingested=result["chunks_ingested"],
            status="processed",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe")
@limiter.limit("60/minute")
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    hint_lang: str = Form("auto")
):
    """Transcribe uploaded audio file using hybrid local/remote engines."""
    import tempfile
    import os

    content = await audio.read()
    if not content or len(content) < 50:
        return {"text": "", "detected_language": hint_lang}

    # Write to a temporary file
    suffix = os.path.splitext(audio.filename or ".wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        tmp_path = tmp.name

    try:
        from app.services.audio import transcribe_audio
        result = await transcribe_audio(tmp_path, hint_lang)
        return result
    except Exception as e:
        logger.error(f"[Audio] Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.get("/document-images/{document_id}/{image_id}")
@limiter.limit("60/minute")
async def get_document_image(request: Request, document_id: str, image_id: str):
    """Secure endpoint for serving document images."""
    import re
    import os
    import json
    from fastapi.responses import FileResponse
    from app.config import settings

    # 1. Strict regex validation
    pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
    if not pattern.match(document_id) or not pattern.match(image_id):
        raise HTTPException(status_code=404, detail="Not found")

    # 2. Canonical path prefix verification
    images_root = os.path.abspath(os.path.join(str(settings.OUTPUT_DIR), "images"))
    target_dir = os.path.abspath(os.path.join(images_root, document_id))
    
    if not target_dir.startswith(images_root):
        raise HTTPException(status_code=404, detail="Not found")

    # 3. Lookup in metadata store
    metadata_path = os.path.join(target_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        raise HTTPException(status_code=404, detail="Not found")
        
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
        
    # Find image path from metadata
    img_record = next((item for item in metadata if item.get("image_id") == image_id), None)
    if not img_record or not img_record.get("image_path"):
        raise HTTPException(status_code=404, detail="Not found")
        
    final_path = os.path.abspath(img_record["image_path"])
    
    # 4. Final path prefix check to prevent traversal in metadata
    if not final_path.startswith(target_dir):
        raise HTTPException(status_code=404, detail="Not found")
        
    if not os.path.exists(final_path):
        raise HTTPException(status_code=404, detail="Not found")
        
    return FileResponse(final_path)


@app.post("/speak")
@limiter.limit("20/minute")
async def speak(payload: SpeakRequest, request: Request):
    """Generate text-to-speech stream using Sarvam AI (for Indian languages) or Edge-TTS."""
    try:
        from app.services.audio import speak_text
        audio_bytes, media_type = await speak_text(payload.text, payload.language)
        return Response(content=audio_bytes, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/troubleshoot")
@limiter.limit("20/minute")
async def troubleshoot(payload: TroubleshootRequest, request: Request):
    """
    Agentic Troubleshooting endpoint.
    Performs multi-turn state-guided diagnosis and recommendation.
    """
    if is_prompt_injection(payload.message):
        raise HTTPException(status_code=400, detail="Potential prompt injection detected.")
    if is_out_of_domain(payload.message):
        raise HTTPException(
            status_code=400,
            detail="I am specialized strictly in automotive and vehicle technical diagnostics. Please ask a query related to your vehicle service manual, OBD-II error codes, or mechanical troubleshooting."
        )

    # 1. Log user turn in PostgreSQL
    from app.database.postgres import record_session_turn
    try:
        await record_session_turn(
            session_id=payload.session_id,
            sender="user",
            message_text=payload.message,
            status="TROUBLESHOOTING"
        )
    except Exception as e:
        logger.warning(f"[PostgreSQL] Failed to record troubleshoot user turn: {e}")

    from app.services.workflow_manager import process_troubleshoot_turn
    try:
        result = await process_troubleshoot_turn(payload.session_id, payload.message)

        # 2. Log assistant diagnostic response in PostgreSQL
        try:
            msg_content = result.get("question") or result.get("next_action") or result.get("answer", "")
            await record_session_turn(
                session_id=payload.session_id,
                sender="assistant",
                message_text=msg_content,
                question=result.get("question"),
                action=result.get("next_action"),
                status=result.get("status", "TROUBLESHOOTING"),
                step_number=result.get("step", 0)
            )
        except Exception as e:
            logger.warning(f"[PostgreSQL] Failed to record troubleshoot assistant turn: {e}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/run", response_model=AgentResponse)
@limiter.limit("10/minute")
async def agent_run(payload: AgentRequest, request: Request):
    """
    Unified Agentic Ingestion + Retrieval endpoint.
    Scrapes web page or ingests file if provided, and performs grounded retrieval.
    """
    if is_prompt_injection(payload.query):
        raise HTTPException(status_code=400, detail="Potential prompt injection detected.")
    if is_out_of_domain(payload.query):
        raise HTTPException(
            status_code=400,
            detail="I am specialized strictly in automotive and vehicle technical diagnostics. Please ask a query related to your vehicle service manual, OBD-II error codes, or mechanical troubleshooting."
        )
        
    session_id = payload.session_id
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    # 1. Log user turn in PostgreSQL
    from app.database.postgres import record_session_turn
    try:
        await record_session_turn(
            session_id=session_id,
            sender="user",
            message_text=payload.query,
            status="AGENT_ACTIVE"
        )
    except Exception as e:
        logger.warning(f"[PostgreSQL] Failed to record agent user turn: {e}")
        
    inputs = {
        "query": payload.query,
        "raw_query": payload.query,
        "language": payload.language or "auto",
        "query_image": payload.image_base64,
        "source_input": payload.source_input,
        "source_content": None,
        "product_id": None,
        "clarification_needed": False,
        "retrieved_chunks": [],
        "sources": [],
        "mode": "qa",
        "answer": "",
        "steps": [],
        "content_changed": False,
        "version_info": None,
        "clarification_options": [],
        "session_id": session_id,
        "input_confidence": "LOW",
        "retrieval_confidence": "LOW",
        "clarification_question": None,
        "clarification_attempts": 0,
        "resolved_query": None,
        "retrieval_retries": 0,
        "understood_data": {}
    }
    
    from app.services.agent_flow import agent_graph
    from starlette.concurrency import run_in_threadpool
    try:
        # Run synchronous LangGraph execution in worker threadpool to avoid blocking event loop
        result = await run_in_threadpool(agent_graph.invoke, inputs)

        # 2. Log assistant turn in PostgreSQL
        try:
            ans = result.get("answer") or result.get("clarification_question") or ""
            await record_session_turn(
                session_id=session_id,
                sender="assistant",
                message_text=ans,
                question=result.get("clarification_question"),
                equipment_model=result.get("product_id"),
                status=result.get("status") or ("NEED_CLARIFICATION" if result.get("clarification_needed") else "COMPLETED")
            )
        except Exception as e:
            logger.warning(f"[PostgreSQL] Failed to record agent assistant turn: {e}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow execution failed: {str(e)}")


# ─── Admin Audit & Telemetry Endpoints ─────────────────────────────────────

@app.get("/admin/audit")
async def get_admin_audit():
    """Returns high-level audit summary and recent turn telemetry for the Admin dashboard."""
    from app.database.postgres import get_audit_summary
    return await get_audit_summary()


# ─── Chat History & Session Persistence Endpoints ─────────────────────────

class SessionPayload(BaseModel):
    session_id: str
    user_id: str = "default_user"
    title: Optional[str] = None
    messages: list[dict] = []
    product: Optional[str] = None
    status: Optional[str] = None


@app.get("/sessions")
def list_sessions(user_id: str = "default_user"):
    """Retrieve all chat sessions for a specific user."""
    from app.services.session_store import SessionStore
    store = SessionStore()
    return {"sessions": store.list_by_user(user_id)}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Retrieve full conversation details for a specific session."""
    from app.database.postgres import get_session_history
    pg_data = await get_session_history(session_id)
    if pg_data and pg_data.get("messages"):
        return pg_data

    from app.services.session_store import SessionStore
    store = SessionStore()
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return store.get(session_id)


@app.post("/sessions")
def save_session(payload: SessionPayload):
    """Persist or update chat session messages and state."""
    from app.services.session_store import SessionStore
    store = SessionStore()
    existing = store.get(payload.session_id)
    existing["user_id"] = payload.user_id
    if payload.title:
        existing["title"] = payload.title
    if payload.messages:
        existing["messages"] = payload.messages
    if payload.product:
        existing["product"] = payload.product
    if payload.status:
        existing["status"] = payload.status
    store.save(payload.session_id, existing)
    return {"status": "ok", "session_id": payload.session_id}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a chat session."""
    from app.services.session_store import SessionStore
    store = SessionStore()
    store.clear(session_id)
    return {"status": "deleted", "session_id": session_id}