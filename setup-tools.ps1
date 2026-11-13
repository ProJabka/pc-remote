param([switch]$Android, [switch]$Studio)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$tools = Join-Path $PSScriptRoot 'tools'
New-Item -ItemType Directory -Force -Path $tools | Out-Null

function Download([string]$Url, [string]$Name, [string]$Sha256 = '') {
    $path = Join-Path $tools $Name
    if (-not (Test-Path -LiteralPath $path)) {
        & curl.exe --fail --location --retry 3 --output $path $Url
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            throw "Download failed: $Url"
        }
    }
    if ($Sha256 -and (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Checksum mismatch for $path. Remove this file and retry."
    }
    return $path
}

$python = Join-Path $tools 'python\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $zip = Download 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip' `
        'python-3.14.10.zip' '90905E64A840557D8C1BC4F5B74DB3D7EE85E3FFB217611CAC1C7813ACEA4159'
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $tools 'python') -Force
}
$pth = Join-Path $tools 'python\python314._pth'
(Get-Content -LiteralPath $pth) -replace '#import site','import site' |
    Set-Content -LiteralPath $pth -Encoding ascii
& $python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('pip') else 1)"
if ($LASTEXITCODE -ne 0) {
    $pip = Download 'https://bootstrap.pypa.io/get-pip.py' 'get-pip.py'
    & $python $pip --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw 'pip installation failed' }
}
& $python -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'server\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Server dependencies installation failed' }

if ($Android) {
    $jdkDir = Join-Path $tools 'jdk'
    $jdk = Get-ChildItem -LiteralPath $jdkDir -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $jdk) {
        $release = Invoke-RestMethod 'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse'
        $package = $release[0].binary.package
        $archive = Download $package.link $package.name $package.checksum
        Expand-Archive -LiteralPath $archive -DestinationPath $jdkDir -Force
        $jdk = Get-ChildItem -LiteralPath $jdkDir -Directory | Select-Object -First 1
    }
    $env:JAVA_HOME = $jdk.FullName
    $sdk = Join-Path $tools 'android-sdk'
    $manager = Join-Path $sdk 'cmdline-tools\latest\bin\sdkmanager.bat'
    if (-not (Test-Path -LiteralPath $manager)) {
        $archive = Download 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip' `
            'android-cli.zip' '4D6931209EEBB1BFB7C7E8B240A6A3CB3AB24479EA294F3539429574B1EEC862'
        $unpack = Join-Path $tools 'android-cli'
        Expand-Archive -LiteralPath $archive -DestinationPath $unpack -Force
        New-Item -ItemType Directory -Force -Path (Join-Path $sdk 'cmdline-tools') | Out-Null
        $source = (Resolve-Path -LiteralPath (Join-Path $unpack 'cmdline-tools')).Path
        $destination = [IO.Path]::GetFullPath((Join-Path $sdk 'cmdline-tools\latest'))
        if (-not $source.StartsWith($tools + '\') -or -not $destination.StartsWith($tools + '\')) {
            throw 'SDK paths are outside the tools directory'
        }
        Move-Item -LiteralPath $source -Destination $destination
    }
    $env:ANDROID_HOME = $sdk
    Write-Output 'Review and accept the Android SDK licenses if you agree:'
    & $manager --licenses
    if ($LASTEXITCODE -ne 0) { throw 'SDK licenses not accepted' }
    & $manager 'platforms;android-35' 'build-tools;35.0.0' 'platform-tools'
    if ($LASTEXITCODE -ne 0) { throw 'Android SDK installation failed' }
    ('sdk.dir=' + $sdk.Replace('\','/')) |
        Set-Content -LiteralPath (Join-Path $PSScriptRoot 'android\local.properties') -Encoding ascii
}
if ($Studio) {
    $exe = Join-Path $tools 'android-studio\bin\studio64.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        $archive = Download 'https://edgedl.me.gvt1.com/android/studio/ide-zips/2026.2.2.9/android-studio-rabbit2-patch1-windows.zip' `
            'studio.zip' '6813B0CE669844B87C5D56B9C5F661362BD3BEBFF55327415496BD7457A7B917'
        Expand-Archive -LiteralPath $archive -DestinationPath $tools -Force
    }
    Write-Output "Android Studio: $exe"
}
Write-Output 'Tools ready. Run start-server.ps1 or build-apk.ps1.'
