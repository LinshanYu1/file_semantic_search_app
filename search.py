from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import faiss
import numpy as np
from config import FAISS_PATH, IDS_PATH
from embedder import embed_texts
from text_utils import expand_text_for_search

from indexer import connect_db


_INDEX: faiss.Index | None = None
_IDS: np.ndarray | None = None



@dataclass(frozen=True)
class SearchFilters:
    drive: str | None = None
    extension: str | None = None
    min_size_mb: float | None = None
    max_size_mb: float | None = None


def _where_clause(filters: SearchFilters) -> tuple[str, list[object]]:
    clauses = []
    params: list[object] = []

    if filters.drive:
        clauses.append("drive = ?")
        params.append(filters.drive)
    if filters.extension:
        clauses.append("extension = ?")
        params.append(filters.extension)
    if filters.min_size_mb is not None:
        clauses.append("size_bytes >= ?")
        params.append(int(filters.min_size_mb * 1024 * 1024))
    if filters.max_size_mb is not None:
        clauses.append("size_bytes <= ?")
        params.append(int(filters.max_size_mb * 1024 * 1024))

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def list_filter_options(conn: sqlite3.Connection | None = None) -> tuple[list[str], list[str]]:
    own_conn = conn is None
    conn = conn or connect_db()
    drives = [row[0] for row in conn.execute("SELECT DISTINCT drive FROM files ORDER BY drive")]
    extensions = [
        row[0] for row in conn.execute(
            "SELECT DISTINCT extension FROM files WHERE extension != '' ORDER BY extension"
        )
    ]
    if own_conn:
        conn.close()
    return drives, extensions


def search_files(
    query: str = "",
    filters: SearchFilters | None = None,
    limit: int = 50,
    semantic_pool: int = 1000,
) -> list[dict]:
    filters = filters or SearchFilters()
    conn = connect_db()
    where_sql, params = _where_clause(filters)

    if not query.strip():
        rows = conn.execute(
            f"""
            SELECT path, name, extension, drive, parent, size_bytes, modified_ts, 0.0 AS score
            FROM files
            {where_sql}
            ORDER BY modified_ts DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        conn.close()
        return [_row_to_dict(row) for row in rows]

    literal_results = _literal_search(conn, query, where_sql, params, limit)

    if not FAISS_PATH.exists() or not IDS_PATH.exists():
        conn.close()
        return [_drop_internal_id(item) for item in literal_results]

    index, ids = load_semantic_index()
    vector = embed_texts([expand_text_for_search(query)])
    scores, positions = index.search(vector, min(semantic_pool, index.ntotal))

    semantic_hits = []
    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue
        semantic_hits.append((int(ids[position]), float(score)))

    if not semantic_hits:
        conn.close()
        return [_drop_internal_id(item) for item in literal_results]

    score_by_id = dict(semantic_hits)
    placeholders = ",".join("?" for _ in semantic_hits)
    id_params = [file_id for file_id, _ in semantic_hits]
    filter_sql = f"AND {where_sql[6:]}" if where_sql else ""
    rows = conn.execute(
        f"""
        SELECT path, name, extension, drive, parent, size_bytes, modified_ts, id
        FROM files
        WHERE id IN ({placeholders}) {filter_sql}
        """,
        [*id_params, *params],
    ).fetchall()
    conn.close()

    literal_ids = {item["id"] for item in literal_results}
    results = []
    for row in rows:
        if row[-1] in literal_ids:
            continue
        score = score_by_id.get(int(row[-1]), 0.0)
        item = _row_to_dict((*row[:-1], score))
        results.append(item)

    merged = literal_results + sorted(results, key=lambda item: item["score"], reverse=True)
    return [_drop_internal_id(item) for item in merged[:limit]]


def _literal_search(
    conn: sqlite3.Connection,
    query: str,
    where_sql: str,
    params: list[object],
    limit: int,
) -> list[dict]:
    literal = query.strip().lower()
    terms = _query_terms(query)
    search_text_clauses = " OR ".join("LOWER(search_text) LIKE ? ESCAPE '\\'" for _ in terms)
    search_text_sql = f" OR {search_text_clauses}" if search_text_clauses else ""
    literal_pattern = _like_pattern(literal)
    term_patterns = [_like_pattern(term) for term in terms]
    filter_sql = f"AND {where_sql[6:]}" if where_sql else ""
    rows = conn.execute(
        f"""
        SELECT path, name, extension, drive, parent, size_bytes, modified_ts, id
        FROM files
        WHERE (
            LOWER(name) LIKE ? ESCAPE '\\'
            OR LOWER(path) LIKE ? ESCAPE '\\'
            {search_text_sql}
        ) {filter_sql}
        ORDER BY
            CASE
                WHEN LOWER(name) = ? THEN 0
                WHEN LOWER(name) LIKE ? ESCAPE '\\' THEN 1
                WHEN LOWER(search_text) LIKE ? ESCAPE '\\' THEN 2
                ELSE 3
            END,
            modified_ts DESC
        LIMIT ?
        """,
        [literal_pattern, literal_pattern, *term_patterns, *params, literal, literal_pattern, literal_pattern, limit],
    ).fetchall()

    results = []
    for row in rows:
        item = _row_to_dict((*row[:-1], 1.0))
        item["id"] = int(row[-1])
        results.append(item)
    return results


def _query_terms(query: str) -> list[str]:
    expanded = expand_text_for_search(query).lower()
    raw_terms = [query.strip().lower(), *expanded.split()]
    terms = []
    seen = set()
    for term in raw_terms:
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms[:12]


def _like_pattern(value: str) -> str:
    escaped = (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def load_semantic_index() -> tuple[faiss.Index, np.ndarray]:
    global _INDEX, _IDS
    if _INDEX is None:
        _INDEX = faiss.read_index(str(FAISS_PATH))
    if _IDS is None:
        _IDS = np.load(IDS_PATH)
    return _INDEX, _IDS



def clear_semantic_cache() -> None:
    global _INDEX, _IDS
    _INDEX = None
    _IDS = None


def _row_to_dict(row: tuple) -> dict:
    path, name, extension, drive, parent, size_bytes, modified_ts, score = row
    return {
        "path": path,
        "name": name,
        "extension": extension,
        "drive": drive,
        "parent": parent,
        "size_mb": round(size_bytes / 1024 / 1024, 2),
        "modified_ts": modified_ts,
        "score": round(float(score), 4),
    }


def _drop_internal_id(item: dict) -> dict:
    item = dict(item)
    item.pop("id", None)
    return item
