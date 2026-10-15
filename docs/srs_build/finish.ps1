$ErrorActionPreference = "Stop"
$src = "D:\helth_wise_AI\docs\srs_build\HealthWise_AI_SRS.docx"
$out = "D:\helth_wise_AI\docs\HealthWise_AI_SRS.docx"
$pdf = "D:\helth_wise_AI\docs\HealthWise_AI_SRS.pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($src)
  $doc.Repaginate()
  foreach ($t in $doc.TablesOfContents) { $t.Update() }
  $doc.Fields.Update() | Out-Null
  foreach ($t in $doc.TablesOfContents) { $t.Update() }
  $doc.SaveAs2($out, 16)
  $doc.ExportAsFixedFormat($pdf, 17)
  Write-Output ("pages: " + $doc.ComputeStatistics(2))
  $doc.Close($false)
} finally { $word.Quit() }
