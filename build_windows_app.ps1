$ErrorActionPreference = "Stop"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --clean SemanticFileSearch.spec

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc installer.iss
    Write-Host "Built installer: installer\SemanticFileSearchSetup.exe"
} else {
    Write-Host "Inno Setup is not installed, skipped installer build."
    Write-Host "Built portable app: dist\SemanticFileSearch\SemanticFileSearch.exe"
}
