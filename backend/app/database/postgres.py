"""
postgres.py — PostgreSQL relational engine for OCTO-RAG.
Handles session state, file registry, and audit logs with SQLAlchemy async + asyncpg.
Maintains Qdrant as the pure vector engine.
"""
import os
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    select,
    delete,
    func,
    text as sql_text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)

from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


# ─── Relational Schema Models ─────────────────────────────────────────────────

class ManualRegistry(Base):
    """
    manual_registry: Tracks ingested technical manuals, file hashes, and chunk counts.
    Prevents duplicate vector ingestion via MD5 hash verification.
    """
    __tablename__ = "manual_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), unique=True, nullable=False, index=True)
    equipment_type = Column(String(100), default="industrial", nullable=False)
    model = Column(String(100), nullable=True)
    file_hash = Column(String(64), nullable=False, index=True)
    chunks_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "equipment_type": self.equipment_type,
            "model": self.model,
            "file_hash": self.file_hash,
            "chunks_count": self.chunks_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DiagnosticSession(Base):
    """
    diagnostic_sessions: Tracks multi-turn troubleshooting sessions, equipment state, and language.
    """
    __tablename__ = "diagnostic_sessions"

    session_id = Column(String(100), primary_key=True, index=True)
    user_id = Column(String(100), default="default_user", nullable=False, index=True)
    equipment_model = Column(String(100), nullable=True)
    current_issue = Column(Text, nullable=True)
    status = Column(String(50), default="START", nullable=False)
    step_number = Column(Integer, default=0, nullable=False)
    language = Column(String(20), default="en", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    turns = relationship(
        "SessionTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionTurn.created_at"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "equipment_model": self.equipment_model,
            "current_issue": self.current_issue,
            "status": self.status,
            "step_number": self.step_number,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SessionTurn(Base):
    """
    session_turns: Granular audit trail for every user message and assistant diagnostic response.
    """
    __tablename__ = "session_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(100),
        ForeignKey("diagnostic_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sender = Column(String(20), nullable=False)  # "user" or "assistant"
    message_text = Column(Text, nullable=False)
    question = Column(Text, nullable=True)
    action = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("DiagnosticSession", back_populates="turns")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "sender": self.sender,
            "message_text": self.message_text,
            "question": self.question,
            "action": self.action,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─── Engine & Sessionmaker Management ─────────────────────────────────────────

_async_engine: Optional[AsyncEngine] = None
_async_session_factory = None
_pg_available: Optional[bool] = None
_pg_last_error: Optional[str] = None


def get_postgres_url() -> str:
    url = getattr(settings, "POSTGRES_URL", "") or os.getenv(
        "POSTGRES_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/octo_rag"
    )
    # Ensure driver is asyncpg
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_async_engine() -> AsyncEngine:
    global _async_engine, _async_session_factory
    if _async_engine is None:
        url = get_postgres_url()
        _async_engine = create_async_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=15,
            pool_recycle=1800,
        )
        _async_session_factory = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _async_engine


def get_session_factory():
    if _async_session_factory is None:
        get_async_engine()
    return _async_session_factory


async def check_postgres_health() -> Tuple[bool, str, Dict[str, Any]]:
    """
    Test connectivity to the PostgreSQL instance and report version/table telemetry.
    Returns: (is_healthy, status_message, telemetry_dict)
    """
    global _pg_available, _pg_last_error
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            result = await conn.execute(sql_text("SELECT version();"))
            version_str = result.scalar() or "PostgreSQL (connected)"

            # Check table counts
            count_res = await conn.execute(sql_text("""
                SELECT 
                    (SELECT COUNT(*) FROM manual_registry) as manuals_count,
                    (SELECT COUNT(*) FROM diagnostic_sessions) as sessions_count,
                    (SELECT COUNT(*) FROM session_turns) as turns_count
            """))
            row = count_res.mappings().one_or_none()
            stats = dict(row) if row else {}

        _pg_available = True
        _pg_last_error = None
        return True, "connected", {
            "version": version_str.split(",")[0] if version_str else "PostgreSQL",
            "manuals_registered": stats.get("manuals_count", 0),
            "sessions_stored": stats.get("sessions_count", 0),
            "total_turns": stats.get("turns_count", 0)
        }
    except Exception as exc:
        _pg_available = False
        _pg_last_error = str(exc)
        logger.warning(f"[PostgreSQL] Health check failed: {exc}")
        return False, f"disconnected: {str(exc)}", {
            "error": str(exc),
            "manuals_registered": 0,
            "sessions_stored": 0,
            "total_turns": 0
        }


async def init_postgres_db():
    """
    Initialize database schema (creates tables if they do not exist).
    Safe to execute on server startup.
    """
    try:
        engine = get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[PostgreSQL] Relational schema verified and ready.")
        return True
    except Exception as e:
        logger.warning(f"[PostgreSQL] Could not initialize tables (will operate with fallback): {e}")
        return False


# ─── High-Level Relational CRUD Operations ───────────────────────────────────

async def register_manual(
    filename: str,
    file_bytes: bytes,
    equipment_type: str = "industrial",
    model: Optional[str] = None,
    chunks_count: int = 0
) -> Tuple[bool, Dict[str, Any]]:
    """
    Compute MD5 hash and register a manual in PostgreSQL.
    If hash already exists, returns (False, existing_record) to skip duplicate ingestion.
    """
    file_hash = hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. Check duplicate by hash
            stmt = select(ManualRegistry).where(ManualRegistry.file_hash == file_hash)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                return False, existing.to_dict()

            # 2. Check duplicate by filename (update if re-uploaded with different hash)
            stmt_fn = select(ManualRegistry).where(ManualRegistry.filename == filename)
            existing_fn = (await session.execute(stmt_fn)).scalar_one_or_none()
            if existing_fn:
                existing_fn.file_hash = file_hash
                existing_fn.equipment_type = equipment_type
                existing_fn.model = model
                existing_fn.chunks_count = chunks_count
                existing_fn.created_at = datetime.now(timezone.utc)
                await session.commit()
                await session.refresh(existing_fn)
                return True, existing_fn.to_dict()

            # 3. Insert new registry entry
            new_entry = ManualRegistry(
                filename=filename,
                equipment_type=equipment_type,
                model=model,
                file_hash=file_hash,
                chunks_count=chunks_count
            )
            session.add(new_entry)
            await session.commit()
            await session.refresh(new_entry)
            return True, new_entry.to_dict()
    except Exception as e:
        logger.error(f"[PostgreSQL] register_manual failed: {e}")
        # Return fallback record
        return True, {
            "filename": filename,
            "equipment_type": equipment_type,
            "model": model,
            "file_hash": file_hash,
            "chunks_count": chunks_count,
            "fallback": True
        }


async def check_manual_duplicate_by_hash(file_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Check if file hash already exists in manual_registry."""
    file_hash = hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(ManualRegistry).where(ManualRegistry.file_hash == file_hash)
            record = (await session.execute(stmt)).scalar_one_or_none()
            return record.to_dict() if record else None
    except Exception as e:
        logger.warning(f"[PostgreSQL] check_manual_duplicate_by_hash fallback: {e}")
        return None


async def get_manual_by_filename(filename: str) -> Optional[Dict[str, Any]]:
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(ManualRegistry).where(ManualRegistry.filename == filename)
            record = (await session.execute(stmt)).scalar_one_or_none()
            return record.to_dict() if record else None
    except Exception as e:
        logger.warning(f"[PostgreSQL] get_manual_by_filename fallback: {e}")
        return None


async def list_registered_manuals() -> List[Dict[str, Any]]:
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(ManualRegistry).order_by(ManualRegistry.created_at.desc())
            records = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in records]
    except Exception as e:
        logger.warning(f"[PostgreSQL] list_registered_manuals fallback: {e}")
        return []


async def delete_registered_manual(filename: str) -> bool:
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = delete(ManualRegistry).where(ManualRegistry.filename == filename)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.warning(f"[PostgreSQL] delete_registered_manual fallback: {e}")
        return False


async def record_session_turn(
    session_id: str,
    sender: str,
    message_text: str,
    question: Optional[str] = None,
    action: Optional[str] = None,
    user_id: str = "default_user",
    equipment_model: Optional[str] = None,
    current_issue: Optional[str] = None,
    status: str = "ACTIVE",
    step_number: int = 0,
    language: str = "en"
) -> Dict[str, Any]:
    """
    Atomically ensures diagnostic_sessions row exists and appends a turn to session_turns.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. Fetch or create diagnostic_session
            stmt = select(DiagnosticSession).where(DiagnosticSession.session_id == session_id)
            sess = (await session.execute(stmt)).scalar_one_or_none()

            now = datetime.now(timezone.utc)
            if not sess:
                sess = DiagnosticSession(
                    session_id=session_id,
                    user_id=user_id,
                    equipment_model=equipment_model,
                    current_issue=current_issue or (message_text[:80] if sender == "user" else None),
                    status=status,
                    step_number=step_number,
                    language=language,
                    created_at=now,
                    updated_at=now
                )
                session.add(sess)
            else:
                sess.updated_at = now
                sess.status = status
                sess.step_number = step_number
                sess.language = language
                if equipment_model:
                    sess.equipment_model = equipment_model
                if current_issue:
                    sess.current_issue = current_issue

            # 2. Add turn
            turn = SessionTurn(
                session_id=session_id,
                sender=sender,
                message_text=message_text,
                question=question,
                action=action,
                created_at=now
            )
            session.add(turn)
            await session.commit()
            await session.refresh(turn)
            return turn.to_dict()
    except Exception as e:
        logger.warning(f"[PostgreSQL] record_session_turn fallback: {e}")
        return {
            "session_id": session_id,
            "sender": sender,
            "message_text": message_text,
            "question": question,
            "action": action,
            "fallback": True
        }


async def get_session_history(session_id: str) -> Dict[str, Any]:
    """Fetch complete session details and ordered turns from Postgres."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(DiagnosticSession).where(DiagnosticSession.session_id == session_id)
            sess = (await session.execute(stmt)).scalar_one_or_none()
            if not sess:
                return {}

            turns_stmt = select(SessionTurn).where(
                SessionTurn.session_id == session_id
            ).order_by(SessionTurn.created_at.asc())
            turns = (await session.execute(turns_stmt)).scalars().all()

            data = sess.to_dict()
            data["turns"] = [t.to_dict() for t in turns]
            data["messages"] = [
                {
                    "sender": t.sender,
                    "text": t.message_text,
                    "question": t.question,
                    "action": t.action,
                    "timestamp": t.created_at.isoformat() if t.created_at else None
                }
                for t in turns
            ]
            return data
    except Exception as e:
        logger.warning(f"[PostgreSQL] get_session_history fallback: {e}")
        return {}


async def get_audit_summary() -> Dict[str, Any]:
    """Provides high-level audit metrics for the Admin UI dashboard."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            total_sessions = (await session.execute(select(func.count(DiagnosticSession.session_id)))).scalar() or 0
            total_turns = (await session.execute(select(func.count(SessionTurn.id)))).scalar() or 0
            total_manuals = (await session.execute(select(func.count(ManualRegistry.id)))).scalar() or 0

            # Latest turns
            recent_turns_stmt = select(SessionTurn).order_by(SessionTurn.created_at.desc()).limit(10)
            recent_turns = (await session.execute(recent_turns_stmt)).scalars().all()

            return {
                "total_sessions": total_sessions,
                "total_turns": total_turns,
                "total_manuals": total_manuals,
                "recent_activity": [t.to_dict() for t in recent_turns]
            }
    except Exception as e:
        logger.warning(f"[PostgreSQL] get_audit_summary fallback: {e}")
        return {
            "total_sessions": 0,
            "total_turns": 0,
            "total_manuals": 0,
            "recent_activity": []
        }
