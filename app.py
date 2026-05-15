from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

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
        self.title("文件快速搜索")
        self.geometry("1280x760")
        self.minsize(1040, 600)

        self.selected_roots = available_windows_drives()
        self.drive_var = tk.StringVar(value="Any")
        self.extension_var = tk.StringVar(value="Any")
        self.custom_extension_var = tk.StringVar()
        self.min_size_var = tk.StringVar()
        self.max_size_var = tk.StringVar()
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")

        self._build_ui()
        self.refresh_filter_options()

    def _build_ui(self) -> None:
        controls = ttk.Frame(self, padding=12)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="文件名称 / 拼音 / 关键词").grid(row=0, column=0, columnspan=9, sticky="w")
        query_entry = ttk.Entry(controls, textvariable=self.query_var)
        query_entry.grid(row=1, column=0, columnspan=9, padx=(0, 0), pady=(0, 10), sticky="ew")
        query_entry.bind("<Return>", lambda _event: self.run_search())

        ttk.Label(controls, text="磁盘位置").grid(row=2, column=0, sticky="w")
        self.drive_combo = ttk.Combobox(controls, textvariable=self.drive_var, state="readonly", width=16)
        self.drive_combo.grid(row=3, column=0, padx=(0, 10), sticky="ew")

        ttk.Label(controls, text="文件类型").grid(row=2, column=1, sticky="w")
        self.extension_combo = ttk.Combobox(controls, textvariable=self.extension_var, state="readonly", width=16)
        self.extension_combo.grid(row=3, column=1, padx=(0, 10), sticky="ew")
        self.extension_combo.bind("<<ComboboxSelected>>", lambda _event: self.toggle_custom_extension())

        ttk.Label(controls, text="其他类型").grid(row=2, column=2, sticky="w")
        self.custom_extension_entry = ttk.Entry(controls, textvariable=self.custom_extension_var, width=10, state="disabled")
        self.custom_extension_entry.grid(row=3, column=2, padx=(0, 10), sticky="ew")

        ttk.Label(controls, text="最小 MB").grid(row=2, column=3, sticky="w")
        ttk.Entry(controls, textvariable=self.min_size_var, width=10).grid(row=3, column=3, padx=(0, 10), sticky="ew")

        ttk.Label(controls, text="最大 MB").grid(row=2, column=4, sticky="w")
        ttk.Entry(controls, textvariable=self.max_size_var, width=10).grid(row=3, column=4, padx=(0, 10), sticky="ew")

        ttk.Button(controls, text="搜索", command=self.run_search).grid(row=3, column=5, padx=(0, 8), sticky="ew")
        ttk.Button(controls, text="选择文件夹", command=self.choose_roots).grid(row=3, column=6, padx=(0, 8), sticky="ew")
        ttk.Button(controls, text="扫描 / 重建索引", command=self.start_indexing).grid(row=3, column=7, columnspan=2, sticky="ew")

        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(8, weight=1)

        columns = ("name", "extension", "drive", "size_mb", "score", "path")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("name", text="文件名")
        self.tree.heading("extension", text="类型")
        self.tree.heading("drive", text="磁盘")
        self.tree.heading("size_mb", text="大小 MB")
        self.tree.heading("score", text="匹配度")
        self.tree.heading("path", text="路径")
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
        folder = filedialog.askdirectory(title="选择需要扫描的文件夹")
        if folder:
            self.selected_roots = [folder]
            self.status_var.set(f"已选择扫描目录：{folder}")

    def start_indexing(self) -> None:
        self.status_var.set("正在扫描文件并重建索引...")
        thread = threading.Thread(target=self._index_worker, daemon=True)
        thread.start()

    def _index_worker(self) -> None:
        def progress(count: int, path: str) -> None:
            self.after(0, lambda: self.status_var.set(f"已索引 {count} 个文件：{path}"))

        try:
            total = build_index(roots=self.selected_roots, progress=progress)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("索引失败", str(exc)))
            self.after(0, lambda: self.status_var.set("索引失败"))
            return

        clear_semantic_cache()
        self.after(0, self.refresh_filter_options)
        self.after(0, lambda: self.status_var.set(f"索引完成：{total} 个文件"))

    def run_search(self) -> None:
        try:
            min_size = self._parse_optional_float(self.min_size_var.get())
            max_size = self._parse_optional_float(self.max_size_var.get())
        except ValueError:
            messagebox.showerror("筛选条件错误", "文件大小必须是数字。")
            return

        extension = self.get_selected_extension()
        if extension == "INVALID":
            messagebox.showerror("筛选条件错误", "其他文件类型请填写类似 .md 或 .json 的格式。")
            return

        filters = SearchFilters(
            drive=None if self.drive_var.get() == "Any" else self.normalize_drive_filter(self.drive_var.get()),
            extension=extension,
            min_size_mb=min_size,
            max_size_mb=max_size,
        )

        self.status_var.set("正在搜索...")
        self.update_idletasks()

        try:
            results = search_files(self.query_var.get(), filters=filters, limit=100)
        except Exception as exc:
            messagebox.showerror("搜索失败", str(exc))
            self.status_var.set("搜索失败")
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
            self.status_var.set(f"找到 {len(results)} 条结果")
        else:
            self.status_var.set("没有结果。首次使用请先选择文件夹并点击“扫描 / 重建索引”。")

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
            messagebox.showerror("打开位置失败", str(exc))

    @staticmethod
    def _parse_optional_float(value: str) -> Optional[float]:
        value = value.strip()
        if not value:
            return None
        return float(value)

    def get_selected_extension(self) -> Optional[str]:
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
