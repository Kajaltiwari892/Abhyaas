param(
    [string]$DatabaseName = "abhyaas",
    [string]$DatabaseUser = "postgres",
    [int]$Port = 5432,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$backendDirectory = Split-Path -Parent $PSScriptRoot
$candidateBinDirectories = [System.Collections.Generic.List[string]]::new()

$pathCommand = Get-Command "psql.exe" -ErrorAction SilentlyContinue
if ($pathCommand) {
    $candidateBinDirectories.Add((Split-Path -Parent $pathCommand.Source))
}

$postgresService = Get-CimInstance Win32_Service |
    Where-Object { $_.Name -match "postgres" -or $_.DisplayName -match "postgres" } |
    Select-Object -First 1
if ($postgresService -and $postgresService.PathName -match '^"?([^\"]+\\pg_ctl\.exe)') {
    $candidateBinDirectories.Add((Split-Path -Parent $Matches[1]))
}

@("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL") |
    Where-Object { Test-Path -LiteralPath $_ } |
    ForEach-Object {
        Get-ChildItem -LiteralPath $_ -Directory | ForEach-Object {
            $candidateBinDirectories.Add((Join-Path $_.FullName "bin"))
        }
    }

$postgresBin = $candidateBinDirectories |
    Select-Object -Unique |
    Where-Object {
        (Test-Path -LiteralPath (Join-Path $_ "psql.exe")) -and
        (Test-Path -LiteralPath (Join-Path $_ "createdb.exe"))
    } |
    Select-Object -First 1

if (-not $postgresBin) {
    throw "PostgreSQL server command-line tools were not found. Re-run the PostgreSQL installer and ensure Command Line Tools is selected."
}

$psql = Join-Path $postgresBin "psql.exe"
$createdb = Join-Path $postgresBin "createdb.exe"

if ($ValidateOnly) {
    Write-Host "PostgreSQL tools found: $postgresBin" -ForegroundColor Green
    & $psql --version
    exit $LASTEXITCODE
}

Write-Host "Abhyaas local PostgreSQL setup" -ForegroundColor Green
Write-Host "Enter the password you chose for the postgres user during installation."
$securePassword = Read-Host "PostgreSQL password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $env:PGPASSWORD = $plainPassword

    & $psql -w -h localhost -p $Port -U $DatabaseUser -d postgres -c "SELECT current_user;" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL rejected the password. Run the script again with the password selected during installation."
    }

    # psql returns $null when the database does not exist. Comparing $null with
    # "1" is safe in PowerShell, so no string method should be called here.
    $databaseExists = & $psql -w -h localhost -p $Port -U $DatabaseUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DatabaseName';"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not check whether the database exists."
    }

    if ($databaseExists -ne "1") {
        & $createdb -w -h localhost -p $Port -U $DatabaseUser $DatabaseName
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the $DatabaseName database."
        }
        Write-Host "Created PostgreSQL database: $DatabaseName" -ForegroundColor Green
    }
    else {
        Write-Host "PostgreSQL database already exists: $DatabaseName" -ForegroundColor Yellow
    }

    $encodedPassword = [Uri]::EscapeDataString($plainPassword)
    $python = Join-Path $backendDirectory ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $python = "python"
    }
    $jwtSecret = & $python -c "import secrets; print(secrets.token_urlsafe(48))"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not generate the local JWT secret."
    }

    $environmentFile = Join-Path $backendDirectory ".env"
    $environmentContent = @"
APP_ENV=development
APP_NAME=Abhyaas API
API_V1_PREFIX=/api/v1
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql+asyncpg://${DatabaseUser}:${encodedPassword}@localhost:${Port}/${DatabaseName}
JWT_SECRET=$jwtSecret
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30
EMAIL_TOKEN_MINUTES=30
EMAIL_PROVIDER=console
COOKIE_SECURE=false
"@
    Set-Content -LiteralPath $environmentFile -Value $environmentContent -Encoding utf8

    Push-Location $backendDirectory
    try {
        & (Join-Path $backendDirectory ".venv\Scripts\alembic.exe") upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw "Database creation succeeded, but the authentication migration failed."
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "Local PostgreSQL and Backend\.env are ready." -ForegroundColor Green
    Write-Host "You can close this window after reading the result."
}
finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
}
