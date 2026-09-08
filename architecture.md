# Comprehensive Architecture Specification — OCTO RAG Assistant

This document provides an exhaustive technical specification of the systems, pipelines, submodule responsibilities, orchestration state machines, security layers, Model Context Protocol (MCP) servers, state transitions, success/failure fallback states, and key architectural decisions in the **OCTO RAG Assistant**.

---

## 1. Submodule Problem-Solving Matrix & Key Architectural Decisions

Every submodule in the backend is designed to solve specific technical problems with explicit architectural rationales:

| Submodule | Target Engineering Problem | Technical Solution & Implementation | Key Architectural Decision & Rationale |
| :--- | :--- | :--- | :--- |
| **`fridge_mcp_server.py`** | External AI clients (Claude Desktop, IDEs) lacking diagnostic & LangGraph execution tools | Implements a **FastMCP** server exposing 6 tools: `search_fridge_manuals`, `lookup_error_code`, `get_thermistor_ohm_table`, `lookup_part_number`, `run_octo_agent`, and `troubleshoot_appliance_turn`. | **Standard Open MCP Protocol**: Exposes tools over stdio and FastAPI SSE (`/mcp/sse`), establishing instant interoperability with Claude Desktop and external IDEs. |
| **`mcp_client.py`** | Internal services requiring diagnostic lookup without network overhead | Programmatic client helper for invoking local MCP tools directly within Python nodes. | **Decoupled Tool Execution**: Prevents HTTP network overhead during internal Python service calls. |
| **`prompt_guard.py`** | Jailbreaks, prompt injection & off-topic LLM token waste | Regex filter intercepting injection patterns (`is_prompt_injection`) AND non-refrigerator domain topics (`is_out_of_domain`). | **Gateway Pre-LLM Boundary**: Rejects non-refrigerator prompts *before* vector search or LLM invocation, expending **0 LLM API tokens** on off-topic requests. |
| **`parser.py`** | Multi-format layout destruction in PDFs/DOCX | Uses **Microsoft MarkItDown** to render multi-format uploads into clean, unified Markdown text before chunking. | **Unified Text Schema**: Standardizes multi-format inputs into Markdown prior to chunking. |
| **`image_extractor.py`** | Loss of vector schematics & diagrams in PDFs | Combines PyMuPDF raster extraction with custom vector drawing region clustering (`get_vector_drawing_regions`), rendering CAD/wiring diagrams to PNGs. | **Vector Drawing Rendering**: Renders CAD path drawings missed by standard PDF image extractors. |
| **`image_filters.py`** | Qdrant vector bloat from decorative logos/lines | Applies aspect ratio bounds ($0.2 \le \text{AR} \le 5.0$), page area checks, and perceptual hash (`pHash`) deduplication ($\le 2$ repeat threshold). | **Perceptual Hash Filtering**: Drops header logos, footer icons, and line dividers before vector indexing. |
| **`chunker.py`** | Context loss across chunk boundaries | Uses a character-sliding window (`CHUNK_SIZE=500`, `OVERLAP=100`) while propagating metadata header tags to each chunk. | **Header Propagation**: Retains document headings and section context across overlapping chunks. |
| **`embedder.py`** | High CPU overhead for text vector encoding | Implements a thread-safe Singleton pattern for `SentenceTransformers` (`all-MiniLM-L6-v2`) with `@lru_cache(maxsize=1024)`. | **LRU Vector Caching**: Eliminates redundant model instantiation and duplicate text embedding calculations. |
| **`vision_embedder.py`** | Text-only search failing on visual manual content | Implements a SigLIP 2 Singleton (`google/siglip-base-patch16-224`) generating 768-dim joint text-image embeddings. | **Multimodal Shared Vector Space**: Enables cross-modal text-to-image semantic vector search. |
| **`vision_search.py`** | Irrelevant visual diagram retrieval | Queries the dedicated `manual_images` Qdrant collection, enforcing application-level `VISION_SCORE_THRESHOLD` filtering. | **Dual Vector Collection Isolation**: Keeps visual image vectors separate from text chunk vectors. |
| **`vector_store.py`** | Payload schema pollution & vector duplication | Maintains dual Qdrant collections (`manuals` & `manual_images`), performing deletion by source file before re-indexing. | **Source File Idempotency**: Ensures atomic re-indexing without duplicate stale vectors. |
| **`hybrid_search.py`** | Keyword mismatch in pure dense vector search | Implements in-memory **BM25** sparse ranking combined with dense candidate vectors using **Reciprocal Rank Fusion (RRF)** ($k=60$). | **Dense + Sparse Fusion**: Balances exact error code matching with broad semantic retrieval. |
| **`retriever.py`** | Empty search hits from strict metadata filters | Implements a 3-level waterfall search (Exact Product $\rightarrow$ Family Prefix $\rightarrow$ Global Search) run concurrently with SigLIP vision search. | **3-Level Waterfall Strategy**: Eliminates search drop-offs while prioritizing exact product documentation. |
| **`agent_flow.py`** | Uncontrolled agent loops & redundant re-indexing | Uses a bounded **LangGraph `StateGraph`** with SQLite MD5 hash version checking (`registry.db`). | **Bounded Deterministic Graph**: Replaces infinite LLM loops with explicit graph state routers. |
| **`workflow_manager.py`**| LLM state drift in multi-turn diagnostic chats | Implements a state-guided session registry (`START` $\rightarrow$ `QUESTION` $\rightarrow$ `ACTION` $\rightarrow$ `VERIFY` $\rightarrow$ `RESOLVED`/`ESCALATE`). | **SOP State Enforcement**: Enforces structured diagnostic discipline, preventing premature repair steps. |
| **`audio.py`** | High latency & Indic language accent failures | Hybrid routing: local `faster-whisper` (`int8` CPU) for English, Sarvam AI (`Saaras v3`) for Indic audio, and `edge-tts` for neural speech synthesis. | **Hybrid STT/TTS Routing**: Delivers fast English STT while preserving accuracy for Indic regional dialects. |
| **`main.py`** | System DDoS and resource exhaustion | Wraps all routes in `slowapi` rate limiters, mounts `/mcp` SSE endpoint, and pre-warms models during startup. | **API Rate Limiting & Startup Pre-warming**: Protects endpoints and eliminates cold-start latency. |

