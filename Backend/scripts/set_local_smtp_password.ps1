param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$backendDirectory = Split-Path -Parent $PSScriptRoot
$environmentFile = Join-Path $backendDirectory ".env"
$startScript = Join-Path $PSScriptRoot "start_backend_background.ps1"

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Backend\.env is missing. Run scripts\setup_local_postgres.ps1 first."
}

$securePassword = Read-Host "Paste the 16-character Google App Password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $appPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $appPassword = $appPassword -replace "\s", ""

    if ($appPassword.Length -ne 16) {
        throw "The Google App Password must contain exactly 16 characters (spaces are ignored)."
    }

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.AddRange([string[]][System.IO.File]::ReadAllLines($environmentFile))
    $passwordWasUpdated = $false

    for ($index = 0; $index -lt $lines.Count; $index += 1) {
        if ($lines[$index] -match "^SMTP_PASSWORD=") {
            $lines[$index] = "SMTP_PASSWORD=$appPassword"
            $passwordWasUpdated = $true
            break
        }
    }

    if (-not $passwordWasUpdated) {
        $lines.Add("SMTP_PASSWORD=$appPassword")
    }

    [System.IO.File]::WriteAllLines($environmentFile, $lines)
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $appPassword = $null
    $securePassword = $null
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $runningProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if (-not $runningProcess -or $runningProcess.CommandLine -notlike "*uvicorn*app.main:app*") {
        throw "Port $Port is being used by another application. The SMTP password was saved, but the backend was not restarted."
    }

    Stop-Process -Id $listener.OwningProcess -Force
    Start-Sleep -Milliseconds 750
}

& $startScript -Port $Port
Write-Host "Local email configuration is ready."
