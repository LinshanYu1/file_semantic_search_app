from pathlib import Path


APP_DIR = Path.home() / ".file_semantic_search"
DB_PATH = APP_DIR / "files.db"
FAISS_PATH = APP_DIR / "files.faiss"
IDS_PATH = APP_DIR / "faiss_ids.npy"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_SKIP_DIR_NAMES = {
    "$recycle.bin",
    "appdata",
    "application data",
    "node_modules",
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "system volume information",
}
