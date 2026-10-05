[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $SourceRoot,

    [Parameter(Mandatory = $true)]
    [string] $TargetRoot,

    [switch] $RequireBinaryChanged
)

$ErrorActionPreference = "Stop"
$sourceRootResolved = (Resolve-Path -LiteralPath $SourceRoot).Path
if (-not (Test-Path -LiteralPath $TargetRoot)) {
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}
$targetRootResolved = (Resolve-Path -LiteralPath $TargetRoot).Path

$files = Get-ChildItem -LiteralPath $sourceRootResolved -Recurse -File |
    Where-Object { $_.Extension -in @(".mq5", ".mqh") }
if (-not $files) { throw "No MQL5 source files found under $sourceRootResolved" }

# Compile a private copy first: a failed compile in the terminal folder removes the
# running EA's EnterpriseEA.ex5, so the target is only touched after a clean build.
$metaEditor = @(
    "C:\Program Files\MetaTrader 5\MetaEditor64.exe",
    "C:\Program Files (x86)\MetaTrader 5\MetaEditor64.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $metaEditor) { throw "MetaEditor64.exe not found" }
$precompile = Join-Path ([System.IO.Path]::GetTempPath()) ("eea-precompile-" + [guid]::NewGuid().ToString("N"))
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceRootResolved.Length).TrimStart("\")
    $destination = Join-Path $precompile $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
}
$preLog = Join-Path $precompile "EnterpriseEA.log"
Start-Process -FilePath $metaEditor -ArgumentList @(('/compile:"' + (Join-Path $precompile "EnterpriseEA.mq5") + '"'),
    ('/log:"' + $preLog + '"')) -Wait | Out-Null
$preResult = if (Test-Path -LiteralPath $preLog) { Get-Content -LiteralPath $preLog -Raw } else { "" }
if ($preResult -notmatch "Result:\s*0 errors,\s*0 warnings") {
    throw "Pre-compile is not clean; the target was not changed. Inspect $preLog"
}
Remove-Item -LiteralPath $precompile -Recurse -Force

$copied = 0
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceRootResolved.Length).TrimStart("")
    $destination = Join-Path $targetRootResolved $relative
    $destinationDirectory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    $copied++
}

$compileScript = Join-Path $PSScriptRoot "compile_target.ps1"
if (-not (Test-Path -LiteralPath $compileScript)) {
    throw "Compile helper not found: $compileScript"
}

$compileArgs = @{
    TargetRoot = $targetRootResolved
}
if ($RequireBinaryChanged) { $compileArgs.RequireBinaryChanged = $true }
$compile = & $compileScript @compileArgs
[pscustomobject]@{
    SourceRoot = $sourceRootResolved
    TargetRoot = $targetRootResolved
    FilesCopied = $copied
    Compile = $compile
}
