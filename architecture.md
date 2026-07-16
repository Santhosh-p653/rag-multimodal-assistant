# Architecture Specification — Multimodal RAG Assistant & Agentic Engine

This document provides a comprehensive technical breakdown of the systems, pipelines, orchestration state machines, and security layers implemented in the Multimodal RAG Assistant.

---

## 1. Document Ingestion Pipeline

During ingestion, documents are parsed, categorized using zero-shot classification, chunked, vectorized, and stored with rich metadata fields.

```mermaid
graph TD
    A[Raw Upload: PDF/DOCX/TXT] -->|MIME & Extension Guard| B(Size Validation <= 25MB)
    B -->|Passed| C[MarkItDown Text Extraction]
    B -->|If PDF| V[PyMuPDF Image & Vector Rendering]
    
    C -->|Markdown Text| D[Product Identifier Zero-Shot Classification]
    D --> E[Overlapping Character Chunker]
    
    V -->|Extract Raster & Render Vector Paths| X[Image Filter: Dimensions/Aspect/pHash]
    X -->|Save PNG & Extract Nearby Text| Y[Embed Nearby Text]
    
    E -->|Chunk Content| F[SentenceTransformers Vectorizer]
    F -->|384-dim Dense Vectors| Z[Semantic Image-Text Association]
    Y --> Z
    
    Z -->|Attach image_ids to Chunks via Cosine Sim| G[(Qdrant Vector DB Ingestion)]
```

### Payloads Stored in Qdrant
```json
{
  "chunk_id": "x100_manual.pdf::chunk_12",
  "content": "To resolve Error E105, power off the device, remove the rear cover...",
  "source_file": "x100_manual.pdf",
  "product": "X100",
  "model": "X100",
  "category": "Printer",
  "version": "v1.2",
  "product_family": "X-Series",
  "section": "Troubleshooting",
  "page": 24
}
```

---

## 2. Context-Aware Hierarchical Hybrid Search

Retrieval queries pass through entity extraction and run on a 3-level prioritized search hierarchy to ensure the most specific documentation is retrieved first, combining dense similarity and sparse BM25 scores using Reciprocal Rank Fusion (RRF).

```mermaid
graph TD
    A[User Query] --> B[Product Identifier Service]
    B -->|Extract Query Entities| C{Metadata Resolver}
    
    C -->|Level 1: Exact Product Match| D[Qdrant Search with product filter]
    D -->|Empty / Low Score| E[Level 2: Product Family Prefix Match]
    E -->|Empty / Low Score| F[Level 3: Global Search across all manuals]
    
    D -->|Results Found| G[Local BM25 Scoring + RRF Fusion]
    E -->|Results Found| G
    F --> G
    
    G -->|Combine Dense & Sparse Ranks| H[Top K Grounded Context Chunks]
```

### Fusion Algorithm (RRF)
$$\text{RRF Score}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
Where $M = \{\text{dense}, \text{sparse}\}$, $k = 60$, and $r_m(d)$ is the rank of document $d$ in result list $m$.

---

## 3. Voice Communication Layer (STT & TTS)

A hybrid audio layer transcribes incoming captured microphone signals and synthesizes outgoing assistant answers to stream playable speech.

```mermaid
graph TD
    A[Captured Mic WAV blob] --> B{Language Hint Selection}
    
    B -->|English 'en'| C[Local faster-whisper]
    C -->|whisper-small CPU int8| D[Text Transcript]
    
    B -->|Indic / Auto 'hi/ta/auto'| E[Sarvam AI Saaras v3 API]
    E -->|saaras:v3 model| D
    
    D --> F[RAG Chat / Troubleshoot Processing]
    F -->|Assistant Answer| G[Sentence Truncation: Max 3 Sentences]
    
    G --> H[edge-tts Microsoft Neural Voices]
    H -->|Language-mapped Neural Voices| I[Autoplay Audio/MPEG Stream]
```

---

## 4. Agentic Troubleshooting Orchestration State Machine

For troubleshooting issues, the assistant runs a state machine to track context across turns, ask check questions, suggest corrective repairs, and verify resolutions.

```mermaid
stateDiagram-v2
    [*] --> START: User reports issue
    
    START --> IDENTIFY_PRODUCT: No product model detected in text
    START --> RETRIEVE_KNOWLEDGE: Product identified (e.g. X100)
    
    IDENTIFY_PRODUCT --> RETRIEVE_KNOWLEDGE: User supplies model (e.g. A200)
    
    RETRIEVE_KNOWLEDGE --> DIAGNOSE: Fetch manual context chunks
    
    DIAGNOSE --> QUESTION: LLM decides to check a condition
    DIAGNOSE --> ACTION: LLM identifies root cause and repair step
    DIAGNOSE --> ESCALATE: Manual does not cover symptom
    
    QUESTION --> QUESTION: User answers (evaluate turn and ask next check)
    QUESTION --> ACTION: Check confirms diagnosis
    
    ACTION --> VERIFY: User performs step
    
    VERIFY --> RESOLVED: User confirms issue is fixed
    VERIFY --> DIAGNOSE: Action failed, evaluate next cause
    VERIFY --> ESCALATE: All manual procedures exhausted
    
    RESOLVED --> [*]
    ESCALATE --> [*]
```

