$ErrorActionPreference = 'Stop'
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerCandidates = @(
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
    'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
)
if ($dockerCommand) { $dockerExe = $dockerCommand.Source }
else { $dockerExe = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1 }
if (-not $dockerExe) { throw 'Docker Desktop is not installed.' }
& $dockerExe compose -p noteapp -f (Join-Path $PSScriptRoot 'docker-compose.yml') -f (Join-Path $PSScriptRoot 'compose.windows.yml') down
if ($LASTEXITCODE -ne 0) { throw 'NoteApp could not stop. Check the Docker output above.' }
Write-Host 'NoteApp stopped. The database volume has been kept.'
