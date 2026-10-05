# Starts the EnterpriseEA soak monitor (G17): samples MT5 and the EA every 5 minutes, read-only.
param([string]$QueueRoot = "")
$ErrorActionPreference = "Stop"
if ($QueueRoot -eq "") {
    $terminals = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    $found = Get-ChildItem -LiteralPath $terminals -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "MQL5\Files\EnterpriseEA" } |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $found) { throw "MQL5\Files\EnterpriseEA not found; pass -QueueRoot" }
    $QueueRoot = $found
}
Write-Host "Soak monitor -> $QueueRoot"
& python (Join-Path $PSScriptRoot "soak_monitor.py") --queue-root $QueueRoot --loop
