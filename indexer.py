from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

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
            content_text TEXT NOT NULL DEFAULT '',
            search_text TEXT NOT NULL DEFAULT ''
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    if "content_text" not in columns:
        conn.execute("ALTER TABLE files ADD COLUMN content_text TEXT NOT NULL DEFAULT ''")
    if "search_text" not in columns:
        conn.execute("ALTER TABLE files ADD COLUMN search_text TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_drive ON files(drive)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size_bytes)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_search_text ON files(search_text)")
    return conn


def has_index() -> bool:
    conn = connect_db()
    count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    conn.close()
    return bool(count and VECTOR_PATH.exists() and IDS_PATH.exists())


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
            (path, name, extension, drive, parent, size_bytes, modified_ts, content_text, search_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.path,
                record.name,
                record.extension,
                record.drive,
                record.parent,
                record.size_bytes,
                record.modified_ts,
                record.content_text.lower(),
                record.search_text.lower(),
            ),
        )
        ids.append(int(cursor.lastrowid))
    return ids


def sync_index(
    roots: Optional[List[str]] = None,
    batch_size: int = 256,
    progress: Optional[ProgressCallback] = None,
) -> int:
    conn = connect_db()
    existing = _existing_records(conn)
    seen_paths: Set[str] = set()
    changed_records: List[FileRecord] = []
    scanned = 0

    def flush_changed() -> None:
        nonlocal changed_records
        if not changed_records:
            return
        save_records(conn, (record.with_content() for record in changed_records))
        conn.commit()
        changed_records = []

    for record in iter_files(roots=roots, extract_content=False):
        scanned += 1
        seen_paths.add(record.path)
        current_signature = (record.size_bytes, record.modified_ts)
        if existing.get(record.path) != current_signature:
            changed_records.append(record)
        if len(changed_records) >= batch_size:
            flush_changed()
        if progress and scanned % batch_size == 0:
            progress(scanned, record.path)

    flush_changed()
    stale_paths = [path for path in existing if path not in seen_paths and _path_in_roots(path, roots)]
    for path in stale_paths:
        conn.execute("DELETE FROM files WHERE path = ?", (path,))
    conn.commit()

    _rebuild_vectors_from_db(conn)
    conn.close()
    return scanned


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


def _existing_records(conn: sqlite3.Connection) -> Dict[str, Tuple[int, float]]:
    return {
        row[0]: (int(row[1]), float(row[2]))
        for row in conn.execute("SELECT path, size_bytes, modified_ts FROM files")
    }


def _path_in_roots(path: str, roots: Optional[List[str]]) -> bool:
    if not roots:
        return True
    normalized_path = os_path_norm(path)
    return any(
        normalized_path == os_path_norm(root) or normalized_path.startswith(os_path_norm(root) + "\\")
        for root in roots
    )


def os_path_norm(path: str) -> str:
    return str(Path(path)).rstrip("\\/").lower()


def _rebuild_vectors_from_db(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, search_text FROM files ORDER BY id").fetchall()
    if not rows:
        for path in (VECTOR_PATH, IDS_PATH):
            if path.exists():
                path.unlink()
        return

    ids = np.asarray([int(row[0]) for row in rows], dtype=np.int64)
    vectors = embed_texts([row[1] for row in rows]).astype("float32")
    np.save(VECTOR_PATH, vectors)
    np.save(IDS_PATH, ids)
