[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $DataRoot,

    [Parameter(Mandatory = $true)]
    [string] $TargetRoot
)

$ErrorActionPreference = "Stop"
$checks = [ordered]@{}
$failures = [System.Collections.Generic.List[string]]::new()

function Check([string] $name, [bool] $passed, [string] $reason) {
    $checks[$name] = [pscustomobject]@{ Passed = $passed; Reason = $reason }
    if (-not $passed) { $failures.Add("${name}: $reason") }
}

function ReadJson([string] $path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json }
    catch { return $null }
}

$binary = Join-Path $TargetRoot "EnterpriseEA.ex5"
$compileLog = Join-Path $TargetRoot "EnterpriseEA.log"
$runtime = ReadJson (Join-Path $DataRoot "runtime_status.json")
$selection = ReadJson (Join-Path $DataRoot "symbol_selection.json")
$policy = ReadJson (Join-Path $DataRoot "policy_settings.json")
$controller = ReadJson (Join-Path $DataRoot "execution_controller_state.json")
$recovery = ReadJson (Join-Path $DataRoot "execution_result.json")
$authorization = ReadJson (Join-Path $DataRoot "live_authorization.json")

Check "target_binary" (Test-Path -LiteralPath $binary) "EnterpriseEA.ex5 is present"
Check "compile_log" ((Test-Path -LiteralPath $compileLog) -and
    ((Get-Content -LiteralPath $compileLog -Raw) -match "Result:\s*0 errors,\s*0 warnings")) "compile log is clean"
Check "runtime_current" ($null -ne $runtime -and $runtime.runtime_state -eq "OBSERVING" -and
    $runtime.reason_code -eq "RUNTIME_EVIDENCE_CURRENT" -and -not [bool]$runtime.new_entries_blocked) "runtime is current and entry-enabled"
Check "runtime_refresh" ($null -ne $runtime -and [int]$runtime.refresh_failure_count -eq 0 -and
    [int]$runtime.consecutive_refresh_failures -eq 0) "runtime has no refresh failures"
Check "selection_fingerprint" ($null -ne $runtime -and -not [string]::IsNullOrWhiteSpace([string]$runtime.selected_symbols_fingerprint) -and
    $null -ne $selection) "selection fingerprint and selection document are present"
Check "policy" ($null -ne $policy -and $policy.committed_policy -ne "UNSELECTED" -and
    [bool]$policy.policy_confirmed) "a committed and confirmed policy is present"
Check "controller" ($null -ne $controller) "durable execution controller state is present"
Check "recovery" ($null -eq $recovery -or $recovery.confirmation_state -ne "EXECUTION_UNKNOWN") "no unresolved execution recovery barrier"
Check "authorization" ($null -ne $authorization) "authorization document is present"

$ready = $failures.Count -eq 0
$report = [pscustomobject]@{
    Status = if ($ready) { "READY_FOR_MANUAL_REVIEW" } else { "NOT_READY" }
    Checks = $checks
    Failures = @($failures)
}
Write-Output ($report | ConvertTo-Json -Depth 6)
if (-not $ready) { exit 2 }
