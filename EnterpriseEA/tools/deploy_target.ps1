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
