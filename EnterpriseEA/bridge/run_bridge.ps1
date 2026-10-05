# Starts the EnterpriseEA AI bridge on Windows (manual run; no scheduled task is created).
param(
    [string]$QueueRoot = "",
    [string]$Config = "",
    [switch]$Once
)
$ErrorActionPreference = "Stop"
if ($QueueRoot -eq "") {
    $terminals = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    $found = Get-ChildItem -LiteralPath $terminals -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "MQL5\Files\EnterpriseEA" } |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $found) { throw "MQL5\Files\EnterpriseEA not found; pass -QueueRoot" }
    $QueueRoot = $found
}
$script = Join-Path $PSScriptRoot "ai_bridge.py"
$arguments = @($script, "--queue-root", $QueueRoot)
if ($Config -ne "") { $arguments += @("--config", $Config) }
if ($Once) { $arguments += "--once" } else { $arguments += "--loop" }
Write-Host "AI bridge -> $QueueRoot"
& python @arguments
