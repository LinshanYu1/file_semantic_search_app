from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Iterable, List, Optional

import numpy as np
from embedder import embed_texts


from config import APP_DIR, DB_PATH, IDS_PATH, VECTOR_PATH
from scanner import FileRecord, iter_files


ProgressCallback = Callable[[int, str], None]


def connect_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            extension TEXT NOT NULL,
            drive TEXT NOT NULL,
            parent TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            modified_ts REAL NOT NULL,
            search_text TEXT NOT NULL DEFAULT ''
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    if "search_text" not in columns:
        conn.execute("ALTER TABLE files ADD COLUMN search_text TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_drive ON files(drive)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size_bytes)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_search_text ON files(search_text)")
    return conn


def reset_storage() -> sqlite3.Connection:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_db()
    conn.execute("DELETE FROM files")
    conn.commit()
    for path in (APP_DIR / "files.faiss", APP_DIR / "faiss_ids.npy", VECTOR_PATH, IDS_PATH):
        if path.exists():
            path.unlink()
    return conn


def save_records(conn: sqlite3.Connection, records: Iterable[FileRecord]) -> List[int]:
    ids = []
    for record in records:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO files
            (path, name, extension, drive, parent, size_bytes, modified_ts, search_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.path,
                record.name,
                record.extension,
                record.drive,
                record.parent,
                record.size_bytes,
                record.modified_ts,
                record.search_text.lower(),
            ),
        )
        ids.append(int(cursor.lastrowid))
    return ids


def build_index(
    roots: Optional[List[str]] = None,
    batch_size: int = 256,
    progress: Optional[ProgressCallback] = None,
) -> int:
    conn = reset_storage()
    all_ids: List[int] = []
    all_vectors: List[np.ndarray] = []
    batch_records: List[FileRecord] = []
    total = 0

    def flush_batch() -> None:
        nonlocal total, batch_records
        if not batch_records:
            return

        ids = save_records(conn, batch_records)
        texts = [record.semantic_text for record in batch_records]
        vectors = embed_texts(texts)

        all_vectors.append(vectors)
        all_ids.extend(ids)
        total += len(batch_records)

        if progress:
            progress(total, batch_records[-1].path)
        batch_records = []

    for record in iter_files(roots=roots):
        batch_records.append(record)
        if len(batch_records) >= batch_size:
            flush_batch()
            conn.commit()

    flush_batch()
    conn.commit()
    conn.close()

    if all_vectors:
        np.save(VECTOR_PATH, np.vstack(all_vectors).astype("float32"))
        np.save(IDS_PATH, np.asarray(all_ids, dtype=np.int64))
    return total
