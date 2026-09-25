"""
migrate_postgres.py — Migration CLI and Data Sync utility for OCTO-RAG.
Applies schema to PostgreSQL and migrates legacy SQLite registry and in-memory session records.
Usage:
  python backend/scripts/migrate_postgres.py [--rollback] [--url <postgres_url>]
"""
import os
import sys
import argparse
import asyncio
import sqlite3
import hashlib
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import settings
from app.database.postgres import (
    Base,
    get_async_engine,
    get_session_factory,
    ManualRegistry,
    DiagnosticSession,
    SessionTurn,
    check_postgres_health
)
from sqlalchemy import text as sql_text


async def run_migration(rollback: bool = False, custom_url: str = None):
    if custom_url:
        settings.POSTGRES_URL = custom_url

    engine = get_async_engine()

    print("=" * 65)
    print("      OCTO-RAG POSTGRESQL MIGRATION & DATA SYNC UTILITY")
    print("=" * 65)
    print(f"Target Database URL: {settings.POSTGRES_URL.split('@')[-1]}")

    if rollback:
        print("\n[Rollback] Dropping tables: session_turns, diagnostic_sessions, manual_registry...")
        rollback_sql_path = Path(__file__).resolve().parent.parent / "migrations" / "001_rollback.sql"
        if rollback_sql_path.exists():
            sql = rollback_sql_path.read_text(encoding="utf-8")
            async with engine.begin() as conn:
                for statement in sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(sql_text(statement))
            print("[Rollback] Rollback completed successfully.")
        else:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            print("[Rollback] Tables dropped via SQLAlchemy metadata.")
        return

    # 1. Apply Schema
    print("\n[1/3] Verifying and applying PostgreSQL schema...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("  ✓ Schema tables verified (manual_registry, diagnostic_sessions, session_turns).")
    except Exception as e:
        print(f"  ✗ Schema creation failed: {e}")
        print("  Please verify your POSTGRES_URL credentials in backend/.env.")
        return

    # 2. Migrate SQLite File Registry
    print("\n[2/3] Checking SQLite registry.db for legacy manuals...")
    reg_db_path = settings.INPUT_DIR.parent / "registry.db"
    migrated_files = 0
    if reg_db_path.exists():
        try:
            conn = sqlite3.connect(str(reg_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT filepath, hash FROM registry")
            rows = cursor.fetchall()
            conn.close()

            session_factory = get_session_factory()
            async with session_factory() as session:
                for filepath, file_hash in rows:
                    filename = os.path.basename(filepath)
                    # Check if already present
                    check_stmt = sql_text("SELECT id FROM manual_registry WHERE filename = :fn")
                    res = await session.execute(check_stmt, {"fn": filename})
                    if res.scalar_one_or_none():
                        continue

                    # Determine equipment type heuristic
                    eq_type = "industrial"
                    lower_fn = filename.lower()
                    if any(term in lower_fn for term in ["cnc", "lathe", "milling", "spindle"]):
                        eq_type = "cnc_machine"
                    elif any(term in lower_fn for term in ["car", "toyota", "camry", "vehicle", "auto"]):
                        eq_type = "automotive"
                    elif any(term in lower_fn for term in ["fridge", "freezer", "cooler", "chiller"]):
                        eq_type = "appliance"

                    new_reg = ManualRegistry(
                        filename=filename,
                        equipment_type=eq_type,
                        model=None,
                        file_hash=file_hash,
                        chunks_count=0
                    )
                    session.add(new_reg)
                    migrated_files += 1

                await session.commit()
            print(f"  ✓ Migrated {migrated_files} manual record(s) from SQLite registry.db to PostgreSQL.")
        except Exception as e:
            print(f"  ! Warning during SQLite migration: {e}")
    else:
        print("  - No legacy SQLite registry.db found.")

    # 3. Synchronize Existing Raw Manuals
    print("\n[3/3] Scanning physical manuals in data_sandbox/input_manuals...")
    input_dir = Path(settings.INPUT_DIR)
    synced_physical = 0
    if input_dir.exists():
        session_factory = get_session_factory()
        async with session_factory() as session:
            for file_path in input_dir.iterdir():
                if file_path.is_file() and not file_path.name.startswith("."):
                    fn = file_path.name
                    # Check existing
                    check_stmt = sql_text("SELECT id FROM manual_registry WHERE filename = :fn")
                    res = await session.execute(check_stmt, {"fn": fn})
                    if not res.scalar_one_or_none():
                        content = file_path.read_bytes()
                        fhash = hashlib.md5(content, usedforsecurity=False).hexdigest()
                        eq_type = "industrial"
                        lower_fn = fn.lower()
                        if any(term in lower_fn for term in ["cnc", "lathe", "milling"]):
                            eq_type = "cnc_machine"
                        elif any(term in lower_fn for term in ["toyota", "car", "camry"]):
                            eq_type = "automotive"

                        session.add(ManualRegistry(
                            filename=fn,
                            equipment_type=eq_type,
                            model=None,
                            file_hash=fhash,
                            chunks_count=0
                        ))
                        synced_physical += 1
            await session.commit()
        print(f"  ✓ Registered {synced_physical} physical manual(s) into PostgreSQL.")

    # 4. Final Health Check
    healthy, status, stats = await check_postgres_health()
    print("\n" + "=" * 65)
    print(f"MIGRATION COMPLETE: Status = {status.upper()}")
    print(f"  • Registered Manuals : {stats.get('manuals_registered', 0)}")
    print(f"  • Diagnostic Sessions: {stats.get('sessions_stored', 0)}")
    print(f"  • Session Turns      : {stats.get('total_turns', 0)}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="OCTO-RAG PostgreSQL Migration CLI")
    parser.add_argument("--rollback", action="store_true", help="Drop all migration tables")
    parser.add_argument("--url", type=str, default=None, help="PostgreSQL connection string override")
    args = parser.parse_args()

    asyncio.run(run_migration(rollback=args.rollback, custom_url=args.url))


if __name__ == "__main__":
    main()
