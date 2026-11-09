param([string]$StateRoot = (Join-Path $env:LOCALAPPDATA 'AARI\Nexus'))
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$configPath = Join-Path $StateRoot '.env.local'
$pidPath = Join-Path $StateRoot 'runtime.json'
if (!(Test-Path -LiteralPath $configPath) -or !(Test-Path -LiteralPath $pythonPath)) { throw 'Install the private configuration and Python environment first.' }
$configuration = [IO.File]::ReadAllText($configPath)
if ($configuration -match '(?im)^NEXUS_TELEGRAM_ENABLED\s*=\s*(true|1|yes)\s*$') { throw 'This start command is poller-free. Telegram requires separate test-bot validation.' }
$port = 8765
if ($configuration -match '(?m)^NEXUS_LOCAL_PORT=(\d+)\s*$') { $port = [int]$Matches[1] }
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
try { $listener.Start() } finally { $listener.Stop() }
$env:NEXUS_LOCAL_ENV_FILE = $configPath
$process = Start-Process -FilePath $pythonPath -ArgumentList '-m','app.local' -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $StateRoot 'runtime.stdout.log') -RedirectStandardError (Join-Path $StateRoot 'runtime.stderr.log') -PassThru
$metadata = @{ launcher_pid = $process.Id; launcher_started = $process.StartTime.ToUniversalTime().ToString('o'); launcher_path = $pythonPath; port = $port }
$metadata | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding UTF8
try {
    $health = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($process.HasExited) { throw 'Nexus exited. Inspect private runtime.stderr.log.' }
        try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/healthz" -TimeoutSec 1 } catch { Start-Sleep -Milliseconds 500; continue }
        if ($health.service -eq 'nexus-local' -and $health.telegram_polling -eq $false -and $health.provider -eq 'ollama') { break }
        throw 'Unexpected process on the Nexus port.'
    }
    if (!$health) { throw 'Nexus startup timed out.' }
    $server = Get-Process -Id $health.pid
    $metadata.server_pid = $server.Id
    $metadata.server_started = $server.StartTime.ToUniversalTime().ToString('o')
    $metadata.server_path = $server.Path
    $metadata | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding UTF8
    Write-Output "Nexus running at http://127.0.0.1:$port; Telegram polling disabled."
} catch {
    if (!$process.HasExited) { & taskkill /PID $process.Id /T /F | Out-Null }
    throw
}
