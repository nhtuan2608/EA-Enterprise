# Starts the EnterpriseEA Telegram gateway on Windows (manual run; no scheduled task is created).
# The bot token is read from the EEA_TELEGRAM_TOKEN environment variable (or token_file in the config).
param(
    [string]$QueueRoot = "",
    [string]$Config = (Join-Path $PSScriptRoot "telegram.json"),
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
if (-not $env:EEA_TELEGRAM_TOKEN) {
    $env:EEA_TELEGRAM_TOKEN = [Environment]::GetEnvironmentVariable("EEA_TELEGRAM_TOKEN", "User")
}
$script = Join-Path $PSScriptRoot "telegram_gateway.py"
$arguments = @($script, "--queue-root", $QueueRoot, "--config", $Config)
if ($Once) { $arguments += "--once" } else { $arguments += "--loop" }
Write-Host "Telegram gateway -> $QueueRoot"
& python @arguments
