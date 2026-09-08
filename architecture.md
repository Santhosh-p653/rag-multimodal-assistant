# Comprehensive Architecture Specification — OCTO RAG Assistant

This document provides a technical breakdown of the systems, pipelines, submodule problem-solving responsibilities, orchestration state machines, security layers, Model Context Protocol (MCP) servers, and architectural decisions implemented in the OCTO RAG Assistant.

---

## 1. Submodule Problem-Solving Matrix

Every submodule in the backend is designed to resolve specific technical and operational challenges:

| Submodule | Target Engineering Problem | Technical Solution & Implementation | Key Architectural Decision |
| :--- | :--- | :--- | :--- |
| **`fridge_mcp_server.py`** | External AI clients (Claude Desktop, IDEs) lacking diagnostic tool access | Implements a **FastMCP** server exposing `lookup_error_code`, `get_thermistor_ohm_table`, `lookup_part_number`, and `search_fridge_manuals`. | Exposes tools over stdio and FastAPI SSE (`/mcp/sse`), establishing standard MCP protocol compatibility. |
| **`mcp_client.py`** | Internal services requiring diagnostic lookup without network overhead | Programmatic client helper for invoking local MCP tools directly within Python nodes. | Decouples MCP tool logic from FastAPI routing and agent nodes. |
| **`prompt_guard.py`** | Jailbreaks, prompt injection & off-topic LLM token waste | Regex filter intercepting injection patterns (`is_prompt_injection`) AND non-refrigerator domain topics (`is_out_of_domain`). | Rejects non-refrigerator prompts at the API boundary, spending **0 LLM API tokens** on off-topic requests. |
| **`parser.py`** | Multi-format layout destruction in PDFs/DOCX | Uses **Microsoft MarkItDown** to render files into unified Markdown text before chunking. | Standardizes text schemas regardless of initial file extension. |
| **`image_extractor.py`** | Loss of vector schematics & diagrams in PDFs | Combines PyMuPDF raster extraction with custom vector drawing region clustering (`get_vector_drawing_regions`), rendering path diagrams to PNGs. | Captures electrical circuit blueprints and CAD path drawings missed by standard PDF image extractors. |
| **`image_filters.py`** | Qdrant vector bloat from decorative logos/lines | Applies aspect ratio bounds ($0.2 \le \text{AR} \le 5.0$), page area checks, and perceptual hash (`pHash`) deduplication ($\le 2$ repeat threshold). | Filters out header logos, footer icons, and line dividers before vector indexing. |
| **`chunker.py`** | Context loss across chunk boundaries | Uses a character-sliding window (`CHUNK_SIZE=500`, `OVERLAP=100`) while propagating metadata header tags to each chunk. | Retains document headings and section context across overlapping chunks. |
| **`embedder.py`** | High CPU overhead for text vector encoding | Implements a thread-safe Singleton pattern for `SentenceTransformers` (`all-MiniLM-L6-v2`) with `@lru_cache(maxsize=1024)`. | Eliminates redundant model instantiation and duplicate text embedding calculations. |
| **`vision_embedder.py`** | Text-only search failing on visual manual content | Implements a SigLIP 2 Singleton (`google/siglip-base-patch16-224`) generating 768-dim joint text-image embeddings. | Enables cross-modal text-to-image semantic vector search. |
| **`vision_search.py`** | Irrelevant visual diagram retrieval | Queries the dedicated `manual_images` Qdrant collection, enforcing application-level `VISION_SCORE_THRESHOLD` filtering. | Separates image vector search from text chunk search boundaries. |
| **`vector_store.py`** | Payload schema pollution & vector duplication | Maintains dual Qdrant collections (`manuals` & `manual_images`), performing deletion by source file before re-indexing. | Guarantees vector uniqueness and isolation between text and visual assets. |
| **`hybrid_search.py`** | Keyword mismatch in pure dense vector search | Implements in-memory **BM25** sparse ranking combined with dense candidate vectors using **Reciprocal Rank Fusion (RRF)** ($k=60$). | Balances exact keyword/error code matching with semantic intent retrieval. |
| **`retriever.py`** | Empty search hits from strict metadata filters | Implements a 3-level waterfall search (Exact Product $\rightarrow$ Family Prefix $\rightarrow$ Global Search) run concurrently with SigLIP vision search. | Eliminates search drop-offs while prioritizing exact product documentation. |
| **`agent_flow.py`** | Uncontrolled agent loops & redundant re-indexing | Uses a bounded **LangGraph `StateGraph`** with SQLite MD5 hash version checking (`registry.db`). | Ensures deterministic state transitions and skips re-embedding unchanged documents. |
| **`workflow_manager.py`**| LLM state drift in multi-turn diagnostic chats | Implements a state-guided session registry (`START` $\rightarrow$ `QUESTION` $\rightarrow$ `ACTION` $\rightarrow$ `VERIFY` $\rightarrow$ `RESOLVED`/`ESCALATE`). | Enforces SOP diagnostic discipline, preventing repetitive or premature fixes. |
| **`audio.py`** | High latency & Indic language accent failures | Hybrid routing: local `faster-whisper` (`int8` CPU) for English, Sarvam AI (`Saaras v3`) for Indic audio, and `edge-tts` for neural speech synthesis. | Provides fast English STT while preserving accuracy for Indic regional dialects. |
| **`main.py`** | System DDoS and resource exhaustion | Wraps all routes in `slowapi` rate limiters, mounts `/mcp` SSE endpoint, and pre-warms models during startup. | Enforces API rate limits and mounts MCP server transport. |

