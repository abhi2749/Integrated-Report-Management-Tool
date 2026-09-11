[CmdletBinding()]
param(
    [string]$FrontendHealthUrl = 'http://localhost:3000/health',
    [string]$BackendHealthUrl = 'http://localhost:8000/health',
    [string[]]$ContainerNames = @(),
    [string]$ComposeFile = ''
)

$ErrorActionPreference = 'Stop'

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Use the existing Docker/PowerShell environment; no additional software is required by this validator."
    }
}

function Assert-Health([string]$Name, [string]$Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10
        if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 400) {
            throw "HTTP $($response.StatusCode)"
        }
        Write-Host "PASS  $Name health: $Url"
    }
    catch {
        throw "FAIL  $Name health: $Url -- $($_.Exception.Message)"
    }
}

Assert-Command 'docker'

$dockerVersion = docker version --format '{{.Server.Version}}'
if (-not $dockerVersion) {
    throw 'Docker daemon is not reachable.'
}
Write-Host "PASS  Docker daemon: $dockerVersion"

if ($ComposeFile) {
    if (-not (Test-Path -LiteralPath $ComposeFile)) {
        throw "Compose file not found: $ComposeFile"
    }
    docker compose -f $ComposeFile config --quiet
    Write-Host "PASS  Compose configuration: $ComposeFile"
}

foreach ($name in $ContainerNames) {
    $status = docker inspect --format '{{.State.Status}}' $name 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $status) {
        throw "Container not found: $name"
    }
    if ($status -ne 'running') {
        throw "Container is not running: $name (status: $status)"
    }
    Write-Host "PASS  Container running: $name"

    $health = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' $name
    if ($health -eq 'unhealthy') {
        throw "Container is unhealthy: $name"
    }
    Write-Host "PASS  Container health: $name ($health)"
}

Assert-Health 'Frontend' $FrontendHealthUrl
Assert-Health 'Backend' $BackendHealthUrl

Write-Host ''
Write-Host 'Step 6J Docker validation: PASS'
