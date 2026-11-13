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
if (Test-Path -LiteralPath $localPython) {
    $python = $localPython
    $prefix = @()
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $python = 'py.exe'
    $prefix = @('-3')
} else {
    $python = 'python.exe'
    $prefix = @()
}

& $python @prefix -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('cryptography') else 1)"
if ($LASTEXITCODE -ne 0) {
    throw 'Install Python 3.11+ and run: python -m pip install -r server/requirements.txt'
}
$share = (Resolve-Path -LiteralPath $Root).Path
$serverArgs = @((Join-Path $PSScriptRoot 'server\server.py'), '--root', $share,
    '--host', $BindAddress, '--port', "$Port")
if ($ReadOnly) { $serverArgs += '--read-only' }
if ($RotateToken) { $serverArgs += '--rotate-token' }
& $python @prefix @serverArgs
exit $LASTEXITCODE
