$ErrorActionPreference = "Stop"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment not found. Run .\setup_windows.ps1 first."
}
& $venvPython -m meeting_assistant start @args