---

## 2. Multimodal Document & Visual Ingestion Pipeline

```mermaid
graph TD
    A[Raw Upload: PDF/DOCX/PPTX/XLSX/TXT] --> B{MIME & Size Guard: <= 25MB}
    B -->|Passed| C[MarkItDown Text Conversion]
    B -->|Failed| Drop[Reject: HTTP 400/413]
    
    C --> D[PyMuPDF Image & Vector Path Extraction]
    D --> E[image_filters.py: Aspect Ratio & pHash Check]
    
    E -->|Passed Image/Vector Crop| F[vision_embedder.py: SigLIP 2 Encoder]
    F -->|768-dim Visual Vectors| G[(Qdrant: manual_images collection)]
    
    C --> H[Product Zero-Shot Metadata Classifier]
    H --> I[chunker.py: Sliding Window Chunker 500/100]
    I --> J[embedder.py: SentenceTransformers Encoder]
    J -->|384-dim Dense Vectors| K[(Qdrant: manuals collection)]
```

---

## 3. Model Context Protocol (MCP) Server Architecture

```mermaid
graph TD
    ExtClient[Claude Desktop / IDE / External AI Agent] -->|stdio / SSE GET /mcp/sse| MCPEntry[FastAPI /mcp App Mount]
    MCPEntry --> FastMCPServer[fridge_mcp_server.py: FastMCP Instance]
    
    FastMCPServer --> Tool1[search_fridge_manuals]
    FastMCPServer --> Tool2[lookup_error_code]
    FastMCPServer --> Tool3[get_thermistor_ohm_table]
    FastMCPServer --> Tool4[lookup_part_number]
    
    Tool1 --> QdrantDB[(Qdrant Vector Database)]
    Tool2 --> ErrorDB[Built-in Error & Pinout Specs]
    Tool3 --> ThermistorCalc[NTC Resistance Formula Engine]
    Tool4 --> OEMCatalog[OEM Spare Parts Catalog]
```

---

## 4. Pre-LLM Security & Domain Boundary Architecture

```mermaid
graph LR
    Request[Client Request] --> SlowAPI[slowapi: IP Rate Limiter]
    SlowAPI --> PydanticGuard[Pydantic Schema Validation]
    PydanticGuard --> InjectionGuard{is_prompt_injection}
    InjectionGuard -->|Detected| Reject1[HTTP 400: Injection Violation]
    InjectionGuard -->|Safe| DomainGuard{is_out_of_domain}
    DomainGuard -->|Off-Topic| Reject2[HTTP 400: Out of Domain Boundary]
    DomainGuard -->|In-Domain| SystemPrompt[Context-Isolated System Prompt]
    SystemPrompt --> LLMExecution[LLM Generation Engine]
```

