[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $TargetRoot,

    [switch] $RequireBinaryChanged
)

$ErrorActionPreference = "Stop"
$source = Join-Path $TargetRoot "EnterpriseEA.mq5"
$binary = Join-Path $TargetRoot "EnterpriseEA.ex5"
$log = Join-Path $TargetRoot "EnterpriseEA.log"

if (-not (Test-Path -LiteralPath $source)) { throw "Target source not found: $source" }
if (-not (Test-Path -LiteralPath $binary)) { throw "Target binary not found before compile: $binary" }

$metaEditor = @(
    "C:\Program Files\MetaTrader 5\MetaEditor64.exe",
    "C:\Program Files (x86)\MetaTrader 5\MetaEditor64.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $metaEditor) { throw "MetaEditor64.exe not found" }

$before = Get-FileHash -LiteralPath $binary -Algorithm SHA256
$beforeWrite = (Get-Item -LiteralPath $binary).LastWriteTimeUtc
$compileArg = '/compile:"' + $source + '"'
$process = Start-Process -FilePath $metaEditor -ArgumentList @($compileArg, "/log") -Wait -PassThru
if (-not (Test-Path -LiteralPath $log)) { throw "Compile log not found: $log" }

$result = Get-Content -LiteralPath $log -Raw
if ($result -notmatch "Result:\s*0 errors,\s*0 warnings") {
    throw "Compile result is not clean (MetaEditor exit code $($process.ExitCode)). Inspect $log"
}

# MetaEditor may return 1 even when the compile log reports a clean build.
# Treat the compiler log as authoritative after validating its exact result.

$after = Get-FileHash -LiteralPath $binary -Algorithm SHA256
$afterWrite = (Get-Item -LiteralPath $binary).LastWriteTimeUtc
$changed = $before.Hash -ne $after.Hash -or $beforeWrite -ne $afterWrite
if ($RequireBinaryChanged -and -not $changed) {
    throw "Compile reported 0/0 but EnterpriseEA.ex5 did not change; detach/reload the EA and retry."
}

[pscustomobject]@{
    MetaEditor = $metaEditor
    Result = "0 errors, 0 warnings"
    BinaryChanged = $changed
    BinarySha256 = $after.Hash
    BinaryLastWriteUtc = $afterWrite.ToString("o")
    Log = $log
}
