param([switch]$ConfigureOnly)
$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'tools\android-studio\bin\studio64.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw 'First run: .\setup-tools.ps1 -Android -Studio'
}
$project = Join-Path $PSScriptRoot 'android'
$jdk = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tools\jdk') -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\java.exe') } |
    Select-Object -First 1
if ($jdk) {
    $env:JAVA_HOME = $jdk.FullName
    $config = Join-Path $project '.gradle\config.properties'
    New-Item -ItemType Directory -Force -Path (Split-Path $config) | Out-Null
    if (-not (Test-Path -LiteralPath $config)) {
        ('java.home=' + $jdk.FullName.Replace('\','/')) | Set-Content -LiteralPath $config -Encoding ascii
    }
    $settings = Join-Path $project '.idea\gradle.xml'
    New-Item -ItemType Directory -Force -Path (Split-Path $settings) | Out-Null
    if (-not (Test-Path -LiteralPath $settings)) {
        @'
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="GradleSettings">
    <option name="linkedExternalProjectsSettings">
      <GradleProjectSettings>
        <option name="externalProjectPath" value="$PROJECT_DIR$" />
        <option name="gradleJvm" value="#GRADLE_LOCAL_JAVA_HOME" />
        <option name="modules">
          <set>
            <option value="$PROJECT_DIR$" />
            <option value="$PROJECT_DIR$/app" />
          </set>
        </option>
      </GradleProjectSettings>
    </option>
  </component>
</project>
'@ | Set-Content -LiteralPath $settings -Encoding utf8
    }
}
if (-not $ConfigureOnly) {
    Start-Process -FilePath $exe -ArgumentList "`"$project`"" -WindowStyle Normal
}
