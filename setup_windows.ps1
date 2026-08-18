$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Python 3.11 or newer is required and was not found on PATH." }
$version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$version -lt [version]"3.11") { throw "Python 3.11+ is required; found $version." }

if (-not (Test-Path -LiteralPath ".venv")) { & python -m venv .venv }
$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e ".[dev]"

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env from .env.example (it was not overwritten)."
}
New-Item -ItemType Directory -Force -Path "data", "models", ".local" | Out-Null

Write-Host ""
Write-Host "Setup complete. Next steps:"
Write-Host "1. Edit .env and add your Azure endpoint, key, and deployment."
Write-Host "2. .\.venv\Scripts\Activate.ps1"
Write-Host "3. python -m meeting_assistant devices"
Write-Host "4. python -m meeting_assistant test-audio"
Write-Host "5. .\run.ps1"

