
# OCTO-RAG — Multimodal RAG & AI Diagnostic Infrastructure

**OCTO-RAG** is an industrial and automotive multimodal Retrieval-Augmented Generation (RAG) and agentic troubleshooting system built by **Santhosh Paramasivan** for technical equipment diagnostics — combining dual-store persistence (Qdrant + PostgreSQL), vision search, stateful diagnostic workflows, end-to-end multilingual voice I/O (Tamil, Hindi, English), a 10-tool native MCP server, and a decoupled Dual UI.

**Author:** Santhosh Paramasivan  
**GitHub:** [Santhosh-p653](https://github.com/Santhosh-p653)  
**Focus:** AI Infrastructure · Multimodal RAG · Agentic AI · Model Context Protocol (MCP) · Dual-Store Architecture

---

## Migration & System Feature Status Badges

| Module / Capability | Status | Implementation Details |
|---|---|---|
| **Multi-Language Voice & Translation Pipeline** | ![Done](https://img.shields.io/badge/status-✅%20done-success) | Sarvam AI (`saaras:v2` / `bulbul:v1`) + `faster-whisper` + `edge-tts`. Native script detection (Tamil `\u0b80-\u0bff`, Hindi `\u0900-\u097f`), English normalized retrieval, localized native generation, and voice response synthesis. |
| **PostgreSQL Relational Store & Migration** | ![Done](https://img.shields.io/badge/status-✅%20done-success) | Async SQLAlchemy + `asyncpg` engine. Schema tables: `manual_registry`, `diagnostic_sessions`, `session_turns`. Migration CLI script (`backend/scripts/migrate_postgres.py`) with zero vector loss. |
| **Files MCP Server Tools (10 Diagnostic Tools)** | ![Done](https://img.shields.io/badge/status-✅%20done-success) | Exposes `list_manuals`, `upload_manual`, `delete_manual`, `get_manual_metadata`, `search_fridge_manuals`, `lookup_error_code`, `get_thermistor_ohm_table`, `lookup_part_number`, `run_octo_agent`, `troubleshoot_appliance_turn`. Thread-safe async execution. |
| **Dual UI Architecture** | ![Done](https://img.shields.io/badge/status-✅%20done-success) | Pure Operator/Technician UI at `/` and `/app` (hands-free voice, live visual cards, zero admin clutter). Dedicated Asset & SOP Portal at `/admin` (upload progress, deletion confirmation modal, equipment category tags, audit timeline). |
| **Hybrid Retrieval & Vision Search** | ![Done](https://img.shields.io/badge/status-✅%20done-success) | 3-level waterfall retrieval (Exact Product → Family Prefix → Global) fused with BM25 sparse matching via Reciprocal Rank Fusion ($k=60$) + SigLIP 2 cross-modal image embeddings. |
| **Pre-LLM Security & Domain Guardrails** | ![Done](https://img.shields.io/badge/status-✅%20done-success) | Prompt injection regex shield + gateway domain boundary (`is_out_of_domain`) expending **0 LLM API tokens** on off-topic requests. |

---

## What is OCTO-RAG?

A human-centered, production-grade **Multimodal Industrial & Automotive RAG Assistant**, **State-Guided Troubleshooting Engine**, and **MCP Diagnostic Server** designed for shop-floor technicians, field maintenance engineers, and technical support centers.

**Dual-Database Storage Model:**
- **Qdrant Vector Database**: Dedicated vector engine hosting dual collections (`manuals` 384-dim dense text embeddings and `manual_images` 768-dim SigLIP 2 vision embeddings).
- **PostgreSQL 18 Relational Engine**: Source of truth for document inventory metadata (`manual_registry`), stateful diagnostic sessions (`diagnostic_sessions`), and technician audit turn logs (`session_turns`).

---

## Dual UI Architecture

1. **User / Technician Console (`/` and `/app`)**:
   - Designed for hands-free field use and fast technical lookup.
   - Live microphone recording with auto-detection for English, Tamil, and Hindi.
   - Grounded answer cards with exact page citations (`📄 Page 14`), multimeter test points, and visual schematics.
   - Interactive troubleshooting cards with bounded state decisions (`[YES]` / `[NO]`).
   - Read-aloud audio player with native regional voice synthesis.
   - Zero admin controls, clean technician-focused interface.

2. **Admin Asset & SOP Portal (`/admin`)**:
   - System telemetry dashboard with real-time PostgreSQL connection health, registered manual counts, and vector index status.
   - Drag-and-drop manual uploader with multi-stage progress tracking and equipment category tagging (`industrial`, `automobile`, `appliance`).
   - Document library with MD5 hash validation, chunk counters, and safe deletion modal with Qdrant vector cleanup.
   - Live Audit Trail timeline displaying multi-turn technician queries, detected languages, matched manuals, and latency.

---

## Multilingual Voice & Query-to-Response Pipeline

```mermaid
flowchart TD
    UserVoice[Technician Audio / Text Input] --> STTRouter{Audio or Text?}
    
    STTRouter -->|Audio Input| ASR[STT Router: Sarvam AI Indic / faster-whisper EN]
    ASR --> RawText[Raw Transcribed Text]
    STTRouter -->|Text Input| RawText
    
    RawText --> ScriptDetector[Script & Language Detector: \u0b80-\u0bff Tamil, \u0900-\u097f Hindi, ASCII English]
    ScriptDetector --> Normalizer[Intent Normalizer: Translates to English for Vector Search]
    
    Normalizer --> WaterfallRAG[3-Level Waterfall Retrieval + RRF BM25 over Qdrant]
    WaterfallRAG --> GroundedContext[English Technical Context + Visual Schematics]
    
    GroundedContext --> LocalizedGen[LLM Generation Node: Strict Native Script System Directive]
    ScriptDetector -.->|Propagate target language: ta / hi / en| LocalizedGen
    
    LocalizedGen --> LocalizedAnswer[Localized Grounded Answer: e.g. Native Tamil / Hindi]
    LocalizedAnswer --> TTSRouter{Language Router}
    
    TTSRouter -->|Tamil 'ta' / Hindi 'hi'| SarvamTTS[Sarvam AI Bulbul v1: meera / arvind / ananya]
    TTSRouter -->|English 'en'| EdgeTTS[edge-tts Microsoft Neural TTS]
    
    SarvamTTS --> AudioOutput[Audio Stream / Playback in Field]
    EdgeTTS --> AudioOutput
```

### Key Multilingual Enhancements
- **No Translation Drift**: Technical parameters (volts, ohms, part numbers, model codes) are preserved intact while explanatory instructions are rendered in fluent native script.
- **Console Encoding Safety**: Replaced raw standard output prints with Unicode-safe sanitizers (`_safe_log`) to prevent Windows console `charmap` codec crashes on regional Indic text.
- **Synchronized Voice Synthesis**: Audio generation automatically picks the matching Indic voice profile (`meera` for Tamil, `arvind` for Hindi) via Sarvam AI with instant fallback to neural `edge-tts`.

---

## PostgreSQL Relational Schema & Migration

### Schema Definition (`backend/migrations/001_initial_schema.sql`)
- **`manual_registry`**: `id`, `filename`, `file_hash` (MD5 unique constraint), `file_size_bytes`, `chunks_count`, `equipment_type`, `model`, `uploaded_at`, `is_active`.
- **`diagnostic_sessions`**: `session_id` (UUID PK), `current_state`, `equipment_type`, `model`, `created_at`, `updated_at`.
- **`session_turns`**: `id`, `session_id` (FK), `turn_index`, `user_input`, `system_response`, `detected_language`, `retrieval_confidence`, `context_citations`, `created_at`.

### Running the Migration
To migrate legacy SQLite records or sync existing physical PDFs into PostgreSQL:

```bash
# Ensure PostgreSQL is running and backend/.env contains:
# POSTGRES_URL=postgresql+asyncpg://postgres:<password>@localhost:5432/octo_rag

python backend/scripts/migrate_postgres.py
```

Output:
```text
============================================================
OCTO-RAG PostgreSQL Database Migration
============================================================
Testing PostgreSQL connection: postgresql+asyncpg://postgres:***@localhost:5432/octo_rag
[OK] Connected to PostgreSQL: PostgreSQL 18.4 on x86_64-windows
[OK] Initial schema applied successfully.
[OK] Migrated 7 manual records from SQLite registry.db.
[OK] Registered 1 new physical manuals.
[OK] Migration completed: 8 total manuals now registered in PostgreSQL.
============================================================
```

---

## MCP Diagnostic Server (10 FastMCP Tools)

`fridge_mcp_server.py` exposes 10 production tools for Claude Desktop, Cursor, and IDEs:

### Diagnostic & Agent Tools
1. `search_fridge_manuals(query, source_file)` — Grounded hybrid RRF search over Qdrant manuals.
2. `lookup_error_code(brand, model, code)` — Resolves appliance & OBD-II DTC codes to PCB test points and repair procedures.
3. `get_thermistor_ohm_table(temp_celsius)` — NTC thermistor resistance (kΩ) for multimeter diagnostics.
4. `lookup_part_number(model, component_name)` — OEM part numbers, voltages, and repair difficulty.
5. `run_octo_agent(query, source_input)` — Full LangGraph agentic execution pipeline.
6. `troubleshoot_appliance_turn(session_id, message)` — Multi-turn stateful troubleshooting machine.

### Files MCP Tools
7. `list_manuals()` — Returns JSON array of all registered manuals in PostgreSQL with file hashes, chunks, and vector source availability.
8. `upload_manual(filename, content_base64, equipment_type, model)` — Ingests base64 manual, parses via MarkItDown, chunks, embeds into Qdrant, and registers in PostgreSQL.
9. `delete_manual(filename)` — Atomically purges raw documents, parsed markdown, extracted images, Qdrant vectors, and PostgreSQL records.
10. `get_manual_metadata(filename)` — Retrieves detailed indexing metadata and telemetry for a specific manual.

### Claude Desktop Setup
Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "octo-rag": {
      "command": "python",
      "args": [
        "C:\\Users\\SAMSUNG\\OneDrive\\Desktop\\rag-multimodal-assistant\\backend\\app\\mcp\\fridge_mcp_server.py"
      ]
    }
  }
}
```

---

## Quickstart

### 1. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
python scripts/migrate_postgres.py

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

- **User Troubleshooting Console**: `http://localhost:3000` or `http://localhost:3000/app`
- **Admin Management Portal**: `http://localhost:3000/admin`
- **FastAPI OpenAPI Docs**: `http://localhost:8000/docs`
- **MCP SSE Endpoint**: `http://localhost:8000/mcp/sse`

---

## Author

**Santhosh Paramasivan**  
AI Engineer — AI Infrastructure, Multimodal RAG, Agentic Systems, MCP  
- GitHub: [`Santhosh-p653`](https://github.com/Santhosh-p653)  
- LinkedIn: [santhosh-paramasivan](https://www.linkedin.com/in/santhosh-paramasivan)  
- Portfolio: [santhosh-p653.github.io](https://santhosh-p653.github.io/portfolio/)


