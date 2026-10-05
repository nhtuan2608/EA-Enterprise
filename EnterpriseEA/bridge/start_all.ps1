# Starts the EnterpriseEA supervisor (G21): it runs and restarts the AI bridge, the Telegram
# gateway and the soak monitor, and alerts on Telegram. Run once after logging in; closing this
# window stops all of them. No scheduled task is created.
param([string]$QueueRoot = "", [string]$Config = (Join-Path $PSScriptRoot "telegram.json"))
$ErrorActionPreference = "Stop"
if ($QueueRoot -eq "") {
    $terminals = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    $found = Get-ChildItem -LiteralPath $terminals -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "MQL5\Files\EnterpriseEA" } |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $found) { throw "MQL5\Files\EnterpriseEA not found; pass -QueueRoot" }
    $QueueRoot = $found
}
if (-not $env:EEA_TELEGRAM_TOKEN) {
    $env:EEA_TELEGRAM_TOKEN = [Environment]::GetEnvironmentVariable("EEA_TELEGRAM_TOKEN", "User")
}
Write-Host "EnterpriseEA supervisor -> $QueueRoot (Ctrl+C or close the window to stop everything)"
& python (Join-Path $PSScriptRoot "supervisor.py") --queue-root $QueueRoot --config $Config
