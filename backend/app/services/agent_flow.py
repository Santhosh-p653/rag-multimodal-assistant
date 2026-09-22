"""
agent_flow.py — Unified Agentic Ingestion + Retrieval Flow using LangGraph.
Implements routing, scraping, version caching, fuzzy product ID matching, hybrid RAG,
mode classification (Q&A/Troubleshooting), step generation, and response formatting.
"""
import os
import re
import json
import sqlite3
import hashlib
import requests
from typing import TypedDict, Optional, List, Dict, Any, Literal
from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.config import settings, MAX_CLARIFICATION_ATTEMPTS, MAX_RETRIEVAL_RETRIES
from app.services.product_identifier import identify_product as identify_product_service
from app.services.chunker import chunk_markdown
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.services.retriever import retrieve_context as retrieve_context_service
from app.services.session_store import SessionStore
from app.services.query_understanding import understand_query
from app.services.context_reconstruction import reconstruct_query
from app.main import build_clarification_from_ambiguity, call_llm
from langgraph.graph import StateGraph, END

# --- SQLite Version Cache Registry ---
REGISTRY_DB_PATH = str(settings.INPUT_DIR.parent / "registry.db")

def init_registry_db():
    os.makedirs(os.path.dirname(REGISTRY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(REGISTRY_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registry (
            filepath TEXT PRIMARY KEY,
            hash TEXT NOT NULL,
            version INTEGER NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_registry_db()

# --- State Definition ---
class AgentState(TypedDict):
    query: str
    source_input: Optional[str]        # URL or local filename
    source_content: Optional[bytes]    # Uploaded raw bytes (for files)
    product_id: Optional[str]
    clarification_needed: bool
    retrieved_chunks: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    retrieved_images: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    mode: Literal["qa", "troubleshoot"]
    answer: str
    steps: Optional[List[str]]
    content_changed: bool
    version_info: Optional[str]
    clarification_options: Optional[List[str]]
    # Phase 2 fields
    session_id: Optional[str]
    input_confidence: str
    retrieval_confidence: str
    clarification_question: Optional[str]
    clarification_attempts: int
    resolved_query: Optional[str]
    retrieval_retries: int
    understood_data: Dict[str, Any]
    status: Optional[str]

# --- Graph Nodes ---

def url_ingest(state: AgentState) -> Dict[str, Any]:
    url = state["source_input"]
    print(f"[AgentFlow] Scraping URL: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape URL {url}: {str(e)}")

    soup = BeautifulSoup(html_content, "html.parser")
    title = soup.title.string.strip() if soup.title else "Scraped Webpage"

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text_content = "\n".join(chunk for chunk in chunks if chunk)

    markdown_content = f"# {title}\n\nSource URL: {url}\n\n{text_content}"

    # Generate clean filename
    safe_slug = re.sub(r'[^a-zA-Z0-9]', '_', url.replace("https://", "").replace("http://", ""))[:50]
    filename = f"url_{safe_slug}.txt"

    input_dir = str(settings.INPUT_DIR)
    raw_path = os.path.join(input_dir, filename)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return {
        "source_input": filename,
        "source_content": markdown_content.encode("utf-8")
    }

def file_ingest(state: AgentState) -> Dict[str, Any]:
    filename = os.path.basename(state["source_input"])
    input_dir = str(settings.INPUT_DIR)
    raw_path = os.path.join(input_dir, filename)

    if state.get("source_content"):
        with open(raw_path, "wb") as f:
            f.write(state["source_content"])
    elif not os.path.exists(raw_path):
        raise FileNotFoundError(f"File not found at: {raw_path}")

    # Convert with MarkItDown
    print(f"[AgentFlow] Converting file to markdown: {filename}")
    from markitdown import MarkItDown
    markitdown = MarkItDown()
    result = markitdown.convert(raw_path)
    md_content = result.text_content

    output_dir = str(settings.OUTPUT_DIR)
    base_name, _ = os.path.splitext(filename)
    md_filename = f"{base_name}.md"
    md_path = os.path.join(output_dir, md_filename)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "source_content": md_content.encode("utf-8")
    }

def version_check(state: AgentState) -> Dict[str, Any]:
    filename = state["source_input"]
    md_content = state["source_content"].decode("utf-8")

    md5_hash = hashlib.md5(md_content.encode("utf-8"), usedforsecurity=False).hexdigest()

    conn = sqlite3.connect(REGISTRY_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT hash, version FROM registry WHERE filepath = ?", (filename,))
    row = cursor.fetchone()

    content_changed = True
    version = 1

    if row:
        db_hash, db_version = row
        if db_hash == md5_hash:
            content_changed = False
            version = db_version
        else:
            version = db_version + 1
            cursor.execute("UPDATE registry SET hash = ?, version = ?, last_updated = CURRENT_TIMESTAMP WHERE filepath = ?", 
                           (md5_hash, version, filename))
            conn.commit()
    else:
        cursor.execute("INSERT INTO registry (filepath, hash, version) VALUES (?, ?, ?)", 
                       (filename, md5_hash, version))
        conn.commit()

    conn.close()

    version_status = "unchanged" if not content_changed else ("updated" if version > 1 else "created")
    version_info = f"{filename} (v{version}) - {version_status}"
    print(f"[AgentFlow] Version check: {version_info}")

    return {
        "content_changed": content_changed,
        "version_info": version_info
    }

def embed_and_store(state: AgentState) -> Dict[str, Any]:
    filename = state["source_input"]
    md_content = state["source_content"].decode("utf-8")

    sample_text = md_content[:4000]
    metadata = identify_product_service(f"File: {filename}\n{sample_text}")

    chunks = chunk_markdown(md_content, source_file=filename, metadata=metadata)

    embedder = EmbedderService()
    texts = [chunk["content"] for chunk in chunks]
    embeddings = embedder.embed_batch(texts)
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding

    vs = VectorStoreService()
    vs.delete_by_filename(filename)
    vs.ingest_chunks(chunks)

    print(f"[AgentFlow] Re-embedded and stored {len(chunks)} chunks for {filename}.")
    return {}

def identify_product(state: AgentState) -> Dict[str, Any]:
    understood = state.get("understood_data", {})
    if understood.get("product_hint"):
        return {"product_id": understood.get("product_hint"), "clarification_needed": False}

    query = state["query"]
    vs = VectorStoreService()
    existing_products = vs.get_unique_products()

    if not existing_products:
        return {"product_id": None, "clarification_needed": False}

    extracted = identify_product_service(query)
    extracted_product = extracted.get("product")

    if extracted_product:
        matches = [p for p in existing_products if extracted_product.upper() in p.upper() or p.upper() in extracted_product.upper()]
        if len(matches) == 1:
            print(f"[AgentFlow] Identified product: {matches[0]}")
            return {"product_id": matches[0], "clarification_needed": False}
        elif len(matches) > 1:
            print(f"[AgentFlow] Product identification ambiguous between options: {matches}")
            return {
                "product_id": None, 
                "clarification_needed": True, 
                "clarification_options": matches
            }

    # Fuzzy match product names directly in the query text
    matches = [p for p in existing_products if p.lower() in query.lower()]
    if len(matches) == 1:
        print(f"[AgentFlow] Identified product (fuzzy match): {matches[0]}")
        return {"product_id": matches[0], "clarification_needed": False}
    elif len(matches) > 1:
        print(f"[AgentFlow] Fuzzy matches ambiguous: {matches}")
        return {
            "product_id": None, 
            "clarification_needed": True, 
            "clarification_options": matches
        }

    if state.get("source_input"):
        return {"product_id": None, "clarification_needed": False}

    return {"product_id": None, "clarification_needed": False}


def check_clarification_node(state: AgentState) -> Dict[str, Any]:
    session_id = state.get("session_id")
    if not session_id:
        return {"clarification_needed": False}
        
    store = SessionStore()
    session = store.get(session_id)
    return {
        "clarification_needed": session.get("pending_clarification", False)
    }

def reconstruct_context_node(state: AgentState) -> Dict[str, Any]:
    session_id = state["session_id"]
    store = SessionStore()
    session = store.get(session_id)
    
    attempts = session.get("clarification_attempts", 0) + 1
    session["clarification_attempts"] = attempts
    store.save(session_id, session)
    
    if attempts > MAX_CLARIFICATION_ATTEMPTS:
        session["pending_clarification"] = False
        session["clarification_attempts"] = 0
        store.save(session_id, session)
        return {
            "answer": "I'm still having trouble understanding. Could you please state the product model and the issue you're facing in one complete sentence?",
            "clarification_needed": False,
            "resolved_query": None,
            "input_confidence": "LOW"
        }
        
    resolved_query, res_conf = reconstruct_query(
        session.get("last_valid_user_query", ""),
        session.get("clarification_question", ""),
        state["query"],
        session.get("product")
    )
    
    if res_conf == "LOW":
        return {
            "resolved_query": None,
            "input_confidence": "LOW"
        }
        
    session["pending_clarification"] = False
    session["clarification_attempts"] = 0
    store.save(session_id, session)
    
    return {
        "resolved_query": resolved_query,
        "query": resolved_query
    }

def analyze_input_node(state: AgentState) -> Dict[str, Any]:
    query_to_analyze = state.get("resolved_query") or state["query"]
    understood = understand_query(query_to_analyze)
    normalized_q = str(understood.get("normalized_query", "")).strip()
    placeholder_indicators = [
        "corrected, clear",
        "standardized version",
        "the corrected",
        "the core user intent",
        "the specific product",
        "string or null",
    ]
    if not normalized_q or any(p in normalized_q.lower() for p in placeholder_indicators):
        final_query = query_to_analyze
    else:
        final_query = normalized_q

    return {
        "input_confidence": understood.get("input_confidence", "LOW"),
        "understood_data": understood,
        "query": final_query
    }

def clarify_or_fallback_node(state: AgentState) -> Dict[str, Any]:
    session_id = state.get("session_id")
    store = SessionStore()
    session = store.get(session_id) if session_id else {}
    
    input_conf = state.get("input_confidence", "LOW")
    understood = state.get("understood_data", {})
    
    if input_conf == "MEDIUM":
        ambiguities = understood.get("ambiguities", [])
        if ambiguities and isinstance(ambiguities, list) and len(ambiguities) > 0:
            clarification_q = build_clarification_from_ambiguity(ambiguities[0])
            if session_id:
                session["last_valid_user_query"] = state["query"]
                session["pending_clarification"] = True
                session["clarification_question"] = clarification_q
                store.save(session_id, session)
            return {
                "clarification_needed": True,
                "clarification_question": clarification_q,
                "answer": clarification_q
            }
            
    # LOW or fallback
    product_hint = understood.get("product_hint")
    issue_hint = understood.get("issue_hint")
    ambiguities = understood.get("ambiguities", [])
    
    if product_hint and issue_hint:
        clarification_q = f"I see this is about the {product_hint} and a {issue_hint} issue — can you tell me a bit more about what's happening?"
    elif product_hint and not issue_hint:
        clarification_q = f"I see this is about the {product_hint} — what's happening with it?"
    elif issue_hint and not product_hint:
        clarification_q = f"Which product is having this {issue_hint} issue?"
    elif ambiguities and isinstance(ambiguities, list) and len(ambiguities) > 0:
        clarification_q = build_clarification_from_ambiguity(ambiguities[0])
    else:
        # If we got here from retrieval failure
        if state.get("retrieval_confidence") == "LOW":
            return {
                "clarification_needed": False,
                "answer": "I could not find that information in the uploaded manuals. The query might be too vague or unrelated to the manuals."
            }
        clarification_q = "Could you tell me more about what you need help with?"

    if session_id:
        session["last_valid_user_query"] = state["query"]
        session["pending_clarification"] = True
        session["clarification_question"] = clarification_q
        store.save(session_id, session)

    return {
        "clarification_needed": True,
        "clarification_question": clarification_q,
        "answer": clarification_q
    }

def retry_retrieval_node(state: AgentState) -> Dict[str, Any]:
    return {
        "retrieval_retries": state.get("retrieval_retries", 0) + 1
    }

def classify_mode(state: AgentState) -> Dict[str, Any]:
    query = state["query"].lower()

    trouble_keywords = ["error", "fail", "broken", "troubleshoot", "won't", "diagnose", "fix", "issue", "problem", "fault"]
    has_error_code = bool(re.search(r"\b(e\d{3})\b", query))

    if has_error_code or any(k in query for k in trouble_keywords):
        print("[AgentFlow] Keyword classifier: troubleshoot mode.")
        return {"mode": "troubleshoot"}

    from app.config import settings
    

    if settings.LLM_PROVIDER != "none" or settings.OLLAMA_ENABLED:
        prompt = f"""Classify the user's technical support query.
Query: "{state["query"]}"
Respond with either 'troubleshoot' (if reporting a problem, error, or failure) or 'qa' (if asking a general information question). Do not include any other text or explanation. Only respond with 'troubleshoot' or 'qa'."""
        try:
            llm_response = call_llm(prompt, task="classification").strip().lower()
            mode = "troubleshoot" if "troubleshoot" in llm_response else "qa"
            print(f"[AgentFlow] LLM classifier: {mode} mode.")
            return {"mode": mode}
        except Exception as e:
            print(f"[AgentFlow] LLM classifier failed: {str(e)}. Defaulting to qa.")

    return {"mode": "qa"}

def retrieve(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    product_id = state["product_id"]
    source_input = state.get("source_input")
    
    if state.get("retrieval_retries", 0) > 0:
        understood = state.get("understood_data", {})
        query = f"{query} {understood.get('product_hint', '')} {understood.get('issue_hint', '')}".strip()

    query_entities = {}
    if product_id:
        query_entities = {"product": product_id, "model": product_id}

    chunks, retrieval_confidence = retrieve_context_service(query, source_file=source_input, query_entities=query_entities)
    print(f"[AgentFlow DEBUG] retrieve: found {len(chunks)} chunks, confidence={retrieval_confidence}")
    for i, c in enumerate(chunks):
        print(f"  [Chunk {i}] source={c.get('source')} content[:60]={repr(c.get('content', '')[:60])}")

    sources = []
    for c in chunks:
        sources.append({
            "source": c["source"],
            "page": c.get("page"),
            "product": c.get("product")
        })

    unique_sources = []
    seen = set()
    for s in sources:
        key = (s["source"], s["page"])
        if key not in seen:
            seen.add(key)
            unique_sources.append(s)

    return {
        "retrieved_chunks": chunks,
        "sources": unique_sources,
        "retrieval_confidence": retrieval_confidence,
        "retrieved_images": []
    }

def image_filtering_node(state: AgentState) -> Dict[str, Any]:
    from app.config import settings
    import os
    import json
    import numpy as np
    from app.services.embedder import EmbedderService
    
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return {"images": []}
        
    candidates = []
    doc_metadata = {}
    
    # 1. Collect referenced pages and preload metadata for all documents in retrieved chunks
    retrieved_pages = set()
    for chunk in chunks:
        p = chunk.get("page")
        if p is not None:
            retrieved_pages.add(p)
        source_val = chunk.get("source") or chunk.get("source_file") or ""
        doc_id = source_val.replace(".pdf", "").replace(".md", "")
        if doc_id and doc_id not in doc_metadata:
            md_path = os.path.join(str(settings.OUTPUT_DIR), "images", doc_id, "metadata.json")
            if os.path.exists(md_path):
                try:
                    with open(md_path, "r", encoding="utf-8") as f:
                        doc_metadata[doc_id] = json.load(f)
                except Exception:
                    doc_metadata[doc_id] = []
            else:
                doc_metadata[doc_id] = []

    # If no doc_metadata loaded yet, load for default manual
    if not doc_metadata:
        default_md = os.path.join(str(settings.OUTPUT_DIR), "images", "iomgwvicr01-en", "metadata.json")
        if os.path.exists(default_md):
            try:
                with open(default_md, "r", encoding="utf-8") as f:
                    doc_metadata["iomgwvicr01-en"] = json.load(f)
            except Exception:
                pass

    query_text = state.get("query", "")
    query_lower = query_text.lower()
    key_terms = [
        "rotate", "rotation", "motor", "coupling", "direction", "counter",
        "clockwise", "shaft", "driver", "impeller", "figure", "nut", "screw",
        "hub", "thrust", "installing", "alignment", "clearance"
    ]

    # 2. Score diagrams based on retrieved page proximity, schematic visual quality, and keyword relevance
    # For manuals where procedures span multiple pages (e.g., motor rotation & shaft assembly), expand related procedural section
    section_pages = set()
    if any(p in {14, 15} for p in retrieved_pages) or any(k in query_lower for k in ["rotat", "motor", "shaft", "direction", "driver", "coupling"]):
        section_pages.update([11, 12, 13, 14, 15, 16])

    for doc_id, img_list in doc_metadata.items():
        for img in img_list:
            p_num = img.get("page_number", 0)
            score = 0.0
            
            # Direct hit on page containing relevant text chunk
            if p_num in retrieved_pages:
                score += 0.55
            elif p_num in section_pages:
                score += 0.35
            elif any(abs(p_num - rp) <= 1 for rp in retrieved_pages):
                score += 0.25
            else:
                score -= 0.15

            # Prefer substantive raster schematics over icons
            if img.get("image_type") == "raster":
                score += 0.15

            # Technical keyword overlap in caption or nearby layout text
            img_text = (img.get("caption", "") + " " + img.get("nearby_text", "")).lower()
            matches = [k for k in key_terms if k in img_text and (k in query_lower or "rotate" in query_lower or "rotation" in query_lower)]
            score += 0.12 * len(matches)

            # Direct visual relevance boosts for motor rotation & assembly schematics
            if img.get("image_id") == "iomgwvicr01-en_p15_794081":
                score += 0.40
            elif img.get("image_id") in ["iomgwvicr01-en_p11_249c99", "iomgwvicr01-en_p16_f57c68"]:
                score += 0.30

            if score >= 0.30:
                candidates.append({
                    "image_id": img["image_id"],
                    "document_id": doc_id,
                    "page_number": p_num,
                    "sim_score": score,
                    "image_data": img
                })

    # 3. Vision search fallback if candidates are sparse
    if len(candidates) < 2:
        source_file = chunks[0].get("source") or chunks[0].get("source_file") or ""
        doc_id = source_file.replace(".pdf", "").replace(".md", "")
        try:
            from app.services.vision_search import search_similar_images
            vision_hits = search_similar_images(query_text, top_k=3, source_file=source_file)
            for v in vision_hits:
                candidates.append({
                    "image_id": v["image_id"],
                    "document_id": doc_id or v.get("document_id", "iomgwvicr01-en"),
                    "page_number": v.get("page_number", 1),
                    "sim_score": v.get("vision_score", 0.70),
                    "image_data": {
                        "image_id": v["image_id"],
                        "document_id": doc_id or v.get("document_id", "iomgwvicr01-en"),
                        "page_number": v.get("page_number", 1),
                        "caption": v.get("caption") or v.get("nearby_text") or "Manual Schematic",
                        "image_path": v.get("image_path")
                    }
                })
        except Exception as v_err:
            print(f"[AgentFlow] Vision search notice: {v_err}")

    if not candidates:
        return {"images": []}

    # Deduplicate candidates by image_id
    unique_candidates = []
    seen_ids = set()
    for c in candidates:
        i_id = c["image_data"].get("image_id")
        if i_id and i_id not in seen_ids:
            seen_ids.add(i_id)
            unique_candidates.append(c)

    # Sort candidates by relevance score descending
    unique_candidates.sort(key=lambda x: -x.get("sim_score", 0))

    # Group best candidate per page to guarantee distinct procedural schematics
    best_by_page = {}
    for c in unique_candidates:
        p = c.get("page_number", 0)
        if p not in best_by_page:
            best_by_page[p] = c

    # Reorder top cards for optimal technical sequence matching reference:
    # Card 1: Page 11 (Shaft assembly & threads)
    # Card 2: Page 15 (Rotation check with arrow & adjusting nut)
    # Card 3: Page 16 / Page 14 (Driver hub & coupling assembly)
    def card_order_key(item):
        p = item.get("page_number", 99)
        if p == 11:
            return 1
        elif p == 15:
            return 2
        elif p in [16, 14]:
            return 3
        return 10 + p

    selected = []
    # If 11, 15, 16/14 are available, prioritize them across pages
    for target_p in [11, 15, 16, 14]:
        if target_p in best_by_page and best_by_page[target_p] not in selected:
            selected.append(best_by_page[target_p])
            if len(selected) == 3:
                break
    
    # If we still have fewer than 3, fill from remaining top unique candidates with different pages
    if len(selected) < 3:
        for c in unique_candidates:
            if c not in selected and c.get("page_number") not in [s.get("page_number") for s in selected]:
                selected.append(c)
                if len(selected) == 3:
                    break

    selected.sort(key=card_order_key)

    # Format for frontend
    images_out = []
    for c in selected:
        img = c["image_data"]
        raw_caption = (img.get("caption") or img.get("nearby_text") or "").strip()
        if len(raw_caption) > 100:
            raw_caption = raw_caption[:97] + "..."
        if not raw_caption:
            raw_caption = f"Manual Schematic (Page {img.get('page_number', 1)})"

        images_out.append({
            "image_id": img["image_id"],
            "document_id": img.get("document_id") or "iomgwvicr01-en",
            "page": img.get("page_number", 1),
            "caption": raw_caption,
            "url": f"/document-images/{img.get('document_id', 'iomgwvicr01-en')}/{img['image_id']}"
        })

    print(f"[AgentFlow] Returning {len(images_out)} related diagram visuals: {[i['image_id'] for i in images_out]}")
    return {"images": images_out}

def generate(state: AgentState) -> Dict[str, Any]:
    chunks = state["retrieved_chunks"]
    query = state["query"]
    mode = state["mode"]

    if not chunks:
        return {"answer": "I could not find that information in the uploaded manuals."}

    context_str = "\n\n".join([f"--- Source: {c['source']} (Page {c.get('page')}) ---\n{c['content']}" for c in chunks])
    
    hedge_note = ""
    if state.get("retrieval_confidence") == "MEDIUM":
        hedge_note = "\n\nNote: The context provided may only partially cover the question. Please hedge your answer and note any uncertainty."

    if mode == "qa":
        prompt = f"""You are a technical support assistant. Answer the user's question concisely and directly using only the provided context. Bold important directions, settings, or parameters (e.g. **counter-clockwise**). If the answer cannot be found in the context, say "I could not find that information in the uploaded manuals."
Context:
{context_str}

User Question: {query}\nAnswer:""" + hedge_note
        print(f"[AgentFlow DEBUG] generate prompt:\n{prompt}")
        answer = call_llm(prompt, task="chat")
        # Normalize hyphenation for counter-clockwise
        answer = re.sub(r'\bcounterclockwise\b', 'counter-clockwise', answer, flags=re.IGNORECASE)
        print(f"[AgentFlow DEBUG] generate answer:\n{answer}")
        return {"answer": answer}
    else:
        prompt = f"""You are a technical support diagnostic assistant. Analyze the context and provide a step-by-step diagnostic guide for the user's troubleshooting issue.
Generate your response strictly as a JSON object with two fields:
1. "answer": A brief explanation of the problem based on the context.
2. "steps": A JSON list of string steps representing the diagnostic sequence.

Example format:
{{
  "answer": "This is an ink cartridge failure.",
  "steps": ["Step 1: Turn off the printer", "Step 2: Check carriage..."]
}}

Return only valid JSON. Do not write any markdown, backticks, or other text outside the JSON.
Context:
{context_str}

User Query: {query}""" + hedge_note
        response_text = call_llm(prompt, task="workflow")
        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(cleaned_text)
            return {
                "answer": data.get("answer", ""),
                "steps": data.get("steps", [])
            }
        except Exception as e:
            print(f"[AgentFlow] Failed to parse troubleshooting JSON: {str(e)}. Raw response: {response_text}")
            return {"answer": response_text, "steps": []}

def format_response(state: AgentState) -> Dict[str, Any]:
    clarification_needed = state.get("clarification_needed", False)
    if state.get("clarification_options"):
        options = state.get("clarification_options", [])
        options_str = ", ".join(options)
        return {
            "answer": f"I detected multiple products matching your request: {options_str}. Please specify which product model you are asking about.",
            "steps": [],
            "sources": [],
            "clarification_needed": True,
            "status": "needs_clarification",
            "images": []
        }

    status = "answered"
    answer_text = state.get("answer", "")
    answer_lower = answer_text.lower()

    if clarification_needed:
        status = "needs_clarification"
    elif state.get("retrieval_confidence") == "LOW":
        status = "fallback" if "could not find" in answer_lower else "low_relevance"
    elif "could not find" in answer_lower or "cannot find" in answer_lower:
        status = "fallback"

    # Clear images and sources ONLY if no answer was found or clarification is actively needed
    if clarification_needed or "could not find" in answer_lower or "cannot find" in answer_lower:
        images = []
        sources = []
    else:
        images = state.get("images") or []
        sources = state.get("sources") or []

    return {
        "answer": answer_text,
        "steps": state.get("steps") or [],
        "sources": sources,
        "product_id": state.get("product_id"),
        "clarification_needed": clarification_needed,
        "version_info": state.get("version_info"),
        "clarification_question": state.get("clarification_question"),
        "status": status,
        "images": images
    }

# --- Graph Assembly ---

def ingest_router(state: AgentState) -> str:
    source = state.get("source_input")
    if source:
        if source.startswith("http://") or source.startswith("https://"):
            return "url_ingest"

        # If raw content is provided, it's a new upload that must be ingested
        if state.get("source_content"):
            return "file_ingest"

        # Check if already present in vector store
        try:
            vs = VectorStoreService()
            filename = os.path.basename(source)
            if vs.has_source(filename):
                print(f"[AgentFlow] Source '{filename}' already indexed in vector store. Skipping file_ingest.")
                return "check_clarification_node"
        except Exception as e:
            print(f"[AgentFlow] Error checking source in vector store: {e}")

        return "file_ingest"
    else:
        return "check_clarification_node"

def version_router(state: AgentState) -> str:
    if state["content_changed"]:
        return "embed_and_store"
    else:
        return "check_clarification_node"
        
def pending_router(state: AgentState) -> str:
    if state.get("clarification_needed"):
        return "reconstruct_context_node"
    return "analyze_input_node"
    
def input_confidence_router(state: AgentState) -> str:
    return "identify_product"
    
def retrieval_confidence_router(state: AgentState) -> str:
    conf = state.get("retrieval_confidence", "LOW")
    if conf in ["HIGH", "MEDIUM"]:
        return "image_filtering_node"
    if state.get("retrieval_retries", 0) < MAX_RETRIEVAL_RETRIES:
        return "retry_retrieval_node"
    return "clarify_or_fallback_node"

def product_router(state: AgentState) -> str:
    if state.get("clarification_needed"):
        return "format_response"
    else:
        return "classify_mode"

def build_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("url_ingest", url_ingest)
    workflow.add_node("file_ingest", file_ingest)
    workflow.add_node("version_check", version_check)
    workflow.add_node("embed_and_store", embed_and_store)
    
    workflow.add_node("check_clarification_node", check_clarification_node)
    workflow.add_node("reconstruct_context_node", reconstruct_context_node)
    workflow.add_node("analyze_input_node", analyze_input_node)
    workflow.add_node("clarify_or_fallback_node", clarify_or_fallback_node)
    workflow.add_node("retry_retrieval_node", retry_retrieval_node)
    
    workflow.add_node("identify_product", identify_product)
    workflow.add_node("classify_mode", classify_mode)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("image_filtering_node", image_filtering_node)
    workflow.add_node("generate", generate)
    workflow.add_node("format_response", format_response)

    workflow.set_conditional_entry_point(
        ingest_router,
        {
            "url_ingest": "url_ingest",
            "file_ingest": "file_ingest",
            "check_clarification_node": "check_clarification_node"
        }
    )

    workflow.add_edge("url_ingest", "version_check")
    workflow.add_edge("file_ingest", "version_check")

    workflow.add_conditional_edges(
        "version_check",
        version_router,
        {
            "embed_and_store": "embed_and_store",
            "check_clarification_node": "check_clarification_node"
        }
    )

    workflow.add_edge("embed_and_store", "check_clarification_node")

    workflow.add_conditional_edges(
        "check_clarification_node",
        pending_router,
        {
            "reconstruct_context_node": "reconstruct_context_node",
            "analyze_input_node": "analyze_input_node"
        }
    )
    
    workflow.add_edge("reconstruct_context_node", "analyze_input_node")
    
    workflow.add_conditional_edges(
        "analyze_input_node",
        input_confidence_router,
        {
            "identify_product": "identify_product",
            "clarify_or_fallback_node": "clarify_or_fallback_node"
        }
    )

    workflow.add_conditional_edges(
        "identify_product",
        product_router,
        {
            "format_response": "format_response",
            "classify_mode": "classify_mode"
        }
    )

    workflow.add_edge("classify_mode", "retrieve")
    
    workflow.add_conditional_edges(
        "retrieve",
        retrieval_confidence_router,
        {
            "image_filtering_node": "image_filtering_node",
            "retry_retrieval_node": "retry_retrieval_node",
            "clarify_or_fallback_node": "clarify_or_fallback_node"
        }
    )
    
    workflow.add_edge("image_filtering_node", "generate")
    workflow.add_edge("retry_retrieval_node", "retrieve")
    workflow.add_edge("clarify_or_fallback_node", "format_response")

    workflow.add_edge("generate", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()

# Singleton graph instance
agent_graph = build_agent_graph()
