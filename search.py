from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from config import IDS_PATH, VECTOR_PATH
from embedder import embed_texts
from text_utils import expand_text_for_search

from indexer import connect_db


_VECTORS: Optional[np.ndarray] = None
_IDS: Optional[np.ndarray] = None



@dataclass(frozen=True)
class SearchFilters:
    drive: Optional[str] = None
    extension: Optional[str] = None
    min_size_mb: Optional[float] = None
    max_size_mb: Optional[float] = None


def _where_clause(filters: SearchFilters) -> Tuple[str, List[object]]:
    clauses = []
    params: List[object] = []

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


def list_filter_options(conn: Optional[sqlite3.Connection] = None) -> Tuple[List[str], List[str]]:
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
    filters: Optional[SearchFilters] = None,
    limit: int = 50,
    semantic_pool: int = 1000,
) -> List[Dict]:
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

    if not VECTOR_PATH.exists() or not IDS_PATH.exists():
        conn.close()
        return [_drop_internal_id(item) for item in literal_results]

    vectors, ids = load_semantic_index()
    vector = embed_texts([expand_text_for_search(query)])
    scores = vectors.dot(vector[0])
    pool_size = min(semantic_pool, scores.shape[0])
    if pool_size <= 0:
        conn.close()
        return [_drop_internal_id(item) for item in literal_results]
    positions = np.argpartition(scores, -pool_size)[-pool_size:]
    positions = positions[np.argsort(scores[positions])[::-1]]

    semantic_hits = []
    for position in positions:
        if position < 0:
            continue
        semantic_hits.append((int(ids[position]), float(scores[position])))

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

    merged = literal_results + results
    merged.sort(key=lambda item: (item["score"], item["modified_ts"]), reverse=True)
    return [_drop_internal_id(item) for item in merged[:limit]]


def _literal_search(
    conn: sqlite3.Connection,
    query: str,
    where_sql: str,
    params: List[object],
    limit: int,
) -> List[Dict]:
    literal = query.strip().lower()
    terms = _query_terms(query)
    search_text_clauses = " OR ".join("LOWER(search_text) LIKE ? ESCAPE '\\'" for _ in terms)
    search_text_sql = f" OR {search_text_clauses}" if search_text_clauses else ""
    literal_pattern = _like_pattern(literal)
    term_patterns = [_like_pattern(term) for term in terms]
    filter_sql = f"AND {where_sql[6:]}" if where_sql else ""
    candidate_limit = max(limit * 20, 200)
    rows = conn.execute(
        f"""
        SELECT path, name, extension, drive, parent, size_bytes, modified_ts, id, content_text
        FROM files
        WHERE (
            LOWER(name) LIKE ? ESCAPE '\\'
            OR LOWER(path) LIKE ? ESCAPE '\\'
            OR LOWER(content_text) LIKE ? ESCAPE '\\'
            {search_text_sql}
        ) {filter_sql}
        ORDER BY
            CASE
                WHEN LOWER(name) = ? THEN 0
                WHEN LOWER(name) LIKE ? ESCAPE '\\' THEN 1
                WHEN LOWER(content_text) LIKE ? ESCAPE '\\' THEN 2
                WHEN LOWER(search_text) LIKE ? ESCAPE '\\' THEN 3
                ELSE 4
            END,
            modified_ts DESC
        LIMIT ?
        """,
        [
            literal_pattern,
            literal_pattern,
            literal_pattern,
            *term_patterns,
            *params,
            literal,
            literal_pattern,
            literal_pattern,
            literal_pattern,
            candidate_limit,
        ],
    ).fetchall()

    results = []
    for row in rows:
        score = _literal_score(row, literal, terms)
        item = _row_to_dict((*row[:7], score))
        item["id"] = int(row[7])
        results.append(item)
    results.sort(key=lambda item: (item["score"], item["modified_ts"]), reverse=True)
    return results[:limit]


def _literal_score(row: tuple, literal: str, terms: List[str]) -> float:
    path, name, extension, _drive, parent, _size_bytes, _modified_ts, _file_id, content_text = row
    name_text = expand_text_for_search(name).lower()
    stem_text = expand_text_for_search(name.rsplit(".", 1)[0]).lower()
    path_text = str(path).lower()
    parent_text = str(parent).lower()
    extension_text = str(extension).lower()
    content_text = str(content_text or "").lower()

    if literal and literal in {name_text, stem_text}:
        return 1.0

    extension_terms = [term for term in terms if _term_matches_extension(term, extension_text)]
    content_terms = [term for term in terms if term not in extension_terms]
    if not content_terms:
        content_terms = terms

    name_matches = _match_count(content_terms, name_text)
    content_matches = _match_count(content_terms, content_text)
    parent_matches = _match_count(content_terms, parent_text)
    path_matches = _match_count(content_terms, path_text)
    has_extension_match = bool(extension_terms)

    score = 0.0
    if literal and literal in name_text:
        score = 0.95
    elif content_terms and name_matches == len(content_terms):
        score = 0.9
    elif name_matches:
        score = 0.65 + 0.2 * (name_matches / len(content_terms))
    elif content_terms and content_matches == len(content_terms):
        score = 0.78
    elif content_matches:
        score = 0.55 + 0.15 * (content_matches / len(content_terms))
    elif content_terms and parent_matches == len(content_terms):
        score = 0.45
    elif parent_matches or path_matches:
        score = 0.3 + 0.15 * ((parent_matches or path_matches) / len(content_terms))
    elif literal and literal in path_text:
        score = 0.35

    if has_extension_match:
        if name_matches or (literal and literal in name_text):
            score += 0.08
        else:
            score += 0.04

    return min(score, 1.0)


def _match_count(terms: List[str], text: str) -> int:
    return sum(1 for term in terms if term and term in text)


def _term_matches_extension(term: str, extension: str) -> bool:
    normalized = term.lower().strip()
    if not normalized:
        return False
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized == extension


def _query_terms(query: str) -> List[str]:
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


def load_semantic_index() -> Tuple[np.ndarray, np.ndarray]:
    global _VECTORS, _IDS
    if _VECTORS is None:
        _VECTORS = np.load(VECTOR_PATH)
    if _IDS is None:
        _IDS = np.load(IDS_PATH)
    return _VECTORS, _IDS



def clear_semantic_cache() -> None:
    global _VECTORS, _IDS
    _VECTORS = None
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
