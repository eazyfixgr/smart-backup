#Requires -Version 5.1
<#
  One-click Windows EXE builder.

  Reads build.config.json (name, entry, spec, icon, extraArgs) and
  build_version.json (version), installs PyInstaller/requirements if needed,
  builds with PyInstaller and copies the resulting EXE to:
      release\<name>-<version>-windows.exe

  Run it by double-clicking build_exe.bat.
#>
param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root

$configPath = Join-Path $Root 'build.config.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    throw 'build.config.json is missing next to build_exe.ps1.'
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json

$name = [string]$config.name
$entry = [string]$config.entry
if (-not $name -or -not $entry) { throw 'build.config.json must define name and entry.' }

$version = '1.0.0'
$versionPath = Join-Path $Root 'build_version.json'
if (Test-Path -LiteralPath $versionPath) {
    try { $version = [string]((Get-Content -LiteralPath $versionPath -Raw | ConvertFrom-Json).version) } catch { }
}
if (-not $version) { $version = '1.0.0' }

$python = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else {
    throw 'Python was not found. Install Python 3 and enable "Add Python to PATH".'
}

function Run-Python {
    param([string[]]$Arguments)
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $python $($Arguments -join ' ')" }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor White
Write-Host "  Building $name $version" -ForegroundColor White
Write-Host "=============================================" -ForegroundColor White

$hasPyInstaller = $false
try {
    & $python -m PyInstaller --version *> $null
    if ($LASTEXITCODE -eq 0) { $hasPyInstaller = $true }
} catch { }
if (-not $hasPyInstaller) {
    Write-Host "==> Installing PyInstaller" -ForegroundColor Cyan
    Run-Python @('-m', 'pip', 'install', '--upgrade', 'pyinstaller')
} else {
    Write-Host "==> PyInstaller is installed" -ForegroundColor Green
}

$requirements = Join-Path $Root 'requirements-build.txt'
if (-not (Test-Path -LiteralPath $requirements)) {
    $requirements = Join-Path $Root 'requirements.txt'
}
if (Test-Path -LiteralPath $requirements) {
    $requirementsName = Split-Path -Leaf $requirements
    Write-Host "==> Installing $requirementsName" -ForegroundColor Cyan
    Run-Python @('-m', 'pip', 'install', '-r', $requirementsName)
}

$spec = [string]$config.spec
if ($spec -and (Test-Path -LiteralPath (Join-Path $Root $spec))) {
    Write-Host "==> Building from $spec" -ForegroundColor Cyan
    Run-Python @('-m', 'PyInstaller', '--noconfirm', '--clean', $spec)
} else {
    Write-Host "==> Building from $entry" -ForegroundColor Cyan
    $pyArgs = @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed', '--name', $name)
    if ($config.icon) { $pyArgs += @('--icon', [string]$config.icon) }
    if ($config.extraArgs) { $pyArgs += @($config.extraArgs | ForEach-Object { [string]$_ }) }
    $pyArgs += $entry
    Run-Python $pyArgs
}

$exePath = Join-Path $Root "dist\$name.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "The build finished but dist\$name.exe was not found."
}

$releaseDir = Join-Path $Root 'release'
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$outPath = Join-Path $releaseDir "$name-$version-windows.exe"
Copy-Item -LiteralPath $exePath -Destination $outPath -Force
$sizeMb = [math]::Round((Get-Item -LiteralPath $outPath).Length / 1MB, 2)

Write-Host ""
Write-Host "Done: $outPath ($sizeMb MB)" -ForegroundColor Green
Write-Host "Upload this file to the GitHub Release." -ForegroundColor Yellow
