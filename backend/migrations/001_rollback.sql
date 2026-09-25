-- ====================================================================
-- OCTO-RAG PostgreSQL Rollback Schema: 001_rollback.sql
-- ====================================================================
-- Safely drops session_turns, diagnostic_sessions, and manual_registry.

DROP TABLE IF EXISTS session_turns CASCADE;
DROP TABLE IF EXISTS diagnostic_sessions CASCADE;
DROP TABLE IF EXISTS manual_registry CASCADE;