### Troubleshooting Session Registry Payload
```python
{
    "session_id": "test_session_abc",
    "product": "X100",
    "issue": "E105",
    "step": 2,
    "status": "QUESTION",  # Active State
    "last_question": "Is the cooling fan spinning at all?",
    "last_action": "Power off the device, inspect rear connector...",
    "history": [
        {"question": "Is the power LED blinking?", "answer": "Yes"},
        {"question": "Is the cooling fan spinning at all?", "answer": "No"}
    ],
    "context": [...]  # Active RAG Context Chunks
}
```

---

## 5. Query Understanding & Context Reconstruction

To handle vague follow-ups, the system analyzes input confidence and reconstructs queries using session memory before retrieval.

```mermaid
graph TD
    A[User Input] --> B{Pending Clarification in Session?}
    B -->|Yes| C[Reconstruct Context Node]
    B -->|No| D[Analyze Input Node]
    C --> D
    
    D -->|LLM extracts Intent, Entities, Ambiguities| E{Input Confidence}
    E -->|HIGH or unambiguous MEDIUM| F[Proceed to Retrieval]
    E -->|LOW or ambiguous MEDIUM| G[Clarify / Fallback Node]
    
    G --> H[Return Clarification Question to UI]
```

---

## 5b. Visual Information Retrieval Filtering

Extracted images must pass a strict runtime confidence filter to avoid hallucinating unrelated visuals.

```mermaid
graph TD
    A[RRF Ranked Chunks] --> B{Retrieval Confidence}
    B -->|LOW| C[Return No Images]
    B -->|HIGH| D[Extract associated image_ids]
    B -->|MEDIUM| E[Extract associated image_ids]
    
    D --> F[Limit to Top 3 Images]
    
    E --> G[Strict Semantic Re-check]
    G -->|chunk_embedding vs image_nearby_text >= 0.65| H[Limit to Top 1 Image]
    G -->|Failed Threshold| C
```

---

## 6. Security & Isolation Layers

Each incoming API call passes through a series of security filters before hitting the core RAG or LLM processing code.

```mermaid
graph LR
    A[Client Request] --> B[slowapi Middleware: Rate Limiter]
    B -->|Check IP Limits| C[Pydantic Schema constraints: Field Lengths]
    C -->|Check Text Size| D[Prompt Guard: Injection detection]
    D -->|Check override patterns| E[Context-Isolated Prompt Builder]
    E -->|Execute RAG| F[LLM Generation]
```

---

## 7. Unified Agentic Ingestion + Retrieval Flow (LangGraph)

For ad-hoc queries combining ingestion and retrieval, the system routes tasks through a bounded **LangGraph `StateGraph`** with conditional routing decisions. This enables LLM-driven path routing (e.g. asking for clarification on product name ambiguity) while maintaining deterministic processing node boundaries.

```mermaid
graph TD
    Start([Start Route]) --> Router{Ingest Router}
    
    Router -->|URL| URL[url_ingest]
    Router -->|File| File[file_ingest]
    Router -->|No Ingestion| CheckClar[check_clarification_node]
    
    URL --> VC[version_check]
    File --> VC
    
    VC -->|Hash Changed| Embed[embed_and_store]
    VC -->|Unchanged| CheckClar
    Embed --> CheckClar
    
    CheckClar -->|Pending Clarification| Recon[reconstruct_context_node]
    CheckClar -->|No Pending| Analyze[analyze_input_node]
    Recon --> Analyze
    
    Analyze -->|High/Unambig| ID[identify_product]
    Analyze -->|Low/Ambig| Clarify[clarify_or_fallback_node]
    
    ID --> Classify[classify_mode: QA / Troubleshoot]
    Classify --> Retrieve[retrieve]
    
    Retrieve -->|High/Medium| Image[image_filtering_node]
    Retrieve -->|Low| Retry[retry_retrieval_node]
    
    Image --> Gen[generate]
    Gen --> Format[format_response]
    Clarify --> Format
```

### Agent State Schema
```python
class AgentState(TypedDict):
    query: str
    source_input: Optional[str]        # URL or filename/path
    source_content: Optional[bytes]    # raw uploaded file content
    product_id: Optional[str]
    clarification_needed: bool
    retrieved_chunks: list[dict]
    sources: list[dict]
    mode: Literal["qa", "troubleshoot"]
    answer: str
    steps: list[str]
    content_changed: bool
    version_info: Optional[str]
    clarification_options: list[str]
```
