# Logon starter for the EnterpriseEA supervisor, called by a shortcut in the Windows Startup folder
# (shell:startup), usually with -WindowStyle Hidden so the window cannot be closed by mistake.
# Does nothing when a supervisor.py is already running (no duplicate gateways / AI bridges).
# Stop it: find the python process whose command line has supervisor.py and end it (its children stop with it).
param([string]$Config = "")
$ErrorActionPreference = "Stop"
$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match 'supervisor\.py' }
if ($running) { exit 0 }
$start = Join-Path $PSScriptRoot "start_all.ps1"
if ($Config -ne "") { & $start -Config $Config } else { & $start }
