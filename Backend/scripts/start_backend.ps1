param(
    [switch]$NoReload,
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$backendDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$healthUrl = "http://127.0.0.1:$Port/api/v1/health"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment is missing. Run: python -m venv .venv"
}

if (-not (Test-Path -LiteralPath (Join-Path $backendDirectory ".env"))) {
    throw "Backend\.env is missing. Run scripts\setup_local_postgres.ps1 first."
}

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.status -eq "ok") {
        Write-Host "Abhyaas backend is already running at http://127.0.0.1:$Port"
        Write-Host "Health: $healthUrl"
        exit 0
    }
}
catch {
    # Nothing healthy is responding, so continue with normal startup checks.
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already being used by process $($listener[0].OwningProcess). Close that process or start Abhyaas on another port."
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
