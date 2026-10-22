$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) '.secrets'
$keyPath = Join-Path $secretDirectory 'notesapp-comment.key'
$keyMarkerPath = Join-Path $secretDirectory 'notesapp-comment.key.created'
New-Item -ItemType Directory -Path $secretDirectory -Force | Out-Null
if (Test-Path -LiteralPath $keyPath) {
    if ((Get-Item -LiteralPath $keyPath).Length -ne 32) {
        throw 'Existing comment key is invalid. Restore the original 32-byte key; do not replace it.'
    }
    if (-not (Test-Path -LiteralPath $keyMarkerPath)) {
        [System.IO.File]::WriteAllText($keyMarkerPath, 'A persistent comment key was initialized. Restore the original key if it is lost.')
    }
    Write-Host 'Using the existing comment key.'
    return
}
if (Test-Path -LiteralPath $keyMarkerPath) {
    throw 'The comment key is missing after initialization. Restore the original key; a replacement will not decrypt existing data.'
}
$keyBytes = New-Object byte[] 32
$randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $randomGenerator.GetBytes($keyBytes) } finally { $randomGenerator.Dispose() }
$keyStream = [System.IO.File]::Open($keyPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try { $keyStream.Write($keyBytes, 0, $keyBytes.Length) } finally { $keyStream.Dispose() }
[Array]::Clear($keyBytes, 0, $keyBytes.Length)
[System.IO.File]::WriteAllText($keyMarkerPath, 'A persistent comment key was initialized. Restore the original key if it is lost.')
Write-Host 'Created a persistent comment key outside the project directory.'
