$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"

Set-Location $backendDir

if (Test-Path $venvActivate) {
    . $venvActivate
} else {
    Write-Warning "Virtual environment not found at $venvActivate — run setup steps in README first."
}

$python = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
    $uvicornArgs = @("-3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload")
} else {
    $uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload")
}

& $python @uvicornArgs
