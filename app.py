from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from indexer import build_index
from scanner import available_windows_drives
from search import SearchFilters, clear_semantic_cache, search_files


COMMON_FILE_TYPES = [
    "Any",
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".txt",
    ".csv",
    ".jpg",
    ".jpeg",
    ".png",
    ".zip",
    "Other",
]


class FileSearchApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Semantic File Search")
        self.geometry("1120x720")
        self.minsize(920, 560)

        self.selected_roots = available_windows_drives()
        self.drive_var = tk.StringVar(value="Any")
        self.extension_var = tk.StringVar(value="Any")
        self.custom_extension_var = tk.StringVar()
        self.min_size_var = tk.StringVar()
        self.max_size_var = tk.StringVar()
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self.refresh_filter_options()

    def _build_ui(self) -> None:
        controls = ttk.Frame(self, padding=12)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Name semantic query").grid(row=0, column=0, sticky="w")
        query_entry = ttk.Entry(controls, textvariable=self.query_var, width=44)
        query_entry.grid(row=1, column=0, padx=(0, 10), sticky="ew")
        query_entry.bind("<Return>", lambda _event: self.run_search())

        ttk.Label(controls, text="Disk location").grid(row=0, column=1, sticky="w")
        self.drive_combo = ttk.Combobox(controls, textvariable=self.drive_var, state="readonly", width=16)
        self.drive_combo.grid(row=1, column=1, padx=(0, 10), sticky="ew")

        ttk.Label(controls, text="File type").grid(row=0, column=2, sticky="w")
        self.extension_combo = ttk.Combobox(controls, textvariable=self.extension_var, state="readonly", width=16)
        self.extension_combo.grid(row=1, column=2, padx=(0, 10), sticky="ew")
        self.extension_combo.bind("<<ComboboxSelected>>", lambda _event: self.toggle_custom_extension())

        ttk.Label(controls, text="Other type").grid(row=0, column=3, sticky="w")
        self.custom_extension_entry = ttk.Entry(controls, textvariable=self.custom_extension_var, width=10, state="disabled")
        self.custom_extension_entry.grid(row=1, column=3, padx=(0, 10))

        ttk.Label(controls, text="Min MB").grid(row=0, column=4, sticky="w")
        ttk.Entry(controls, textvariable=self.min_size_var, width=10).grid(row=1, column=4, padx=(0, 10))

        ttk.Label(controls, text="Max MB").grid(row=0, column=5, sticky="w")
        ttk.Entry(controls, textvariable=self.max_size_var, width=10).grid(row=1, column=5, padx=(0, 10))

        ttk.Button(controls, text="Search", command=self.run_search).grid(row=1, column=6, padx=(0, 8))
        ttk.Button(controls, text="Choose folders", command=self.choose_roots).grid(row=1, column=7, padx=(0, 8))
        ttk.Button(controls, text="Scan / Rebuild index", command=self.start_indexing).grid(row=1, column=8)

        controls.columnconfigure(0, weight=1)

        columns = ("name", "extension", "drive", "size_mb", "score", "path")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("name", text="Name")
        self.tree.heading("extension", text="Type")
        self.tree.heading("drive", text="Disk")
        self.tree.heading("size_mb", text="Size MB")
        self.tree.heading("score", text="Score")
        self.tree.heading("path", text="Path")
        self.tree.column("name", width=230)
        self.tree.column("extension", width=80)
        self.tree.column("drive", width=80)
        self.tree.column("size_mb", width=90, anchor=tk.E)
        self.tree.column("score", width=80, anchor=tk.E)
        self.tree.column("path", width=560)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.tree.bind("<Double-1>", self.open_selected_file)

        status = ttk.Label(self, textvariable=self.status_var, padding=(12, 4))
        status.pack(fill=tk.X)

    def refresh_filter_options(self) -> None:
        drives = [self.normalize_drive_filter(drive) for drive in available_windows_drives()]

        self.drive_combo["values"] = ["Any", *drives]
        self.extension_combo["values"] = COMMON_FILE_TYPES
        if self.drive_var.get() not in self.drive_combo["values"]:
            self.drive_var.set("Any")
        if self.extension_var.get() not in self.extension_combo["values"]:
            self.extension_var.set("Any")
        self.toggle_custom_extension()

    def toggle_custom_extension(self) -> None:
        if self.extension_var.get() == "Other":
            self.custom_extension_entry.configure(state="normal")
            self.custom_extension_entry.focus_set()
        else:
            self.custom_extension_var.set("")
            self.custom_extension_entry.configure(state="disabled")

    def choose_roots(self) -> None:
        folder = filedialog.askdirectory(title="Choose a folder to scan")
        if folder:
            self.selected_roots = [folder]
            self.status_var.set(f"Selected scan root: {folder}")

    def start_indexing(self) -> None:
        self.status_var.set("Scanning files and building FAISS index...")
        thread = threading.Thread(target=self._index_worker, daemon=True)
        thread.start()

    def _index_worker(self) -> None:
        def progress(count: int, path: str) -> None:
            self.after(0, lambda: self.status_var.set(f"Indexed {count} files: {path}"))

        try:
            total = build_index(roots=self.selected_roots, progress=progress)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Indexing failed", str(exc)))
            self.after(0, lambda: self.status_var.set("Indexing failed"))
            return

        clear_semantic_cache()
        self.after(0, self.refresh_filter_options)
        self.after(0, lambda: self.status_var.set(f"Index ready: {total} files"))

    def run_search(self) -> None:
        try:
            min_size = self._parse_optional_float(self.min_size_var.get())
            max_size = self._parse_optional_float(self.max_size_var.get())
        except ValueError:
            messagebox.showerror("Invalid filter", "Size filters must be numbers.")
            return

        extension = self.get_selected_extension()
        if extension == "INVALID":
            messagebox.showerror("Invalid filter", "Other file type should look like .md or .json.")
            return

        filters = SearchFilters(
            drive=None if self.drive_var.get() == "Any" else self.normalize_drive_filter(self.drive_var.get()),
            extension=extension,
            min_size_mb=min_size,
            max_size_mb=max_size,
        )

        self.status_var.set("Searching...")
        self.update_idletasks()

        try:
            results = search_files(self.query_var.get(), filters=filters, limit=100)
        except Exception as exc:
            messagebox.showerror("Search failed", str(exc))
            self.status_var.set("Search failed")
            return

        self.tree.delete(*self.tree.get_children())
        for item in results:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    item["name"],
                    item["extension"],
                    item["drive"],
                    item["size_mb"],
                    item["score"],
                    item["path"],
                ),
            )
        if results:
            self.status_var.set(f"{len(results)} results")
        else:
            self.status_var.set("0 results. If this is the first run, choose a folder and click Scan / Rebuild index.")

    def open_selected_file(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        path = self.tree.item(selected[0], "values")[-1]
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", path])
            else:
                os.startfile(path)
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    @staticmethod
    def _parse_optional_float(value: str) -> float | None:
        value = value.strip()
        if not value:
            return None
        return float(value)

    def get_selected_extension(self) -> str | None:
        selected = self.extension_var.get()
        if selected == "Any":
            return None
        if selected != "Other":
            return selected

        custom = self.custom_extension_var.get().strip().lower()
        if not custom:
            return None
        if not custom.startswith(".") or len(custom) < 2:
            return "INVALID"
        return custom

    @staticmethod
    def normalize_drive_filter(value: str) -> str:
        return value.rstrip("\\/")


if __name__ == "__main__":
    FileSearchApp().mainloop()
