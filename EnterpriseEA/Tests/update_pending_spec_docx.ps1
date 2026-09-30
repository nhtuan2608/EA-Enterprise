$ErrorActionPreference = 'Stop'
$root = (Resolve-Path '.').Path
$source = Join-Path $root 'Dac_ta_tong_the_EA_MT5_MCP_AI_News_Dashboard_v1_2.docx'
$target = Join-Path $root 'Dac_ta_tong_the_EA_MT5_MCP_AI_News_Dashboard_v1_3.docx'
$spec = Join-Path $root 'EnterpriseEA/PENDING_ORDER_LIFECYCLE_SPEC.md'
$plan = Join-Path $root 'EnterpriseEA/PENDING_ORDER_LIFECYCLE_PLAN.md'
Copy-Item -LiteralPath $source -Destination $target -Force
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($target)
    try {
        foreach ($paragraph in $doc.Paragraphs) {
            if ($paragraph.Range.Text -match '1\.2.*30.*2026') {
                $status = (Get-Content -LiteralPath $spec -Encoding UTF8 -TotalCount 1).TrimStart('#',' ')
                $versionText = $paragraph.Range.Text -replace '1\.2','1.3'
                $versionText = $versionText -replace '\|[^|]*$', ('|  ' + $status)
                $paragraph.Range.Text = $versionText.TrimEnd([char]13,[char]7) + [char]13
                break
            }
        }
        $selection = $word.Selection
        $null = $selection.EndKey(6)
        $selection.TypeParagraph()
        foreach ($item in @(@{Path=$spec}, @{Path=$plan})) {
            $selection.Style = $doc.Styles.Item('Heading 1')
            $heading = (Get-Content -LiteralPath $item.Path -Encoding UTF8 -TotalCount 1).TrimStart('#',' ')
            $selection.TypeText($heading)
            $selection.TypeParagraph()
            foreach ($line in (Get-Content -LiteralPath $item.Path -Encoding UTF8)) {
                if ($line -match '^# ') { continue }
                if ($line -match '^## (.*)$') {
                    $selection.Style = $doc.Styles.Item('Heading 2')
                    $selection.TypeText($Matches[1])
                } elseif ($line.Trim() -ne '') {
                    $selection.Style = $doc.Styles.Item('Normal')
                    $clean = $line.Replace('**','').Replace('`','')
                    $selection.TypeText($clean)
                } else { continue }
                $selection.TypeParagraph()
            }
        }
        $doc.Save()
        Write-Output ('OUTPUT=' + $target)
        Write-Output ('PAGES=' + $doc.ComputeStatistics(2))
    } finally { $doc.Close($false) }
} finally { $word.Quit() }
