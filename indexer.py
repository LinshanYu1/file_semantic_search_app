from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Iterable

import faiss
import numpy as np
from embedder import embed_texts


from config import APP_DIR, DB_PATH, FAISS_PATH, IDS_PATH
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
    for path in (FAISS_PATH, IDS_PATH):
        if path.exists():
            path.unlink()
    return conn


def save_records(conn: sqlite3.Connection, records: Iterable[FileRecord]) -> list[int]:
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
    roots: list[str] | None = None,
    batch_size: int = 256,
    progress: ProgressCallback | None = None,
) -> int:
    conn = reset_storage()
    index = None
    all_ids: list[int] = []
    batch_records: list[FileRecord] = []
    total = 0

    def flush_batch() -> None:
        nonlocal index, total, batch_records
        if not batch_records:
            return

        ids = save_records(conn, batch_records)
        texts = [record.semantic_text for record in batch_records]
        vectors = embed_texts(texts)

        if index is None:
            index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
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

    if index is not None:
        faiss.write_index(index, str(FAISS_PATH))
        np.save(IDS_PATH, np.asarray(all_ids, dtype=np.int64))
    return total
