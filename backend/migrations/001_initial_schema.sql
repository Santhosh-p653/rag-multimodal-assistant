-- ====================================================================
-- OCTO-RAG PostgreSQL Relational Schema: 001_initial_schema.sql
-- ====================================================================
-- Stores file registry, diagnostic sessions, and conversation audit turns.
-- Qdrant vector database remains untouched for dense & sparse embeddings.

-- 1. Manual Registry Table
CREATE TABLE IF NOT EXISTS manual_registry (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    equipment_type VARCHAR(100) NOT NULL DEFAULT 'industrial',
    model VARCHAR(100),
    file_hash VARCHAR(64) NOT NULL,
    chunks_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_manual_registry_hash ON manual_registry(file_hash);
CREATE INDEX IF NOT EXISTS idx_manual_registry_filename ON manual_registry(filename);

-- 2. Diagnostic Sessions Table
CREATE TABLE IF NOT EXISTS diagnostic_sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    equipment_model VARCHAR(100),
    current_issue TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'START',
    step_number INTEGER NOT NULL DEFAULT 0,
    language VARCHAR(20) NOT NULL DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_sessions_user_id ON diagnostic_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_diagnostic_sessions_updated_at ON diagnostic_sessions(updated_at DESC);

-- 3. Session Turns Table (Granular Audit Log)
CREATE TABLE IF NOT EXISTS session_turns (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL REFERENCES diagnostic_sessions(session_id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL,
    message_text TEXT NOT NULL,
    question TEXT,
    action TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_turns_session_id ON session_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_session_turns_created_at ON session_turns(created_at DESC);
