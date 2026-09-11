$ErrorActionPreference = "Stop"

$projectRoot = "C:\ReportingTool\frontend-ui"

$appFile = Join-Path `
    $projectRoot `
    "src\App.jsx"

$backupFile = Join-Path `
    $projectRoot `
    "src\Backup\App_before_datasource_update.jsx"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Generic Datasource Migration" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# VERIFY APP FILE
# ------------------------------------------------------------

if (-not (Test-Path $appFile)) {

    throw "App.jsx was not found at $appFile"

}

# ------------------------------------------------------------
# CREATE BACKUP
# ------------------------------------------------------------

Copy-Item `
    $appFile `
    $backupFile `
    -Force

Write-Host "Backup created:" -ForegroundColor Green
Write-Host $backupFile
Write-Host ""

# ------------------------------------------------------------
# READ APP.JSX
# ------------------------------------------------------------

$content = Get-Content `
    $appFile `
    -Raw

$originalContent = $content

# ------------------------------------------------------------
# OLD MYSQL / MONGODB TEST ENDPOINT
# ------------------------------------------------------------

$content = $content.Replace(
    'sourceType === "mysql"
          ? "/datasource/mysql/test"
          : "/datasource/mongodb/test"',
    '"/datasource/test"'
)

# ------------------------------------------------------------
# OLD MYSQL / MONGODB TABLE ENDPOINT
# ------------------------------------------------------------

$content = $content.Replace(
    'sourceType === "mysql"
          ? "/datasource/mysql/tables"
          : "/datasource/mongodb/collections"',
    '"/datasource/tables"'
)

# ------------------------------------------------------------
# OLD MYSQL / MONGODB COLUMN ENDPOINT
# ------------------------------------------------------------

$content = $content.Replace(
    'sourceType === "mysql"
          ? "/datasource/mysql/columns"
          : "/datasource/mongodb/fields"',
    '"/datasource/columns"'
)

# ------------------------------------------------------------
# TEST REQUEST BODY
# ------------------------------------------------------------

$oldTestBody = @'
{
          host,
          port: Number(port),
          username: username || null,
          password: password || null,
        }
'@

$newTestBody = @'
{
          source_type: sourceType,
          host,
          port: Number(port),
          username: username || null,
          password: password || null,
        }
'@

$content = $content.Replace(
    $oldTestBody,
    $newTestBody
)

# ------------------------------------------------------------
# TABLE REQUEST BODY
# ------------------------------------------------------------

$oldTableBody = @'
{
              host,
              port: Number(port),
              username: username || null,
              password: password || null,
              database: db,
            }
'@

$newTableBody = @'
{
              source_type: sourceType,
              host,
              port: Number(port),
              username: username || null,
              password: password || null,
              database: db,
            }
'@

$content = $content.Replace(
    $oldTableBody,
    $newTableBody
)

# ------------------------------------------------------------
# COLUMN REQUEST BODY
# ------------------------------------------------------------

$oldColumnBody = @'
{
              host,
              port: Number(port),
              username: username || null,
              password: password || null,
              database,
              collection: name,
            }
'@

$newColumnBody = @'
{
              source_type: sourceType,
              host,
              port: Number(port),
              username: username || null,
              password: password || null,
              database,
              table: name,
            }
'@

$content = $content.Replace(
    $oldColumnBody,
    $newColumnBody
)

# ------------------------------------------------------------
# WRITE UPDATED APP.JSX
# ------------------------------------------------------------

if ($content -eq $originalContent) {

    Write-Host ""
    Write-Host "No matching datasource code was changed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "App.jsx may already use the generic datasource API."
    Write-Host ""

    exit 0
}

Set-Content `
    -Path $appFile `
    -Value $content `
    -Encoding UTF8

Write-Host ""
Write-Host "App.jsx updated successfully." -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# CHECK FOR OLD ENDPOINTS
# ------------------------------------------------------------

Write-Host "Checking for remaining old datasource endpoints..." `
    -ForegroundColor Cyan

$legacyMatches = Select-String `
    -Path $appFile `
    -Pattern "/datasource/mysql/|/datasource/mongodb/"

if ($legacyMatches) {

    Write-Host ""
    Write-Host "Old datasource endpoints still found:" `
        -ForegroundColor Yellow

    foreach ($match in $legacyMatches) {

        Write-Host `
            "Line $($match.LineNumber): $($match.Line.Trim())"

    }

} else {

    Write-Host ""
    Write-Host "No old datasource endpoints found." `
        -ForegroundColor Green

}

Write-Host ""
Write-Host "Migration finished." -ForegroundColor Green
Write-Host ""