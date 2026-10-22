[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Package,
    [Parameter(Mandatory)][string]$WorkDirectory,
    [Parameter(Mandatory)][string]$ReaderDll
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.4') { throw 'Use PowerShell 7.4 or later.' }
$pkgPath = (Resolve-Path -LiteralPath $Package).Path
$workPath = (Resolve-Path -LiteralPath $WorkDirectory).Path
$libraryPath = (Resolve-Path -LiteralPath $ReaderDll).Path
$index = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'data/source-index.json') | ConvertFrom-Json
$tables = Get-Content -Raw -LiteralPath (Join-Path $workPath 'validation.json') | ConvertFrom-Json
$binaries = Get-Content -Raw -LiteralPath (Join-Path $workPath 'binary-text-validation.json') | ConvertFrom-Json
$records = @($tables.files) + @($binaries.files | Where-Object kind -eq 'hud_utf8_property') + @($tables.generated) + @($tables.textures)
$expectedResources = @($index.tables).Count + @($index.generated).Count + @($index.textures).Count + @($binaries.files | Where-Object kind -eq 'hud_utf8_property').Count
$executable = @($binaries.files | Where-Object path -eq 'eboot.bin')
if ($records.Count -ne $expectedResources -or $executable.Count -ne 1) { throw 'Expected complete v1.0 work-directory validation reports.' }
Add-Type -Path $libraryPath
if (-not ('ShadowsTools.PfscReader' -as [type])) {
    $readerSource = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'scripts/ArchiveReaders.cs'))
    $references = @((Get-ChildItem -LiteralPath (Join-Path $PSHOME 'ref') -Filter '*.dll').FullName) + $libraryPath
    Add-Type -TypeDefinition $readerSource -ReferencedAssemblies $references -CompilerOptions '/nowarn:1701'
}
$stream = [IO.File]::OpenRead($pkgPath)
try { $pkg = [LibOrbisPkg.PKG.PkgReader]::new($stream).ReadPkg() }
finally { $stream.Dispose() }
if ($pkg.Header.content_id -notmatch 'CUSA03562_00') { throw 'Unexpected package content ID.' }
$key = $pkg.GetEkpfs()
if ($null -eq $key) { throw 'This reader cannot open the package.' }
$mapped = [IO.MemoryMappedFiles.MemoryMappedFile]::CreateFromFile($pkgPath, [IO.FileMode]::Open, [NullString]::Value, 0, [IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
try {
    $accessor = $mapped.CreateViewAccessor([long]$pkg.Header.pfs_image_offset,[long]$pkg.Header.pfs_image_size,[IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
    try {
        $outer = [LibOrbisPkg.PFS.PfsReader]::new($accessor,$pkg.Header.pfs_flags,$key,$null,$null)
        $compressed = [ShadowsTools.PfscReader]::new($outer.GetFile('pfs_image.dat').GetView())
        $inner = [LibOrbisPkg.PFS.PfsReader]::new($compressed,0,$null,$null,$null)
        $files = @{}
        foreach ($file in $inner.GetAllFiles()) { $files[($file.FullName -replace '^/uroot/','')] = $file }
        if (-not $files.ContainsKey('DAT/common.psarc') -or -not $files.ContainsKey('eboot.bin')) { throw 'Missing translated payload files.' }
        $archive = [ShadowsTools.PsarcReader]::new($files['DAT/common.psarc'].GetView())
        $entries = @{}
        foreach ($entry in $archive.Entries) { $entries[$entry.Path] = $entry }
        foreach ($record in $records) {
            $name = $record.path -replace '^common/',''
            if (-not $entries.ContainsKey($name)) { throw "Missing translated resource: $name" }
            $bytes = $archive.Read($entries[$name])
            $actual = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
            if ($actual -ne $record.output_sha256) { throw "Package resource mismatch: $name" }
        }
        $size = (Get-Item -LiteralPath (Join-Path $workPath 'overlay/eboot.bin')).Length
        if ($files['eboot.bin'].size -ne $size) { throw 'Executable size differs.' }
        $bytes = [byte[]]::new($size)
        $files['eboot.bin'].GetView().Read(0,$bytes,0,$bytes.Length)
        $actual = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
        if ($actual -ne $executable[0].output_sha256) { throw 'Package executable mismatch.' }
    } finally { $accessor.Dispose() }
} finally { $mapped.Dispose() }
$report = [ordered]@{
    status = 'translated_payload_readback_verified'
    package = $pkgPath
    verified_archive_resources = $records.Count
    executable_verified = $true
    entire_package_integrity_checked = $false
    console_tested = $false
}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workPath 'package-readback.json') -Encoding utf8
$report | ConvertTo-Json
Write-Output 'Translated payload matches the prepared build. This does not verify every PKG integrity field or console behavior.'
