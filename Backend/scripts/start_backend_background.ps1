param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$backendDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$environmentFile = Join-Path $backendDirectory ".env"
$healthUrl = "http://127.0.0.1:$Port/api/v1/health"
$runtimeDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "abhyaas-backend"
$standardOutput = Join-Path $runtimeDirectory "backend.stdout.log"
$standardError = Join-Path $runtimeDirectory "backend.stderr.log"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment is missing. Run: python -m venv .venv"
}

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Backend\.env is missing. Run scripts\setup_local_postgres.ps1 first."
}

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.status -eq "ok") {
        Write-Host "Abhyaas backend is already running at http://127.0.0.1:$Port"
        exit 0
    }
}
catch {
    # No healthy Abhyaas process is currently responding on this port.
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port is already used by process $($listener[0].OwningProcess)."
}

New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
$arguments = @(
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1",
    "--port", $Port.ToString()
)

$process = Start-Process `
    -FilePath $python `
    -ArgumentList $arguments `
    -WorkingDirectory $backendDirectory `
    -WindowStyle Hidden `
    -RedirectStandardOutput $standardOutput `
    -RedirectStandardError $standardError `
    -PassThru

for ($attempt = 1; $attempt -le 20; $attempt += 1) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq "ok") {
            Write-Host "Abhyaas backend started in the background."
            Write-Host "API: http://127.0.0.1:$Port"
            Write-Host "Health: $healthUrl"
            Write-Host "Process ID: $($process.Id)"
            Write-Host "Logs: $runtimeDirectory"
            exit 0
        }
    }
    catch {
        # Give Uvicorn another moment to finish startup.
    }
}

if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
}
throw "Backend startup failed. Check $standardError"
