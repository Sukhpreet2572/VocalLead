param([switch]$Reload)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create backend/.venv and install requirements first. See docs/setup.md.' }
Push-Location $repoRoot
try {
    $apiHost = & $pythonPath -c "import sys; sys.path.insert(0, 'backend'); from app.core.config import Settings; print(Settings().api_host)"
    $apiPort = & $pythonPath -c "import sys; sys.path.insert(0, 'backend'); from app.core.config import Settings; print(Settings().api_port)"
    if ($LASTEXITCODE -ne 0) { throw 'Invalid backend configuration' }
    $uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', $apiHost, '--port', $apiPort, '--no-access-log')
    if ($Reload) { $uvicornArgs += @('--reload', '--reload-dir', 'backend') }
    & $pythonPath @uvicornArgs
} finally { Pop-Location }
