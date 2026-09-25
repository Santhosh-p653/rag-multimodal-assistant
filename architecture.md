# Comprehensive Architecture Specification — OCTO RAG Assistant

This document provides an exhaustive technical specification of the systems, pipelines, submodule responsibilities, orchestration state machines, security layers, Model Context Protocol (MCP) servers, state transitions, success/failure fallback states, and key architectural decisions in the **OCTO RAG Assistant**.

---

## 1. Submodule Problem-Solving Matrix & Key Architectural Decisions

Every submodule in the backend is designed to solve specific technical problems with explicit architectural rationales:

| Submodule | Target Engineering Problem | Technical Solution & Implementation | Key Architectural Decision & Rationale |
| :--- | :--- | :--- | :--- |
| **`postgres.py`** | Lack of relational persistence, missing session history, file registry and turn audits | Async SQLAlchemy + `asyncpg` engine managing `manual_registry`, `diagnostic_sessions`, and `session_turns`. | **Dual-Database Decoupling**: Offloads relational state, metadata, and audit logs to PostgreSQL 18, keeping Qdrant as a dedicated high-throughput vector index. |
| **`fridge_mcp_server.py`** | External AI clients (Claude Desktop, IDEs) lacking diagnostic tools and file management | FastMCP server exposing 10 tools: RAG search, error codes, thermistor table, parts catalog, agent flow, troubleshooting turn, PLUS Files MCP tools (`list_manuals`, `upload_manual`, `delete_manual`, `get_manual_metadata`). | **Standard Open MCP Protocol & Thread Safety**: Exposes tools over stdio and FastAPI SSE (`/mcp/sse`) with thread-safe async event loop isolation (`_run_async_safely`). |
| **`mcp_client.py`** | Internal services requiring diagnostic lookup without network overhead | Programmatic client helper for invoking local MCP tools directly within Python nodes. | **Decoupled Tool Execution**: Prevents HTTP network overhead during internal Python service calls. |
| **`prompt_guard.py`** | Jailbreaks, prompt injection & off-topic LLM token waste | Regex filter intercepting injection patterns (`is_prompt_injection`) AND non-equipment domain topics (`is_out_of_domain`). | **Gateway Pre-LLM Boundary**: Rejects off-topic prompts *before* vector search or LLM invocation, expending **0 LLM API tokens** on rejected requests. |
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
| **`query_understanding.py`** | English-only assumption failing on Indic multilingual input | Unicode script range analyzer (`detect_query_script`), English query normalization for RAG retrieval, and language tag preservation (`ta`, `hi`, `en`). | **Cross-Lingual Intent Normalization**: Enables high-precision English technical document retrieval while preserving the technician's native language. |
| **`agent_flow.py`** | Language mismatch between query and response + console crash | Bounded **LangGraph `StateGraph`** with native-script LLM prompt directives, localized generation, and Unicode-safe logging (`_safe_log`). | **End-to-End Localization & Encoding Safety**: Guarantees native language answers for Indic users and prevents Windows `cp1252` console crashes. |
| **`workflow_manager.py`**| LLM state drift in multi-turn diagnostic chats | Implements a state-guided session registry (`START` $\rightarrow$ `QUESTION` $\rightarrow$ `ACTION` $\rightarrow$ `VERIFY` $\rightarrow$ `RESOLVED`/`ESCALATE`). | **SOP State Enforcement**: Enforces structured diagnostic discipline, preventing premature repair steps. |
| **`audio.py`** | Indic language voice failures and pronunciation drift | Hybrid routing: Sarvam AI (`saaras:v2` STT & `bulbul:v1` TTS with `meera`/`arvind` voices) for Indic, `faster-whisper` and `edge-tts` for English. | **Voice Engine Specialization**: Directs Indic speech to Sarvam AI and English speech to local Whisper/edge-tts. |
| **`main.py`** | System DDoS and resource exhaustion | Wraps all routes in `slowapi` rate limiters, mounts `/mcp` SSE endpoint, and exposes PostgreSQL audit & session endpoints. | **API Rate Limiting & Lifecycle Governance**: Protects endpoints and exposes session audit telemetries. |

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
    ExtClient[Claude Desktop / Cursor / IDE / External AI Client] -->|stdio / SSE GET /mcp/sse| MCPEntry[FastAPI /mcp App Mount]
    MCPEntry --> FastMCPServer[fridge_mcp_server.py: FastMCP Server 10 Tools]
    
    subgraph Diagnostic & Diagnostic Agent Tools
        FastMCPServer --> Tool1[search_fridge_manuals: Waterfall RRF Search]
        FastMCPServer --> Tool2[lookup_error_code: Error & Pinout DB]
        FastMCPServer --> Tool3[get_thermistor_ohm_table: Thermistor Engine]
        FastMCPServer --> Tool4[lookup_part_number: OEM Parts Catalog]
        FastMCPServer --> Tool5[run_octo_agent: Full LangGraph StateGraph]
        FastMCPServer --> Tool6[troubleshoot_appliance_turn: Stateful Troubleshooting Machine]
    end

    subgraph Files MCP Asset Management Tools
        FastMCPServer --> Tool7[list_manuals: Query PostgreSQL Registry & Vector Sources]
        FastMCPServer --> Tool8[upload_manual: Base64 Ingestion + Chunk + Qdrant + Postgres]
        FastMCPServer --> Tool9[delete_manual: Atomic Purge from Disk, Qdrant & Postgres]
        FastMCPServer --> Tool10[get_manual_metadata: Hash, Chunk Count & Metadata Inspection]
    end
    
    Tool1 --> QdrantDB[(Qdrant Vector Database)]
    Tool5 --> LangGraphEngine[agent_flow.py: Bounded StateGraph]
    Tool6 --> TroubleshootingEngine[workflow_manager.py: State Engine]
    Tool7 --> PostgresDB[(PostgreSQL 18: manual_registry)]
    Tool8 --> PostgresDB
    Tool9 --> PostgresDB
    Tool10 --> PostgresDB
