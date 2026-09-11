[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$failed = $false

function Assert-Contains([string]$Path, [string]$Pattern, [string]$Message) {
    $content = Get-Content -Raw -LiteralPath $Path
    if ($content -notmatch [regex]::Escape($Pattern)) {
        Write-Host "FAIL: $Message"
        $script:failed = $true
    } else {
        Write-Host "PASS: $Message"
    }
}

$compose = Join-Path $ProjectRoot "docker-compose.yml"
$envExample = Join-Path $ProjectRoot "backend\.env.example"
$dockerfile = Join-Path $ProjectRoot "backend\Dockerfile"
$nginx = Join-Path $ProjectRoot "frontend-ui\nginx.conf"

if (-not (Test-Path $compose)) { throw "docker-compose.yml not found: $compose" }

Assert-Contains $compose '127.0.0.1:8000:8000' 'Backend is not publicly bound by Docker.'
Assert-Contains $compose 'no-new-privileges:true' 'no-new-privileges is enabled.'
Assert-Contains $compose 'cap_drop:' 'Linux capabilities are dropped.'
Assert-Contains $compose 'SECRET_KEY:?SECRET_KEY must be set' 'SECRET_KEY is required by Compose.'
Assert-Contains $compose 'ENCRYPTION_KEY:?ENCRYPTION_KEY must be set' 'ENCRYPTION_KEY is required by Compose.'
Assert-Contains $compose 'SECRET_KEY_PREVIOUS' 'Previous signing key transition is supported.'
Assert-Contains $compose 'ENCRYPTION_KEY_PREVIOUS' 'Previous encryption key transition is supported.'
Assert-Contains $envExample 'Never print or commit real key values.' 'Environment template warns against secret exposure.'
Assert-Contains $dockerfile 'rm -rf' 'Backend image removes development artifacts.'
Assert-Contains $dockerfile '.env' 'Backend image excludes .env.'
Assert-Contains $nginx 'server_tokens off;' 'Nginx server version disclosure is disabled.'

if ($failed) {
    Write-Host "Final security validation: FAILED"
    exit 1
}

Write-Host "Final security validation: PASS"
exit 0
