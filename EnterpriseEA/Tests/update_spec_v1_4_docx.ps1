param(
    [Parameter(Mandatory = $true)] [string] $Replacements,
    [Parameter(Mandatory = $true)] [string] $Appendix
)
# Builds spec v1.4 from v1.3: removes the Paper route (PAPER_EXCLUDED_PERMANENTLY)
# by exact phrase replacement, then appends the normative appendix D.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path '.').Path
$source = Join-Path $root 'Dac_ta_tong_the_EA_MT5_MCP_AI_News_Dashboard_v1_3.docx'
$target = Join-Path $root 'Dac_ta_tong_the_EA_MT5_MCP_AI_News_Dashboard_v1_4.docx'
$pairs = Get-Content -LiteralPath $Replacements -Encoding UTF8 -Raw | ConvertFrom-Json
Copy-Item -LiteralPath $source -Destination $target -Force
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($target)
    try {
        $missing = @()
        foreach ($pair in $pairs) {
            $range = $doc.Content
            $find = $range.Find
            $find.ClearFormatting()
            $find.Replacement.ClearFormatting()
            # Execute(FindText, MatchCase, MatchWholeWord, MatchWildcards, MatchSoundsLike,
            #         MatchAllWordForms, Forward, Wrap, Format, ReplaceWith, Replace)
            $found = $find.Execute($pair[0], $true, $false, $false, $false, $false, $true, 0, $false, $pair[1], 2)
            if (-not $found) { $missing += $pair[0] }
        }
        $selection = $word.Selection
        $null = $selection.EndKey(6)
        $selection.TypeParagraph()
        foreach ($line in (Get-Content -LiteralPath $Appendix -Encoding UTF8)) {
            if ($line -match '^# (.*)$') { $selection.Style = $doc.Styles.Item('Heading 1'); $selection.TypeText($Matches[1]) }
            elseif ($line -match '^## (.*)$') { $selection.Style = $doc.Styles.Item('Heading 2'); $selection.TypeText($Matches[1]) }
            elseif ($line.Trim() -ne '') { $selection.Style = $doc.Styles.Item('Normal'); $selection.TypeText($line) }
            else { continue }
            $selection.TypeParagraph()
        }
        $doc.Save()
        $text = $doc.Content.Text
        $left = ([regex]::Matches($text, '(?i)paper')).Count
        Write-Output ('OUTPUT=' + $target)
        Write-Output ('PAGES=' + $doc.ComputeStatistics(2))
        Write-Output ('MISSING=' + ($missing -join ' || '))
        Write-Output ('PAPER_MENTIONS_LEFT=' + $left)
    } finally { $doc.Close($false) }
} finally { $word.Quit() }
