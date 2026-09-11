[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install/start Docker Desktop, then run this launcher again."
    }
}

function Require-File([string]$RelativePath) {
    if (-not (Test-Path (Join-Path $Root $RelativePath) -PathType Leaf)) {
        throw "Required application file '$RelativePath' is missing from the package."
    }
}

Require-Command 'docker'
Require-File 'docker-compose.yml'
Require-File 'frontend-ui/nginx.conf'

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker daemon is not reachable. Start Docker Desktop and retry.'
}

docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose is not available. Install/update Docker Desktop and retry.'
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'docker-compose.yml validation failed.'
}

Write-Host ''
Write-Host '=== Integrated Report Management Tool ===' -ForegroundColor Cyan
Write-Host 'Pulling production images from Docker Hub...' -ForegroundColor Yellow

docker compose pull
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Hub image pull failed.'
}

Write-Host 'Starting application with Docker-managed host ports...' -ForegroundColor Yellow

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose failed to start the application.'
}

$deadline = (Get-Date).AddMinutes(3)
$healthy = $false

while ((Get-Date) -lt $deadline) {

    $backendId = (docker compose ps -q backend 2>$null).Trim()
    $frontendId = (docker compose ps -q frontend 2>$null).Trim()

    $backendState = if ($backendId) {
        (docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $backendId 2>$null).Trim()
    } else {
        ''
    }

    $frontendState = if ($frontendId) {
        (docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $frontendId 2>$null).Trim()
    } else {
        ''
    }

    if ($backendState -eq 'healthy' -and $frontendState -eq 'healthy') {
        $healthy = $true
        break
    }

    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    docker compose ps
    throw 'Application containers did not become healthy within 3 minutes.'
}

$frontendPort = (docker compose port frontend 80 2>$null).Trim()
$backendPort = (docker compose port backend 8000 2>$null).Trim()

if (-not $frontendPort) {
    throw 'Frontend started but its host port could not be discovered.'
}

$frontendUrl = "http://$frontendPort"
$backendUrl = if ($backendPort) {
    "http://$backendPort"
} else {
    '(internal / not published)'
}

Write-Host ''
Write-Host "Frontend: $frontendUrl" -ForegroundColor Green
Write-Host "Backend:  $backendUrl" -ForegroundColor Green
Write-Host 'Images:   Docker Hub production images' -ForegroundColor Green
Write-Host 'Version:  1.0.0' -ForegroundColor Green
Write-Host 'The frontend proxies API traffic to the backend; no fixed application port is required.' -ForegroundColor Gray
Write-Host ''

if (-not $NoBrowser) {
    Start-Process $frontendUrl
}