---

## 2. Multimodal Ingestion Pipeline (Workflows & Fallback States)

```mermaid
graph TD
    A[Raw Upload File] --> Guard{Validation Guard: Size <= 25MB & Allowed MIME/Ext}
    
    Guard -->|Invalid Size >25MB| RejSize[FAILURE STATE: HTTP 413 File Too Large]
    Guard -->|Invalid Format| RejMime[FAILURE STATE: HTTP 400 Unsupported Format]
    Guard -->|Passed| VersionCheck{version_check: MD5 Hash in registry.db}
    
    VersionCheck -->|Unchanged Hash| SkipIdx[SUCCESS STATE: Skip Indexing / Content Unchanged]
    VersionCheck -->|New/Updated Hash| MarkItDown[MarkItDown Text Parsing]
    
    MarkItDown --> PyMuPDF[PyMuPDF Image & Vector Path Extraction]
    PyMuPDF --> ImageFilter{image_filters.py: Aspect Ratio & pHash Filter}
    
    ImageFilter -->|Valid Image Crop| SigLIP[vision_embedder.py: SigLIP 2 Encoder]
    ImageFilter -->|Decorative / Logo| DropImg[Filtered Out]
    
    SigLIP --> QdrantImg[(Qdrant: manual_images Collection)]
    
    MarkItDown --> Chunker[chunker.py: Sliding Window 500/100]
    Chunker --> Embedder[embedder.py: SentenceTransformers Encoder]
    Embedder --> QdrantText[(Qdrant: manuals Collection)]
    
    QdrantText --> SuccessIngest[SUCCESS STATE: HTTP 200 Indexing Complete]
```

### Ingestion States & Fallbacks
1. **Validation Rejection States**: `HTTP 413` for files $>25\text{MB}$; `HTTP 400` for unsupported MIME types.
2. **Version Cache Skip State**: If raw file MD5 matches `registry.db`, chunking and vector embedding are skipped completely.
3. **Image Extraction Fallback State**: If PyMuPDF encounters corrupt vector graphics or zero images, document processing falls back gracefully to text-only vector indexing without throwing errors.

---

## 3. Context-Aware Hierarchical Retrieval & Confidence Routing

