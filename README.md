# Semantic File Search for Windows

一个 Windows 桌面文件搜索原型：先扫描文件 metadata 和部分文件正文，使用文件名/路径/正文文本构建本地向量索引，再用 metadata filter + semantic search 查询文件。

## Features

- 扫描磁盘或指定文件夹
- 保存文件 metadata 到 SQLite
- 使用文件名、扩展名、父目录和可提取正文生成轻量 embedding
- 提取 `.pdf`、`.docx` 和常见纯文本文件内容参与查询
- 支持完整拼音和常见模糊拼音，不使用拼音首字母简写
- 首次启动自动构建索引，运行时定期后台同步文件变化
- 使用 NumPy 做 semantic search
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

## Build Windows installer

Modern Windows 10/11 build:

```powershell
.\build_windows_app.ps1
```

Legacy Windows 7 SP1/8 build:

```powershell
.\build_windows_legacy.ps1
```

The legacy build must be created with Python 3.8 x64. Python 3.9+ can produce
`api-ms-win-core-path-l1-1-0.dll` errors on Windows 7, even when packaged as an
installer. If a Windows 10/11 machine still fails to launch, install the
Microsoft Visual C++ 2015-2022 Redistributable x64.
