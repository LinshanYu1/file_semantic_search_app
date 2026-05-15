from __future__ import annotations

from pathlib import Path
from typing import List


MAX_TEXT_CHARS = 200_000
MAX_TEXT_BYTES = 512_000
MAX_PDF_PAGES = 20

PLAIN_TEXT_EXTENSIONS = {
    ".txt",
    ".csv",
    ".md",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".css",
    ".ini",
    ".yaml",
    ".yml",
}


def extract_file_text(path: str, extension: str) -> str:
    extension = extension.lower()
    try:
        if extension in PLAIN_TEXT_EXTENSIONS:
            return _extract_plain_text(path)
        if extension == ".pdf":
            return _extract_pdf_text(path)
        if extension == ".docx":
            return _extract_docx_text(path)
    except Exception:
        return ""
    return ""


def _extract_plain_text(path: str) -> str:
    data = Path(path).read_bytes()[:MAX_TEXT_BYTES]
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return _limit_text(data.decode(encoding, errors="ignore"))
        except Exception:
            continue
    return ""


def _extract_pdf_text(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    parts: List[str] = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        text = page.extract_text() or ""
        if text:
            parts.append(text)
        if sum(len(part) for part in parts) >= MAX_TEXT_CHARS:
            break
    return _limit_text("\n".join(parts))


def _extract_docx_text(path: str) -> str:
    from docx import Document

    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    return _limit_text("\n".join(parts))


def _limit_text(text: str) -> str:
    return " ".join(str(text or "").split())[:MAX_TEXT_CHARS]
