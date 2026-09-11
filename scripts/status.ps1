[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose ps
$frontend = docker compose port frontend 80 2>$null
$backend = docker compose port backend 8000 2>$null
if ($frontend) { Write-Host "Frontend: http://$($frontend.Trim())" -ForegroundColor Green }
if ($backend) { Write-Host "Backend:  http://$($backend.Trim())" -ForegroundColor Green }
