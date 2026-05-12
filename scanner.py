from __future__ import annotations

import os
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from config import DEFAULT_SKIP_DIR_NAMES


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    extension: str
    drive: str
    parent: str
    size_bytes: int
    modified_ts: float

    @property
    def semantic_text(self) -> str:
        stem = Path(self.name).stem.replace("_", " ").replace("-", " ")
        return f"{stem} {self.extension} {self.parent}"


def available_windows_drives() -> list[str]:
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives or [str(Path.home())]


def should_skip_dir(path: str, skip_dir_names: set[str] | None = None) -> bool:
    skip_dir_names = skip_dir_names or DEFAULT_SKIP_DIR_NAMES
    name = os.path.basename(path).lower()
    return name in skip_dir_names


def iter_files(
    roots: Iterable[str] | None = None,
    skip_dir_names: set[str] | None = None,
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
                yield FileRecord(
                    path=path,
                    name=filename,
                    extension=extension,
                    drive=drive,
                    parent=dirpath,
                    size_bytes=int(stat.st_size),
                    modified_ts=float(stat.st_mtime),
                )