---

## 5. LangGraph Unified Agentic Execution Pipeline

The `POST /agent/run` endpoint executes a bounded **LangGraph `StateGraph`**:

```mermaid
graph TD
    Start([Start Endpoint: POST /agent/run]) --> IngestRouter{Ingest Router}
    
    IngestRouter -->|URL input| URL[url_ingest: BeautifulSoup4 Scraper]
    IngestRouter -->|File input| File[file_ingest: MarkItDown Converter]
    IngestRouter -->|Query only| CheckClar[check_clarification_node]
    
    URL --> VersionCheck[version_check: SQLite MD5 Hash Registry]
    File --> VersionCheck
    
    VersionCheck -->|Content Changed| EmbedStore[embed_and_store: Chunk & Index Qdrant]
    VersionCheck -->|Content Unchanged| CheckClar
    EmbedStore --> CheckClar
    
    CheckClar -->|Pending Clarification| Recon[reconstruct_context_node: Query Rewriter]
    CheckClar -->|No Pending Clarification| Analyze[analyze_input_node: Confidence Evaluator]
    Recon --> Analyze
    
    Analyze --> ConfRouter{Input Confidence Router}
    ConfRouter -->|LOW / Ambiguous| ClarifyNode[clarify_or_fallback_node]
    ConfRouter -->|HIGH / Unambiguous| IdentifyProd[identify_product: Product Matching]
    
    IdentifyProd --> ProdRouter{Product Router}
    ProdRouter -->|Ambiguous Models| ClarifyNode
    ProdRouter -->|Resolved Model| ClassifyMode[classify_mode: QA vs Troubleshoot]
    
    ClassifyMode --> RetrieveNode[retrieve: Waterfall RRF Hybrid Search]
    RetrieveNode --> RetrConfRouter{Retrieval Confidence Router}
    
    RetrConfRouter -->|HIGH / MEDIUM| ImgFilterNode[image_filtering_node: SigLIP Visual Association]
    RetrConfRouter -->|LOW / Low Score| RetryRetr[retry_retrieval_node]
    
    RetryRetr --> RetrieveNode
    ImgFilterNode --> GenNode[generate: LLM Grounded Answer / JSON Steps]
    ClarifyNode --> FormatNode[format_response: Response Formatter]
    GenNode --> FormatNode
    FormatNode --> End([END Response])
```

---

## 6. Agentic Troubleshooting Orchestration State Machine

For diagnostic support, the system tracks structured state across user turns ([workflow_manager.py](file:///c:/Users/SAMSUNG/OneDrive/Desktop/rag-multimodal-assistant/backend/app/services/workflow_manager.py)):

```mermaid
stateDiagram-v2
    [*] --> START: User Reports Technical Issue
    
    START --> IDENTIFY_PRODUCT: Missing Model ID in Text
    START --> RETRIEVE_KNOWLEDGE: Product Identified (e.g. Profile)
    
    IDENTIFY_PRODUCT --> RETRIEVE_KNOWLEDGE: User Selects Product Model
    
    RETRIEVE_KNOWLEDGE --> DIAGNOSE: Fetch RAG Manual Chunks
    
    DIAGNOSE --> QUESTION: LLM Formulates Diagnostic Check
    DIAGNOSE --> ACTION: LLM Identifies Root Cause & Repair Step
    DIAGNOSE --> ESCALATE: Symptom Uncovered in Documentation
    
    QUESTION --> QUESTION: User Answers Check (Evaluate & Ask Next Check)
    QUESTION --> ACTION: Check Confirms Root Cause
    
    ACTION --> VERIFY: User Performs Repair Step
    
    VERIFY --> RESOLVED: User Confirms Problem Fixed
    VERIFY --> DIAGNOSE: Action Failed -> Evaluate Next Cause
    VERIFY --> ESCALATE: All Manual Procedures Exhausted
    
    RESOLVED --> [*]
    ESCALATE --> [*]
```
