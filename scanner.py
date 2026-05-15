from __future__ import annotations

import os
import string
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Set

from config import DEFAULT_SKIP_DIR_NAMES
from content_extractor import extract_file_text
from text_utils import expand_text_for_search


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    extension: str
    drive: str
    parent: str
    size_bytes: int
    modified_ts: float
    content_text: str = ""

    @property
    def semantic_text(self) -> str:
        stem = Path(self.name).stem.replace("_", " ").replace("-", " ")
        return expand_text_for_search(f"{stem} {self.extension} {self.parent} {self.content_text}")

    @property
    def search_text(self) -> str:
        return expand_text_for_search(f"{self.name} {self.extension} {self.parent} {self.content_text}")

    def with_content(self) -> "FileRecord":
        if self.content_text:
            return self
        return replace(self, content_text=extract_file_text(self.path, self.extension))


def available_windows_drives() -> List[str]:
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives or [str(Path.home())]


def should_skip_dir(path: str, skip_dir_names: Optional[Set[str]] = None) -> bool:
    skip_dir_names = skip_dir_names or DEFAULT_SKIP_DIR_NAMES
    name = os.path.basename(path).lower()
    return name in skip_dir_names


def iter_files(
    roots: Optional[Iterable[str]] = None,
    skip_dir_names: Optional[Set[str]] = None,
    extract_content: bool = True,
) -> Iterator[FileRecord]:
    roots = list(roots or available_windows_drives())
    skip_dir_names = skip_dir_names or DEFAULT_SKIP_DIR_NAMES

    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [
                dirname for dirname in dirnames
                if not should_skip_dir(os.path.join(dirpath, dirname), skip_dir_names)
            ]

            for filename in filenames:
                path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue

                drive = os.path.splitdrive(path)[0] or Path(path).anchor
                extension = Path(filename).suffix.lower()
                content_text = extract_file_text(path, extension) if extract_content else ""
                yield FileRecord(
                    path=path,
                    name=filename,
                    extension=extension,
                    drive=drive,
                    parent=dirpath,
                    size_bytes=int(stat.st_size),
                    modified_ts=float(stat.st_mtime),
                    content_text=content_text,
                )
