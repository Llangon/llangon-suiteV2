param(
    [Parameter(Mandatory = $true)][string]$BaseWorkbook,
    [Parameter(Mandatory = $true)][string]$OutputWorkbook
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$basePath = (Resolve-Path $BaseWorkbook).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputWorkbook)
$outputDir = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$layout = Get-Content -LiteralPath (Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\workbook_layout.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest = Get-Content -LiteralPath (Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\field_manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$macroDir = Join-Path $repoRoot "macros\ficha_llangon_v2"
$macroFiles = Get-ChildItem -LiteralPath $macroDir -Filter "*.bas" | Sort-Object Name
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$verifier = Join-Path $repoRoot "scripts\verify_ficha_llangon_v2.py"

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $workbook = $excel.Workbooks.Open($basePath, 0, $false)

    $project = $workbook.VBProject
    foreach ($macroFile in $macroFiles) {
        $componentName = [System.IO.Path]::GetFileNameWithoutExtension($macroFile.Name)
        $existing = $null
        try { $existing = $project.VBComponents.Item($componentName) } catch {}
        if ($null -ne $existing) { $project.VBComponents.Remove($existing) }
        $component = $project.VBComponents.Add(1)
        $component.Name = $componentName
        $component.CodeModule.AddFromString((Get-Content -LiteralPath $macroFile.FullName -Raw -Encoding UTF8))
    }

    foreach ($property in $layout.names.PSObject.Properties) {
        $name = $property.Name
        $reference = [string]$property.Value
        try { $workbook.Names.Item($name).Delete() } catch {}
        $parts = $reference.Split("!", 2)
        $workbook.Names.Add($name, "='" + $parts[0] + "'!" + $parts[1]) | Out-Null
    }

    $ficha = $workbook.Worksheets.Item("Ficha")
    $informe = $workbook.Worksheets.Item("Informe_PDF")
    $listas = $workbook.Worksheets.Item("_Listas")
    $tech = $workbook.Worksheets.Item("_Llangon")
    $informe.Unprotect("")

    foreach ($item in $manifest.scalar_fields) {
        if ($item.logical_id -eq "document.confidentiality_notice") { continue }
        try { $workbook.Names.Item([string]$item.excel_name).RefersToRange.ClearContents() } catch {}
    }
    foreach ($item in $manifest.ranges) {
        try { $workbook.Names.Item([string]$item.excel_name).RefersToRange.ClearContents() } catch {}
    }
    $tech.Range("B2:B6").ClearContents()
    $tech.Range("B9").ClearContents()
    $tech.Range("B10").Value = "manual"
    $tech.Range("B11").ClearContents()
    $tech.Range("B13").ClearContents()
    $tech.Range("B14:B16").Value = 0
    $tech.Range("B17").ClearContents()
    $tech.Range("B18").Value = "Pendiente"
    $tech.Range("B21").ClearContents()
    $ficha.Range("C9").Value = "Pendiente de revisar"
    $informe.Range("A6:H1000").UnMerge()
    $informe.Range("A6:H1000").Clear()
    $informe.Range("A6:H6").Merge()
    $informe.Range("A6").Value = "Vista pendiente de generar desde Ficha"

    $clients = $listas.ListObjects.Item("tblClientes")
    if ($null -ne $clients.DataBodyRange) {
        $reasonIndex = $clients.ListColumns.Item("RazonSocial").Index
        $labelIndex = $clients.ListColumns.Item("Label").Index
        $displayIndex = $clients.ListColumns.Item("DisplayName").Index
        $idIndex = $clients.ListColumns.Item("ID").Index
        $activeIndex = $clients.ListColumns.Item("Activo").Index
        $counts = @{}
        foreach ($row in $clients.ListRows) {
            $reason = ([string]$row.Range.Cells.Item(1, $reasonIndex).Value2).Trim()
            if ($reason) {
                $key = $reason.ToLowerInvariant()
                if (-not $counts.ContainsKey($key)) { $counts[$key] = 0 }
                $counts[$key]++
            }
        }
        foreach ($row in $clients.ListRows) {
            $reason = ([string]$row.Range.Cells.Item(1, $reasonIndex).Value2).Trim()
            if (-not $reason) { continue }
            $label = $reason
            if ($counts[$reason.ToLowerInvariant()] -gt 1) { $label += " [ID " + [string]$row.Range.Cells.Item(1, $idIndex).Value2 + "]" }
            if ([string]$row.Range.Cells.Item(1, $activeIndex).Value2 -ne "1") { $label += " (inactivo)" }
            $row.Range.Cells.Item(1, $labelIndex).Value2 = $label
            $row.Range.Cells.Item(1, $displayIndex).Value2 = $reason
        }
    }
    try { $workbook.Names.Item("llg_client_choices").Delete() } catch {}
    $lastClientRow = [Math]::Max(2, $clients.Range.Row + $clients.Range.Rows.Count - 1)
    $workbook.Names.Add("llg_client_choices", "='_Listas'!`$H`$2:`$H`$" + $lastClientRow) | Out-Null

    $ficha.Range("J4:O4").UnMerge()
    $ficha.Range("J4:O4").Merge()
    $ficha.Range("J4").Value = "CONFIGURACIÓN DEL PDF"
    $ficha.Range("J4:O4").Interior.Color = 6978327
    $ficha.Range("J4:O4").Font.Name = "Aptos"
    $ficha.Range("J4:O4").Font.Bold = $true
    $ficha.Range("J4:O4").Font.Color = 16777215
    $ficha.Range("J5:O5").UnMerge()
    $ficha.Range("J5:O5").Merge()
    $ficha.Range("J5").Value = "Aviso de confidencialidad (admite {DESTINATARIO})"
    $ficha.Range("J5:O5").Font.Name = "Aptos"
    $ficha.Range("J5:O5").Font.Size = 9
    $ficha.Range("J6:O9").UnMerge()
    $ficha.Range("J6:O9").Merge()
    if ([string]::IsNullOrWhiteSpace([string]$ficha.Range("J6").Value2)) {
        $ficha.Range("J6").Value = "Documento confidencial para uso exclusivo de {DESTINATARIO}. Prohibida su difusión sin autorización."
    }
    $ficha.Range("J6:O9").WrapText = $true
    $ficha.Range("J6:O9").VerticalAlignment = -4160
    $ficha.Range("J6:O9").Interior.Color = 16186879
    $ficha.Range("J6:O9").Borders.Color = 13621451
    $ficha.Columns("J:O").ColumnWidth = 11

    $ficha.Range("C7").Validation.Delete() | Out-Null
    $ficha.Range("C7").Validation.Add(3, 1, 1, "=llg_client_choices")
    $ficha.Range("C7").Validation.IgnoreBlank = $true
    $ficha.Range("C7").Validation.InCellDropdown = $true
    $ficha.Range("H64").Formula = "=SUM(H53:INDEX(H:H,ROW()-1))"
    $ficha.Range("H79").Formula = "=SUM(H68:INDEX(H:H,ROW()-1))"

    function Add-ActionButton {
        param($Sheet, [string]$Name, [string]$Caption, [string]$Macro, [string]$Cell, [double]$Width, [double]$Height = 24)
        $anchor = $Sheet.Range($Cell)
        $shape = $Sheet.Shapes.AddShape(5, $anchor.Left, $anchor.Top + 1, $Width, $Height)
        $shape.Name = $Name
        $shape.AlternativeText = "LlangonAction"
        $shape.OnAction = $Macro
        $shape.Fill.ForeColor.RGB = 2797114
        $shape.Line.ForeColor.RGB = 1547064
        $shape.TextFrame2.TextRange.Text = $Caption
        $shape.TextFrame2.TextRange.Font.Name = "Aptos"
        $shape.TextFrame2.TextRange.Font.Size = 9
        $shape.TextFrame2.TextRange.Font.Bold = -1
        $shape.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = 16777215
        $shape.TextFrame2.VerticalAnchor = 3
        $shape.TextFrame2.TextRange.ParagraphFormat.Alignment = 2
    }

    foreach ($shape in @($ficha.Shapes)) {
        if ($shape.AlternativeText -eq "LlangonAction") { $shape.Delete() }
    }
    Add-ActionButton $ficha "btnActualizarClientes" "Actualizar clientes" "UpdateClients" "J1" 118
    Add-ActionButton $ficha "btnImportarPlace" "Importar PLACE" "ImportPlace" "M1" 118
    Add-ActionButton $ficha "btnRevisarFicha" "Revisar ficha" "ReviewFichaAction" "J2" 118
    Add-ActionButton $ficha "btnPrepararPdf" "Preparar PDF" "PreparePDF" "M2" 118
    Add-ActionButton $ficha "btnAbrirInforme" "Abrir informe / PDF" "OpenLastPdfOrReport" "J3" 241

    foreach ($shape in @($informe.Shapes)) {
        if ($shape.AlternativeText -eq "LlangonAction") { $shape.Delete() }
    }
    Add-ActionButton $informe "btnVolverFicha" "Volver a Ficha" "VolverAFicha" "F4" 95
    Add-ActionButton $informe "btnFallbackPdf" "Exportar PDF Excel" "ExportFallbackExcel" "G4" 115

    $registry = @()
    foreach ($item in $manifest.scalar_fields) {
        $registry += ,@($item.logical_id, "name", $item.excel_name, $item.type, $item.owner, [int][bool]$item.required_final, [int][bool]$item.pdf)
    }
    foreach ($item in $manifest.ranges) {
        $registry += ,@($item.logical_id, "range", $item.excel_name, "collection", "document", 0, 1)
    }
    $registryTable = $tech.ListObjects.Item("tblFieldRegistry")
    $registryTable.Resize($tech.Range("D1:J" + ($registry.Count + 1)))
    $tech.Range("D2:J" + ($registry.Count + 1)).ClearContents()
    for ($index = 0; $index -lt $registry.Count; $index++) {
        for ($column = 0; $column -lt 7; $column++) {
            $tech.Cells.Item($index + 2, $column + 4).Value2 = [string]$registry[$index][$column]
        }
    }
    $tech.Range("B7").Value = [string]$manifest.template_version
    $tech.Range("B8").Value = [string]$manifest.payload_schema_version

    $ficha.PageSetup.PrintArea = "`$B`$1:`$H`$119"
    $ficha.PageSetup.Orientation = 1
    $ficha.PageSetup.PaperSize = 9
    $ficha.PageSetup.Zoom = $false
    $ficha.PageSetup.FitToPagesWide = 1
    $ficha.PageSetup.FitToPagesTall = $false
    $ficha.PageSetup.RightFooter = "Página &P de &N"
    $listas.Visible = 2
    $tech.Visible = 2
    $informe.Protect("", $true, $true, $true, $true) | Out-Null

    foreach ($propertyName in "LlangonTemplateId", "LlangonTemplateVersion", "LlangonPayloadVersion") {
        try { $workbook.CustomDocumentProperties.Item($propertyName).Delete() } catch {}
    }
    $workbook.SaveAs($outputPath, 52)
    $workbook.Close($true)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
    $workbook = $null
    $excel.AutomationSecurity = 1
    $workbook = $excel.Workbooks.Open($outputPath, 0, $false)
    $selfTests = @(
        "SelfTestCompile",
        "SelfTestPlaceParser",
        "SelfTestPlaceBridgeTsv",
        "SelfTestPlaceLongUrl"
    )
    foreach ($test in $selfTests) {
        $result = $excel.Run("'" + $workbook.Name + "'!" + $test)
        Write-Host ($test + ": " + [string]$result)
    }
    $workbook.Save()
} catch {
    Write-Host ("Línea de generación: " + $_.InvocationInfo.ScriptLineNumber)
    Write-Host $_.ScriptStackTrace
    Write-Host $_.Exception.ToString()
    throw
} finally {
    if ($null -ne $workbook) { try { $workbook.Close($false) } catch {} }
    if ($null -ne $excel) { try { $excel.Quit() } catch {} }
    if ($null -ne $workbook) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }
    if ($null -ne $excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

& $python $verifier --workbook $outputPath --repo-root $repoRoot
if ($LASTEXITCODE -ne 0) { throw "La verificación estática del XLSM no ha sido satisfactoria." }
