$ErrorActionPreference = "Stop"

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python Launcher not found. Install Python 3.8 x64 from python.org and enable 'py launcher'."
}

py -3.8 -c "import platform, struct; assert struct.calcsize('P') == 8, 'Use Python 3.8 x64'; print(platform.python_version())"
py -3.8 -m venv .venv-win7
.\.venv-win7\Scripts\Activate.ps1
python -m pip install --upgrade "pip<25"
pip install -r requirements-legacy-win7.txt
pyinstaller --clean SemanticFileSearch.spec

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc /DMyAppOutputBaseFilename=SemanticFileSearchSetup-Win7 installer.iss
    Write-Host "Built legacy installer: installer\SemanticFileSearchSetup-Win7.exe"
} else {
    Write-Host "Inno Setup is not installed, skipped installer build."
    Write-Host "Built legacy portable app: dist\SemanticFileSearch\SemanticFileSearch.exe"
}
