param(
    [switch]$NoReload,
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$backendDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment is missing. Run: python -m venv .venv"
}

if (-not (Test-Path -LiteralPath (Join-Path $backendDirectory ".env"))) {
    throw "Backend\.env is missing. Run scripts\setup_local_postgres.ps1 first."
}

Push-Location $backendDirectory
try {
    $uvicornArguments = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $Port.ToString())
    if (-not $NoReload) {
        $uvicornArguments += "--reload"
    }
    & $python @uvicornArguments
}
finally {
    Pop-Location
}
