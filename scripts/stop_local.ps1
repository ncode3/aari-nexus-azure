param([string]$StateRoot = (Join-Path $env:LOCALAPPDATA 'AARI\Nexus'))
$ErrorActionPreference = 'Stop'
$pidPath = Join-Path $StateRoot 'runtime.json'
if (!(Test-Path -LiteralPath $pidPath)) { Write-Output 'No managed Nexus process is recorded.'; exit 0 }
$metadata = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
$stopped = $false
foreach ($kind in @('launcher','server')) {
    $processId = $metadata.PSObject.Properties["${kind}_pid"].Value
    if (!$processId) { continue }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (!$process) { continue }
    $expectedPath = $metadata.PSObject.Properties["${kind}_path"].Value
    $expectedStart = $metadata.PSObject.Properties["${kind}_started"].Value
    if ($process.Path -ne $expectedPath -or $process.StartTime.ToUniversalTime().ToString('o') -ne $expectedStart) { throw 'Recorded PID was reused or changed identity; refusing to stop an unrelated process.' }
    & taskkill /PID $process.Id /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Nexus process-tree shutdown failed.' }
    $process.WaitForExit(10000) | Out-Null
    $stopped = $true
    break
}
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$($metadata.port)/healthz" -TimeoutSec 1 } catch { $health = $null; break }
    Start-Sleep -Milliseconds 250
}
if ($health) { throw 'A service still answers on the Nexus port; shutdown is not verified.' }
Write-Output 'Nexus stopped. Persistent state and backups retained.'
