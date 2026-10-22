[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$UpdatePackage,
    [Parameter(Mandatory)][string]$Destination,
    [Parameter(Mandatory)][string]$ReaderDll,
    [switch]$TranslationInputsOnly
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.4') { throw 'Use PowerShell 7.4 or later.' }
$pkgPath = (Resolve-Path -LiteralPath $UpdatePackage).Path
$libraryPath = (Resolve-Path -LiteralPath $ReaderDll).Path
$outputRoot = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $outputRoot) { throw 'Destination must be a new folder.' }
Add-Type -Path $libraryPath
if (-not ('ShadowsTools.PfscReader' -as [type])) {
    $readerSource = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'scripts/ArchiveReaders.cs'))
    $references = @((Get-ChildItem -LiteralPath (Join-Path $PSHOME 'ref') -Filter '*.dll').FullName) + $libraryPath
    Add-Type -TypeDefinition $readerSource -ReferencedAssemblies $references -CompilerOptions '/nowarn:1701'
}
function Save-Path([string]$Relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $outputRoot $Relative))
    if (-not $path.StartsWith($outputRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe package path: $Relative" }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
    return $path
}
$stream = [IO.File]::OpenRead($pkgPath)
try { $pkg = [LibOrbisPkg.PKG.PkgReader]::new($stream).ReadPkg() }
finally { $stream.Dispose() }
if ($pkg.Header.content_id -notmatch 'CUSA03562_00') { throw 'This is not the expected CUSA03562 package.' }
$key = $pkg.GetEkpfs()
if ($null -eq $key) { throw 'This reader cannot open the supplied package. Use a compatible extracted update folder.' }
$mapped = [IO.MemoryMappedFiles.MemoryMappedFile]::CreateFromFile($pkgPath, [IO.FileMode]::Open, [NullString]::Value, 0, [IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
try {
    if (-not $TranslationInputsOnly) {
        foreach ($meta in $pkg.Metas.Metas) {
            if ([LibOrbisPkg.GP4.Gp4Creator]::GeneratedEntries -contains $meta.id) { continue }
            if (-not [LibOrbisPkg.PKG.EntryNames]::IdToName.ContainsKey($meta.id)) { continue }
            $name = [LibOrbisPkg.PKG.EntryNames]::IdToName[$meta.id]
            $storedSize = if ($meta.Encrypted) { ($meta.DataSize + 15) -band (-bnot 15) } else { $meta.DataSize }
            $entryStream = $mapped.CreateViewStream($meta.DataOffset, $storedSize, [IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
            try {
                $bytes = [byte[]]::new($storedSize)
                $entryStream.ReadExactly($bytes)
                if ($meta.Encrypted) { $bytes = [LibOrbisPkg.PKG.Entry]::Decrypt($bytes, $pkg, $meta) }
                if ($storedSize -ne $meta.DataSize) { $bytes = $bytes[0..($meta.DataSize - 1)] }
                [IO.File]::WriteAllBytes((Save-Path "sce_sys/$name"),$bytes)
            } finally { $entryStream.Dispose() }
        }
    }
    $accessor = $mapped.CreateViewAccessor([long]$pkg.Header.pfs_image_offset,[long]$pkg.Header.pfs_image_size,[IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
    try {
        $outer = [LibOrbisPkg.PFS.PfsReader]::new($accessor,$pkg.Header.pfs_flags,$key,$null,$null)
        $compressed = [ShadowsTools.PfscReader]::new($outer.GetFile('pfs_image.dat').GetView())
        $inner = [LibOrbisPkg.PFS.PfsReader]::new($compressed,0,$null,$null,$null)
        $files = @($inner.GetAllFiles())
        foreach ($file in $files) {
            $relative = $file.FullName -replace '^/uroot/', ''
            if ($TranslationInputsOnly -and $relative -notin @('DAT/common.psarc','eboot.bin')) { continue }
            $file.Save((Save-Path $relative),$false)
            Write-Output "Extracted $relative"
        }
    } finally { $accessor.Dispose() }
} finally { $mapped.Dispose() }
Write-Output "Extraction finished: $outputRoot"
