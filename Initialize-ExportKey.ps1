$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) '.secrets'
$keyPath = Join-Path $secretDirectory 'notesapp-export-hmac.key'
$markerPath = Join-Path $secretDirectory 'notesapp-export-hmac.key.created'
New-Item -ItemType Directory -Path $secretDirectory -Force | Out-Null
if (Test-Path -LiteralPath $keyPath) {
    if ((Get-Item -LiteralPath $keyPath).Length -ne 32) {
        throw 'The export HMAC key is invalid. Restore the original 32-byte key.'
    }
    if (-not (Test-Path -LiteralPath $markerPath)) {
        [System.IO.File]::WriteAllText($markerPath, 'Persistent export HMAC key initialized. Restore it if lost.')
    }
    Write-Host 'Using the existing export HMAC key.'
    return
}
if (Test-Path -LiteralPath $markerPath) {
    throw 'The initialized export HMAC key is missing. Restore it; a replacement cannot verify older exports.'
}
$keyBytes = New-Object byte[] 32
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($keyBytes) } finally { $generator.Dispose() }
$stream = [System.IO.File]::Open($keyPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try { $stream.Write($keyBytes, 0, $keyBytes.Length) } finally { $stream.Dispose() }
[Array]::Clear($keyBytes, 0, $keyBytes.Length)
[System.IO.File]::WriteAllText($markerPath, 'Persistent export HMAC key initialized. Restore it if lost.')
Write-Host 'Created a persistent export HMAC key outside the application directory.'
