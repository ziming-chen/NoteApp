param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerCandidates = @(
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
    'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
)
if ($dockerCommand) { $dockerExe = $dockerCommand.Source }
else { $dockerExe = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1 }
if (-not $dockerExe) { throw 'Install Docker Desktop before starting NoteApp.' }
$engineReady = $false
try {
    & $dockerExe version --format '{{.Server.Version}}' 2>$null
    $engineReady = $LASTEXITCODE -eq 0
} catch { }
if (-not $engineReady) {
    $repairScript = Join-Path (Split-Path -Parent $PSScriptRoot) 'Support\DockerDesktop\Repair-DockerDesktop.ps1'
    if (Test-Path -LiteralPath $repairScript) { & $repairScript }
    else { throw 'Start Docker Desktop and wait for the engine to be running, then try again.' }
    & $dockerExe version --format '{{.Server.Version}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop engine is still unavailable.' }
}
& (Join-Path $PSScriptRoot 'Initialize-CommentKey.ps1')
& (Join-Path $PSScriptRoot 'Initialize-ExportKey.ps1')
$composeArgs = @('compose', '-p', 'noteapp', '-f', (Join-Path $PSScriptRoot 'docker-compose.yml'), '-f', (Join-Path $PSScriptRoot 'compose.windows.yml'))
& $dockerExe @composeArgs up -d --build --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'NoteApp could not start. Check the Docker output above.' }
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/healthz' -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200 -and $response.Content.Trim() -eq 'ok') { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'The web service did not pass its health check.' }
Write-Host 'NoteApp is ready: http://localhost:8080'
if (-not $NoBrowser) { Start-Process 'http://localhost:8080' }
