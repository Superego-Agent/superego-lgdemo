# src/metadata_manager.py
import aiosqlite
import os
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Constants ---
METADATA_DB_PATH = os.path.join(os.getenv("DATA_DIR", "data"), "threads_metadata.db")
# Defines the structure of the threads table
THREADS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS threads (
    thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
# Defines the structure of the runs table, linking runs to threads
RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_thread_id INTEGER NOT NULL,
    checkpoint_thread_id TEXT NOT NULL UNIQUE,
    final_checkpoint_id TEXT,
    constitution_ids_json TEXT NOT NULL,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    compare_group_id TEXT,
    FOREIGN KEY (parent_thread_id) REFERENCES threads (thread_id) ON DELETE CASCADE
);
"""
# SQL query to update the last_updated timestamp for a thread
UPDATE_THREAD_TIMESTAMP_SQL = """
UPDATE threads SET last_updated = CURRENT_TIMESTAMP WHERE thread_id = ?;
"""

# --- Database Initialization ---

async def init_db():
    """Initializes the metadata database, creating tables if they don't exist."""
    db_dir = os.path.dirname(METADATA_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        await db.execute(THREADS_TABLE_SQL)
        await db.execute(RUNS_TABLE_SQL)
        await db.commit()
    print(f"Metadata database initialized at {METADATA_DB_PATH}")

# --- Helper Functions ---

def _generate_default_thread_name(constitution_ids: List[str]) -> str:
    """Generates a default name for a new thread."""
    # Basic placeholder - could be replaced with random words etc.
    if not constitution_ids or constitution_ids == ["none"]:
        const_str = "Default"
    else:
        const_str = "+".join(sorted(list(set(constitution_ids) - {'none'}))) # Use '+' as separator
        if not const_str: const_str = "None" # Handle case where only 'none' was present

    # Simple name for now
    return f"Chat ({const_str})"

# --- Thread Operations ---

async def add_thread(name: str) -> int:
    """Adds a new thread to the database and returns its ID."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        cursor = await db.execute("INSERT INTO threads (name) VALUES (?)", (name,))
        await db.commit()
        return cursor.lastrowid

async def get_thread(thread_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves details for a specific thread."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def list_threads() -> List[Dict[str, Any]]:
    """Lists all threads, ordered by last updated time."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT thread_id, name, last_updated FROM threads ORDER BY last_updated DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def rename_thread(thread_id: int, new_name: str):
    """Renames a thread and updates its last_updated timestamp."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        await db.execute("UPDATE threads SET name = ?, last_updated = CURRENT_TIMESTAMP WHERE thread_id = ?", (new_name, thread_id))
        await db.commit()

async def delete_thread(thread_id: int):
    """Deletes a thread and all its associated runs (due to CASCADE)."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        await db.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
        await db.commit()

# --- Run Operations ---

async def add_run(parent_thread_id: int, checkpoint_thread_id: str, constitution_ids: List[str], compare_group_id: Optional[str] = None) -> int:
    """
    Adds a new run associated with a thread.
    Updates the parent thread's last_updated timestamp.
    """
    constitution_json = json.dumps(sorted(list(set(constitution_ids)))) # Store consistently
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO runs (parent_thread_id, checkpoint_thread_id, constitution_ids_json, compare_group_id)
            VALUES (?, ?, ?, ?)
            """,
            (parent_thread_id, checkpoint_thread_id, constitution_json, compare_group_id)
        )
        run_id = cursor.lastrowid
        # Update parent thread's timestamp
        await db.execute(UPDATE_THREAD_TIMESTAMP_SQL, (parent_thread_id,))
        await db.commit()
        return run_id

async def update_run_final_checkpoint(run_id: int, final_checkpoint_id: str):
    """Updates a run entry with the ID of its final LangGraph checkpoint."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        await db.execute(
            "UPDATE runs SET final_checkpoint_id = ? WHERE run_id = ?",
            (final_checkpoint_id, run_id)
        )
        await db.commit()

async def get_runs_for_thread(thread_id: int) -> List[Dict[str, Any]]:
    """Retrieves all runs associated with a specific thread, ordered by time."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_id, checkpoint_thread_id, final_checkpoint_id, constitution_ids_json, run_timestamp, compare_group_id
            FROM runs
            WHERE parent_thread_id = ?
            ORDER BY run_timestamp ASC
            """,
            (thread_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_latest_checkpoint_thread_id(thread_id: int) -> Optional[str]:
    """Gets the LangGraph checkpoint_thread_id of the most recent run for a given thread."""
    async with aiosqlite.connect(METADATA_DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT checkpoint_thread_id
            FROM runs
            WHERE parent_thread_id = ?
            ORDER BY run_timestamp DESC
            LIMIT 1
            """,
            (thread_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None