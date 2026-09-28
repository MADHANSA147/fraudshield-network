$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    throw 'Create the Python environment using README.md first.'
}
if (-not (Test-Path -LiteralPath 'apps/web/dist/index.html')) {
    throw 'Build the frontend with npm ci and npm run build in apps/web first.'
}
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
& '.venv/Scripts/python.exe' -m fraudshield.cli serve
