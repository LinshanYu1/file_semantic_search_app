```markdown
# Semantic File Search for Windows

一个 Windows 桌面文件搜索原型：先扫描文件 metadata，使用文件名/路径文本构建 FAISS 向量索引，再用 metadata filter + semantic search 查询文件。

## Features

- 扫描磁盘或指定文件夹
- 保存文件 metadata 到 SQLite
- 使用 `sentence-transformers/all-MiniLM-L6-v2` 对文件名、扩展名、父目录生成 embedding
- 使用 FAISS 做 semantic search
- 支持 metadata filters:
  - 磁盘位置
  - 文件类型
  - 文件大小范围
- 双击结果打开文件

## Run

```powershell
cd file_semantic_search_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

首次点击 `Scan / Rebuild index` 会下载 embedding model，并把索引保存到：

```text
%USERPROFILE%\.file_semantic_search
```

## Package as a Windows App

PyInstaller 不能在 macOS 上可靠地直接交叉打包 Windows app。推荐流程是：

1. 在 Mac 上写代码
2. 把代码 push 到 GitHub
3. 用 GitHub Actions 的 Windows runner 自动生成安装包

本项目已经包含 workflow：

```text
.github/workflows/windows-build.yml
```

在 GitHub 页面进入 `Actions` -> `Build Windows Installer` -> `Run workflow`，完成后下载 artifacts：

- `SemanticFileSearch-portable`: 免安装版本
- `SemanticFileSearch-installer`: Windows 安装器

## Package on a Windows Machine

如果你有 Windows 电脑或 Windows 虚拟机，也可以直接运行：

```powershell
cd file_semantic_search_app
.\build_windows_app.ps1
```

如果机器上安装了 Inno Setup，会生成：

```text
installer\SemanticFileSearchSetup.exe
```

否则会生成免安装程序：

```text
dist\SemanticFileSearch\SemanticFileSearch.exe
```

也可以手动运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pyinstaller --clean SemanticFileSearch.spec
```

然后用 Inno Setup 编译安装器：

```powershell
iscc installer.iss
```

## Design Notes

这个版本和你 NLP project 的 RAG 思路对应关系是：

- `build_rag.py` -> `indexer.py`
- `rag_retrival.py` -> `search.py`
- `app.py` Gradio UI -> `app.py` Tkinter desktop UI

文件检索里 metadata 数量会很大，所以 metadata 不建议只放在 LangChain docstore 里逐条 Python 过滤。这里用 SQLite 做 metadata filter，FAISS 做 semantic score，然后取交集。
```