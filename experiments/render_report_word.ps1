param(
    [string]$InputDocx = "output/docx/bao_cao_hexudon.docx",
    [string]$OutputPdf = "scratch/word_report_review/report.pdf",
    [switch]$UpdateFieldsAndSave
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path -LiteralPath $InputDocx).Path
$destination = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPdf))
New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($destination)) | Out-Null
$word = $null
$document = $null
try {
    # Chỉ đọc báo cáo, không chạy macro và không sửa tệp gốc.
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($source, $false, (-not $UpdateFieldsAndSave), $false)
    if ($UpdateFieldsAndSave) {
        if ($document.ReadOnly) { throw "Không thể lưu cập nhật trường vì tài liệu đang chỉ đọc." }
        [void]$document.Fields.Update()
        foreach ($toc in $document.TablesOfContents) {
            $toc.Update()
            $toc.Range.Font.Name = "Times New Roman"
            $toc.Range.Font.Size = 12.5
            $toc.Range.Font.Color = 0
            $toc.Range.ParagraphFormat.SpaceBefore = 0
            $toc.Range.ParagraphFormat.SpaceAfter = 0
        }
        $document.Repaginate()
        foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
        $document.Save()
    }
    $document.Repaginate()
    $pages = $document.ComputeStatistics(2)
    $document.ExportAsFixedFormat($destination, 17)
    Write-Output "Word exported $pages pages to $destination"
}
finally {
    if ($null -ne $document) {
        $document.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit(0)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
}