```mermaid
graph TD
    Query[User Query] --> Guard{prompt_guard.py: Injection & Domain Check}
    
    Guard -->|Injection Pattern| BlockInj[FAILURE STATE: HTTP 400 Prompt Injection]
    Guard -->|Off-Topic Topic| BlockDomain[FAILURE STATE: HTTP 400 Out of Domain / 0 Tokens]
    Guard -->|Passed| Waterfall{3-Level Waterfall Strategy}
    
    Waterfall -->|Level 1: Match| Exact[Qdrant Search: Exact Product]
    Waterfall -->|Level 1: Empty| Family[Qdrant Search: Product Family Prefix]
    Waterfall -->|Level 2: Empty| Global[Qdrant Search: Global Manuals]
    
    Exact --> Candidates[Top 50 Dense Candidates]
    Family --> Candidates
    Global --> Candidates
    
    Candidates --> BM25[In-Memory BM25 Sparse Scoring]
    BM25 --> RRF[RRF Fusion: k=60]
    
    RRF --> ConfEval{Retrieval Confidence Evaluator}
    
    ConfEval -->|HIGH Confidence| HighState[SUCCESS STATE: High Relevance LLM Answer]
    ConfEval -->|MEDIUM Confidence| MedState[SUCCESS STATE: Hedged Answer + Uncertainty Note]
    ConfEval -->|LOW / Zero Chunks| LowState[FALLBACK STATE: Standard Manual Fallback Answer]
```

### Retrieval States & Fallbacks
1. **HIGH Confidence State**: Top RRF chunks match query entities directly. Returns grounded answer with exact page citations.
2. **MEDIUM Confidence State**: Chunks cover query partially or product hint differs slightly. Returns answer instructed to hedge with uncertainty warnings.
3. **LOW Confidence Fallback State**: Zero hits or top score below threshold. Returns exact standardized fallback string: `"I could not find that information in the uploaded manuals. The query might be too vague or unrelated to the manuals."`

---

## 4. LangGraph Unified Agentic Execution Pipeline (`agent_flow.py`)

```mermaid
graph TD
    Start([POST /agent/run or run_octo_agent MCP Tool]) --> IngestRouter{ingest_router}
    
    IngestRouter -->|URL| URLIngest[url_ingest: BeautifulSoup4 Scraper]
    IngestRouter -->|File| FileIngest[file_ingest: MarkItDown Converter]
    IngestRouter -->|Text Query| CheckClar[check_clarification_node]
    
    URLIngest --> VersionCheck[version_check: SQLite MD5 Registry]
    FileIngest --> VersionCheck
    
    VersionCheck -->|Content Changed| EmbedStore[embed_and_store: Index Qdrant]
    VersionCheck -->|Unchanged| CheckClar
    EmbedStore --> CheckClar
    
    CheckClar -->|Pending Clarification| Recon[reconstruct_context_node: Query Rewriter]
    CheckClar -->|No Pending| Analyze[analyze_input_node: Confidence Evaluator]
    Recon --> Analyze
    
    Analyze --> InputConfRouter{input_confidence_router}
    InputConfRouter -->|LOW / Ambiguous| ClarifyNode[clarify_or_fallback_node]
    InputConfRouter -->|HIGH / Unambiguous| IdentifyProd[identify_product: Product Resolver]
    
    IdentifyProd --> ProdRouter{product_router}
    ProdRouter -->|Ambiguous Models| ClarifyNode
    ProdRouter -->|Resolved Model| ClassifyMode[classify_mode: QA vs Troubleshoot]
    
    ClassifyMode --> RetrieveNode[retrieve: Waterfall RRF Search]
    RetrieveNode --> RetrConfRouter{retrieval_confidence_router}
    
    RetrConfRouter -->|HIGH / MEDIUM| ImgFilterNode[image_filtering_node: SigLIP Visual Association]
    RetrConfRouter -->|LOW / Retries Available| RetryRetr[retry_retrieval_node]
    RetrConfRouter -->|LOW / Retries Exhausted| ClarifyNode
    
    RetryRetr --> RetrieveNode
    ImgFilterNode --> GenNode[generate: Grounded Answer / JSON Steps]
    ClarifyNode --> FormatNode[format_response: Formatter]
    GenNode --> FormatNode
    FormatNode --> End([END Response Payload])
```

### Agentic Graph States
* **`status: "answered"`**: Grounded answer generated successfully.
* **`status: "needs_clarification"`**: Multiple matching product models found; prompts user to clarify.
* **`status: "fallback"`**: Context retrieval failed or yielded no relevant chunks.
* **`retry_retrieval_node`**: Automatic retry state triggering up to `MAX_RETRIEVAL_RETRIES` (default 2) before dropping to fallback.

