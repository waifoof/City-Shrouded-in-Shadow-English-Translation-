[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$UpdateFolder,
    [string]$WorkDirectory,
    [string]$BasePackage,
    [string]$Publisher,
    [string]$Python = 'python',
    [switch]$CheckOnly,
    [switch]$EditedTranslations
)
$ErrorActionPreference = 'Stop'
if (-not $CheckOnly -and -not $WorkDirectory) { throw 'Specify a new -WorkDirectory.' }
if ($Publisher -and (-not $BasePackage -or $CheckOnly)) { throw '-Publisher requires -BasePackage and a full build, not -CheckOnly.' }
$scriptPath = Join-Path $PSScriptRoot 'scripts/apply_translation.py'
$applyArgs = @($scriptPath, '--update-folder', $UpdateFolder)
if ($WorkDirectory) { $applyArgs += @('--output', $WorkDirectory) }
if ($BasePackage) { $applyArgs += @('--base-package', $BasePackage) }
if ($CheckOnly) { $applyArgs += '--check-only' }
if ($EditedTranslations) { $applyArgs += '--edited-translations' }
& $Python @applyArgs
if ($LASTEXITCODE -ne 0) { throw 'Translation preparation failed. Review the error above; no original files were patched in place.' }
if ($Publisher) {
    $publisherPath = (Resolve-Path -LiteralPath $Publisher).Path
    $workPath = (Resolve-Path -LiteralPath $WorkDirectory).Path
    $project = Join-Path $workPath 'English-v1.0-1.03.gp4'
    $packageFolder = Join-Path $workPath 'package'
    $temporaryFolder = Join-Path $workPath 'temp'
    [IO.Directory]::CreateDirectory($packageFolder) | Out-Null
    [IO.Directory]::CreateDirectory($temporaryFolder) | Out-Null
    & $publisherPath img_create --oformat pkg --no_progress_bar --tmp_path $temporaryFolder $project $packageFolder *> (Join-Path $workPath 'package-build.log')
    $builderExit = $LASTEXITCODE
    $builderLog = Get-Content -Raw -LiteralPath (Join-Path $workPath 'package-build.log')
    if ($builderExit -ne 0 -or $builderLog -match '\[Error\]' -or $builderLog -notmatch 'Create image Process finished') { throw 'PKG build failed. See package-build.log.' }
    Write-Output "PKG creation finished: $packageFolder"
    Write-Output 'Review the build log and verify/test the new PKG. Source-resource checks are not console testing.'
}
