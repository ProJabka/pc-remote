param(
    [string]$Root = (Join-Path $PSScriptRoot 'shared'),
    [string]$BindAddress = '0.0.0.0',
    [ValidateRange(1,65535)][int]$Port = 8443,
    [switch]$ReadOnly,
    [switch]$RotateToken
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONUTF8 = '1'
$localPython = Join-Path $PSScriptRoot 'tools\python\python.exe'
$python = $null
$prefix = @()
if (Test-Path -LiteralPath $localPython) {
    $python = $localPython
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $python = 'py.exe'
    $prefix = @('-3')
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $python = 'python.exe'
}

$dependencyCheck = $false
if ($python) {
    & $python @prefix -c "import sys,importlib.util; sys.exit(0 if sys.version_info >= (3,11) and importlib.util.find_spec('cryptography') else 1)" 2>$null
    $dependencyCheck = ($LASTEXITCODE -eq 0)
}

# A fresh clone may not have the private, bundled Python runtime yet.
# Bootstrap it automatically so double-clicking start-server.cmd is enough.
if (-not $dependencyCheck) {
    $setupScript = Join-Path $PSScriptRoot 'setup-tools.ps1'
    if (-not (Test-Path -LiteralPath $setupScript)) {
        throw 'setup-tools.ps1 is missing. Download the complete project and retry.'
    }
    Write-Host 'Подготавливаю Python и зависимости сервера (это нужно только при первом запуске)...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setupScript
    if ($LASTEXITCODE -ne 0) {
        throw 'Server setup failed. Check the internet connection and retry.'
    }
    if (-not (Test-Path -LiteralPath $localPython)) {
        throw 'Setup finished, but the local Python runtime was not found.'
    }
    $python = $localPython
    $prefix = @()
    & $python -c "import sys,importlib.util; sys.exit(0 if sys.version_info >= (3,11) and importlib.util.find_spec('cryptography') else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw 'The cryptography dependency is missing. Run setup-tools.cmd and retry.'
    }
}
$share = (Resolve-Path -LiteralPath $Root).Path
$serverArgs = @((Join-Path $PSScriptRoot 'server\server.py'), '--root', $share,
    '--host', $BindAddress, '--port', "$Port")
if ($ReadOnly) { $serverArgs += '--read-only' }
if ($RotateToken) { $serverArgs += '--rotate-token' }
& $python @prefix @serverArgs
exit $LASTEXITCODE