---

## 5. Stateful Troubleshooting Engine (`workflow_manager.py`)

```mermaid
stateDiagram-v2
    [*] --> START: User Initiates Troubleshooting Session
    
    START --> IDENTIFY_PRODUCT: Product Model Missing
    START --> RETRIEVE_KNOWLEDGE: Product Identified
    
    IDENTIFY_PRODUCT --> RETRIEVE_KNOWLEDGE: User Selects Product Model
    
    RETRIEVE_KNOWLEDGE --> DIAGNOSE: Fetch RAG Manual Context
    
    DIAGNOSE --> QUESTION: Formulate Diagnostic Check
    DIAGNOSE --> ACTION: Identify Root Cause & Repair Step
    DIAGNOSE --> ESCALATE: Symptom Unresolved / Manual Boundary Reached
    
    QUESTION --> QUESTION: Technician Answers Check (Evaluate Next Step)
    QUESTION --> ACTION: Check Confirms Root Cause
    
    ACTION --> VERIFY: Technician Performs Repair Step
    
    VERIFY --> RESOLVED: SUCCESS STATE (Fix Confirmed Fixed)
    VERIFY --> DIAGNOSE: Repair Failed -> Evaluate Next Cause
    VERIFY --> ESCALATE: ESCALATION STATE (All Procedures Exhausted)
    
    RESOLVED --> [*]
    ESCALATE --> [*]
```

### Troubleshooting States
1. **`START`**: Initialized session.
2. **`IDENTIFY_PRODUCT`**: Prompting user for appliance model number.
3. **`QUESTION`**: Asking technician a diagnostic verification question (e.g. *"Is power light ON?"*).
4. **`ACTION`**: Providing a specific manual repair procedure.
5. **`VERIFY`**: Asking technician to confirm if repair step resolved issue.
6. **`RESOLVED` (Success State)**: Issue resolved; session closed successfully.
7. **`ESCALATE` (Escalation State)**: Manual steps exhausted; recommends human technician dispatch.

---

## 6. Model Context Protocol (MCP) Server Architecture

```mermaid
graph TD
    ExtClient[Claude Desktop / IDE / External AI Client] -->|stdio / SSE GET /mcp/sse| MCPEntry[FastAPI /mcp App Mount]
    MCPEntry --> FastMCPServer[fridge_mcp_server.py: FastMCP Server]
    
    FastMCPServer --> Tool1[search_fridge_manuals: Waterfall RRF Search]
    FastMCPServer --> Tool2[lookup_error_code: Error & Pinout DB]
    FastMCPServer --> Tool3[get_thermistor_ohm_table: Thermistor Engine]
    FastMCPServer --> Tool4[lookup_part_number: OEM Parts Catalog]
    FastMCPServer --> Tool5[run_octo_agent: Full LangGraph StateGraph]
    FastMCPServer --> Tool6[troubleshoot_appliance_turn: Stateful Troubleshooting Machine]
    
    Tool1 --> QdrantDB[(Qdrant Vector Database)]
    Tool5 --> LangGraphEngine[agent_flow.py: Bounded StateGraph]
    Tool6 --> TroubleshootingEngine[workflow_manager.py: State Engine]
```

---

## 7. Security, Pre-LLM Guardrail & Rate Limiting Mechanics

```mermaid
graph LR
    Request[Client Request] --> SlowAPI[slowapi: IP Rate Limiter]
    SlowAPI -->|Rate Exceeded| RejRate[FAILURE STATE: HTTP 429 Too Many Requests]
    SlowAPI --> PydanticGuard[Pydantic Schema Validation]
    PydanticGuard -->|Invalid Schema| RejSchema[FAILURE STATE: HTTP 422 Unprocessable]
    PydanticGuard --> InjectionGuard{is_prompt_injection}
    InjectionGuard -->|Detected| RejInj[FAILURE STATE: HTTP 400 Prompt Injection]
    InjectionGuard -->|Safe| DomainGuard{is_out_of_domain}
    DomainGuard -->|Off-Topic| RejDomain[FAILURE STATE: HTTP 400 Out of Domain / 0 Tokens Spent]
    DomainGuard -->|In-Domain| SystemPrompt[Context-Isolated System Prompt]
    SystemPrompt --> LLMExecution[LLM Generation Engine]
```
