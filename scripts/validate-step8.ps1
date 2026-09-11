$ErrorActionPreference = 'Stop'

Write-Host 'Step 8H final performance validation'
Write-Host '[1/3] Backend test suite'
Push-Location (Join-Path $PSScriptRoot '..\backend')
try {
    python -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Backend test suite failed.' }
} finally {
    Pop-Location
}

Write-Host '[2/3] Frontend regression tests'
Push-Location (Join-Path $PSScriptRoot '..\frontend-ui')
try {
    npm test -- --run
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    npm run lint
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lint failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally {
    Pop-Location
}

Write-Host '[3/3] Step 8H architecture checks'
Push-Location (Join-Path $PSScriptRoot '..\backend')
try {
    python -m pytest tests/test_step8h_final_performance_validation.py -q
    if ($LASTEXITCODE -ne 0) { throw 'Step 8H architecture checks failed.' }
} finally {
    Pop-Location
}

Write-Host 'Step 8H validation PASS'
