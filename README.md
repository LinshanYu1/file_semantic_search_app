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
