$ErrorActionPreference = 'Stop'
$localJdk = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tools\jdk') -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\java.exe') } |
    Select-Object -First 1
if ($localJdk) { $env:JAVA_HOME = $localJdk.FullName }
$localSdk = Join-Path $PSScriptRoot 'tools\android-sdk'
if (Test-Path -LiteralPath (Join-Path $localSdk 'platforms\android-35')) {
    $env:ANDROID_HOME = $localSdk
    ('sdk.dir=' + $localSdk.Replace('\','/')) |
        Set-Content -LiteralPath (Join-Path $PSScriptRoot 'android\local.properties') -Encoding ascii
}
$tools = Join-Path $PSScriptRoot 'tools'
if (Test-Path -LiteralPath $tools) { $env:GRADLE_USER_HOME = Join-Path $tools 'gradle-home' }
Push-Location -LiteralPath (Join-Path $PSScriptRoot 'android')
try {
    & .\gradlew.bat --console=plain assembleDebug lintDebug
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $dist = Join-Path $PSScriptRoot 'dist'
    New-Item -ItemType Directory -Path $dist -Force | Out-Null
    $apk = Join-Path $dist 'PC-Remote.apk'
    Copy-Item -LiteralPath 'app\build\outputs\apk\debug\app-debug.apk' -Destination $apk -Force
    $release = Join-Path $PSScriptRoot 'release'
    New-Item -ItemType Directory -Path $release -Force | Out-Null
    Copy-Item -LiteralPath $apk -Destination (Join-Path $release 'PC-Remote.apk') -Force
    Write-Output "APK: $apk"
} finally {
    Pop-Location
}
