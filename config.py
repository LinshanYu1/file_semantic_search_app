from pathlib import Path


APP_DIR = Path.home() / ".file_semantic_search"
DB_PATH = APP_DIR / "files.db"
VECTOR_PATH = APP_DIR / "file_vectors.npy"
IDS_PATH = APP_DIR / "vector_ids.npy"


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