```

### Thread-Safe Async MCP Execution (`_run_async_safely`)
FastMCP runs synchronous Python tool functions within client runner threads. Directly executing `asyncio.run(coroutine)` on an existing coroutine across threads creates `'NoneType' object has no attribute 'send'`. OCTO-RAG implements a thread-safe helper `_run_async_safely(async_fn, *args, **kwargs)` that instantiates fresh coroutines in a clean, dedicated worker thread event loop via `concurrent.futures.ThreadPoolExecutor`.

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

---

## 8. Dual-Database Relational + Vector Architecture

```mermaid
graph TD
    Client[FastAPI Application Gateway] --> StoreRouter{Storage Router}
    
    StoreRouter -->|Vectors & Semantic Embeddings| Qdrant[(Qdrant Vector DB)]
    StoreRouter -->|Relational State, Audits & Metadata| Postgres[(PostgreSQL 18 DB)]
    
    subgraph Qdrant Engine
        Qdrant --> TextColl[Collection: manuals 384-dim Dense Text]
        Qdrant --> ImgColl[Collection: manual_images 768-dim SigLIP 2 Vision]
    end
    
    subgraph PostgreSQL Relational Store
        Postgres --> TblManuals[manual_registry: MD5 hashes, sizes, chunks, category]
        Postgres --> TblSessions[diagnostic_sessions: session_id, state, equipment_type]
        Postgres --> TblTurns[session_turns: turn audits, query, response, lang, confidence]
    end
```

### Decoupling Rationale
1. **Vector Performance**: Qdrant handles high-dimensional HNSW vector search without relational index overhead.
2. **ACID Metadata Integrity**: PostgreSQL enforces unique constraints on document MD5 hashes, ensuring duplicate files are instantly detected before initiating expensive chunking or embedding.
3. **Technician Audit Trail**: Multi-turn troubleshooting steps, user feedback, and model citations are persisted permanently for regulatory and SOP compliance.

---

## 9. Multilingual Voice & Query-to-Response Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Technician as Technician (Field / Shop Floor)
    participant VoiceUI as Frontend Voice Recorder
    participant AudioSvc as audio.py (STT Router)
    participant QueryUnd as query_understanding.py
    participant Retriever as retriever.py (Waterfall + RRF)
    participant AgentFlow as agent_flow.py (LangGraph)
    participant TTSSvc as audio.py (TTS Router)

    Technician->>VoiceUI: Speaks in Tamil: "ஃப்ரீஸர் பத்தி சொல்லு"
    VoiceUI->>AudioSvc: POST /transcribe (Audio blob)
    AudioSvc-->>VoiceUI: Transcribed Tamil Text
    VoiceUI->>AgentFlow: POST /agent/run (query, language="auto")
    AgentFlow->>QueryUnd: Script Detection & Understanding
    Note over QueryUnd: Detects Tamil (\u0b80-\u0bff), tags lang="ta", normalizes to English: "Tell me about the freezer"
    QueryUnd-->>AgentFlow: normalized_query, language="ta"
    AgentFlow->>Retriever: Waterfall Search with English Query
    Retriever-->>AgentFlow: Top Grounded Manual Chunks (English)
    AgentFlow->>AgentFlow: LLM Generation (System Directive: MUST reply in Tamil)
    Note over AgentFlow: Generates: "ஃப்ரீஸர் பகுதி 0 டிகிரி ஃபாரன்ஹைட்..."
    AgentFlow-->>VoiceUI: Grounded Tamil Response Payload
    VoiceUI->>TTSSvc: POST /speak (text, language="ta")
    TTSSvc-->>VoiceUI: Sarvam AI synthesized audio (meera voice)
    VoiceUI->>Technician: Audio Playback in Native Tamil
```

---

## 10. Decoupled Dual UI Architecture

1. **User / Technician Console (`/` and `/app`)**:
   - Zero admin buttons or configuration forms.
   - Large hands-free voice trigger and auto-playing regional voice synthesis.
   - Step-by-step diagnostic verification cards with structured SOP actions.
   - Multimodal schematic zoom viewer for wiring diagrams.

2. **Admin Asset & SOP Portal (`/admin`)**:
   - Database telemetry cards: PostgreSQL connection status, total registered manuals, stored sessions, active turns.
   - Drag-and-drop manual ingestion with progress bars and equipment categorization tags (`industrial`, `automobile`, `appliance`).
   - File deletion modal with complete Qdrant vector and PostgreSQL cleanup.
   - Real-time audit activity timeline showing technician query turns, confidence scores, and matched source documents.

