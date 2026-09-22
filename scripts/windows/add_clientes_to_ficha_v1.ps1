param(
    [Parameter(Mandatory = $true)][string]$SourceWorkbook,
    [Parameter(Mandatory = $true)][string]$OutputWorkbook
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourcePath = (Resolve-Path $SourceWorkbook).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputWorkbook)
$outputDir = Split-Path -Parent $outputPath
$modulePath = Join-Path $repoRoot "macros\ficha_v1\modClientesSuite.bas"
$existingExcelIds = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Get-SheetSignature {
    param($Sheet)
    $used = $Sheet.UsedRange
    $cells = New-Object System.Collections.Generic.List[string]
    $mergeSet = @{}
    foreach ($cell in @($used.Cells)) {
        $cells.Add(($cell.Address() + "|" + [string]$cell.FormulaR1C1 + "|" + [string]$cell.Value2 + "|" + [string]$cell.NumberFormat + "|" + [string]$cell.Interior.Color + "|" + [string]$cell.Font.Color + "|" + [string]$cell.Font.Bold))
        if ($cell.MergeCells) { $mergeSet[$cell.MergeArea.Address()] = $true }
    }
    $shapes = @($Sheet.Shapes | ForEach-Object { $_.Name + "|" + $_.OnAction + "|" + $_.AlternativeText }) -join ";"
    $rows = @($used.Rows | ForEach-Object { $_.Row.ToString() + "=" + $_.RowHeight }) -join ";"
    $columns = @($used.Columns | ForEach-Object { $_.Column.ToString() + "=" + $_.ColumnWidth }) -join ";"
    $used.Address() + "`n" + ($cells -join "`n") + "`nMERGES=" + (($mergeSet.Keys | Sort-Object) -join ";") + "`nSHAPES=" + $shapes + "`nROWS=" + $rows + "`nCOLS=" + $columns + "`nPRINT=" + $Sheet.PageSetup.PrintArea
}

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $workbook = $excel.Workbooks.Open($sourcePath, 0, $false)

    if ($workbook.Worksheets.Count -ne 2 -or $workbook.Worksheets.Item(1).Name -ne "Ficha" -or $workbook.Worksheets.Item(2).Name -ne "Datos") {
        throw "La plantilla no contiene exclusivamente las hojas Ficha y Datos en el orden esperado."
    }
    $fichaBefore = Get-SheetSignature $workbook.Worksheets.Item("Ficha")
    $datosBefore = Get-SheetSignature $workbook.Worksheets.Item("Datos")

    $missing = [Type]::Missing
    $clientes = $workbook.Worksheets.Add($missing, $workbook.Worksheets.Item("Datos"), 1, $missing)
    $clientes.Name = "Clientes"
    $clientes.Tab.Color = 5287936
    $clientes.Range("A1:G7").Font.Name = "Arial"
    $clientes.Range("A1:G7").Font.Size = 10
    $clientes.Range("A1:G1").Merge()
    $clientes.Range("A1").Value2 = "CLIENTES · LLANGON SUITE"
    $clientes.Range("A1:G1").Interior.Color = 5287936
    $clientes.Range("A1:G1").Font.Color = 16777215
    $clientes.Range("A1:G1").Font.Bold = $true
    $clientes.Range("A1:G1").Font.Size = 14
    $clientes.Range("A1:G1").HorizontalAlignment = -4108
    $clientes.Rows.Item(1).RowHeight = 27

    $clientes.Range("A2").Value2 = "Última actualización"
    $clientes.Range("B2:C2").Merge()
    $clientes.Range("D2").Value2 = "Estado"
    $clientes.Range("E2:G2").Merge()
    $clientes.Range("A2").Font.Bold = $true
    $clientes.Range("D2").Font.Bold = $true
    $clientes.Range("A2").Interior.Color = 13434828
    $clientes.Range("D2").Interior.Color = 13434828
    $clientes.Range("B2:C2").Interior.Color = 15921906
    $clientes.Range("E2:G2").Interior.Color = 15921906
    $clientes.Range("A2:G2").Borders.Color = 10921638

    $clientes.Range("D4:G4").Merge()
    $clientes.Range("D4").Value2 = "Consulta de solo lectura. La tabla adopta automáticamente cualquier campo nuevo que se añada a los clientes de la Suite."
    $clientes.Range("D4:G4").Font.Italic = $true
    $clientes.Range("D4:G4").Font.Color = 6579300
    $clientes.Range("D4:G4").WrapText = $true

    $headers = @("id", "label", "display_name", "razon_social", "nombre_comercial", "active", "updated_at")
    for ($column = 1; $column -le 7; $column++) {
        $clientes.Cells.Item(6, $column).Value2 = $headers[$column - 1]
    }
    $table = $clientes.ListObjects.Add(1, $clientes.Range("A6:G7"), $null, 1)
    $table.Name = "tblClientes"
    $table.TableStyle = "TableStyleMedium4"
    $table.DataBodyRange.ClearContents()
    $clientes.Columns.Item("A").ColumnWidth = 11
    $clientes.Columns.Item("B").ColumnWidth = 42
    $clientes.Columns.Item("C").ColumnWidth = 28
    $clientes.Columns.Item("D").ColumnWidth = 36
    $clientes.Columns.Item("E").ColumnWidth = 28
    $clientes.Columns.Item("F").ColumnWidth = 10
    $clientes.Columns.Item("G").ColumnWidth = 22
    $clientes.Range("A:G").VerticalAlignment = -4108
    $clientes.Range("A6:G7").WrapText = $false
    $clientes.Activate() | Out-Null
    $excel.ActiveWindow.DisplayGridlines = $false
    $excel.ActiveWindow.FreezePanes = $false
    $clientes.Range("A7").Select() | Out-Null
    $excel.ActiveWindow.FreezePanes = $true

    $button = $clientes.Shapes.AddShape(5, $clientes.Range("A4").Left, $clientes.Range("A4").Top, 190, 25)
    $button.Name = "btnActualizarClientes"
    $button.AlternativeText = "Actualizar catálogo de clientes desde Llangon Suite"
    $button.OnAction = "ActualizarClientes"
    $button.Placement = 1
    $button.Fill.ForeColor.RGB = 5287936
    $button.Line.ForeColor.RGB = 2773495
    $button.TextFrame2.TextRange.Text = "ACTUALIZAR CLIENTES"
    $button.TextFrame2.TextRange.Font.Name = "Arial"
    $button.TextFrame2.TextRange.Font.Size = 10
    $button.TextFrame2.TextRange.Font.Bold = -1
    $button.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = 16777215
    $button.TextFrame2.TextRange.ParagraphFormat.Alignment = 2
    $button.TextFrame2.VerticalAnchor = 3

    try { $workbook.Names.Item("ListaClientes").Delete() } catch {}
    $workbook.Names.Add("ListaClientes", "='Clientes'!`$B`$7:`$B`$7") | Out-Null
    $component = $workbook.VBProject.VBComponents.Add(1)
    $component.Name = "modClientesSuite"
    $component.CodeModule.AddFromString((Get-Content -LiteralPath $modulePath -Raw -Encoding UTF8))

    $fichaAfter = Get-SheetSignature $workbook.Worksheets.Item("Ficha")
    $datosAfter = Get-SheetSignature $workbook.Worksheets.Item("Datos")
    if ($fichaAfter -ne $fichaBefore) {
        Write-Output ((Compare-Object ($fichaBefore -split "`n") ($fichaAfter -split "`n") | Select-Object -First 12 | Out-String))
        throw "La hoja Ficha cambió durante la incorporación de Clientes."
    }
    if ($datosAfter -ne $datosBefore) {
        Write-Output ((Compare-Object ($datosBefore -split "`n") ($datosAfter -split "`n") | Select-Object -First 12 | Out-String))
        throw "La hoja Datos cambió durante la incorporación de Clientes."
    }

    $workbook.SaveAs($outputPath, 52)
    $workbook.Close($true)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
    $workbook = $null

    $excel.AutomationSecurity = 1
    $workbook = $excel.Workbooks.Open($outputPath, 0, $false)
    $result = $excel.Run("'" + $workbook.Name + "'!SelfTestClientesSuite")
    Write-Output ("SelfTestClientesSuite: " + [string]$result)
    if ((Get-SheetSignature $workbook.Worksheets.Item("Ficha")) -ne $fichaBefore) { throw "La prueba alteró la hoja Ficha." }
    if ((Get-SheetSignature $workbook.Worksheets.Item("Datos")) -ne $datosBefore) { throw "La prueba alteró la hoja Datos." }
    # La prueba se ejecuta en memoria y se descarta para entregar una tabla vacía y prístina.
    $workbook.Close($false)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
    $workbook = $null

    $excel.AutomationSecurity = 3
    $workbook = $excel.Workbooks.Open($outputPath, 0, $true)
    $clientSheet = $workbook.Worksheets.Item("Clientes")
    if ($clientSheet.ListObjects.Count -ne 1) { throw "La tabla de clientes no persiste después de reabrir el libro." }
    if ($clientSheet.ListObjects.Item("tblClientes").ListRows.Count -gt 0) {
        if ($excel.WorksheetFunction.CountA($clientSheet.ListObjects.Item("tblClientes").DataBodyRange) -ne 0) { throw "La tabla entregable contiene datos de prueba." }
    }
    if ($clientSheet.Shapes.Item("btnActualizarClientes").OnAction -ne "ActualizarClientes") { throw "El botón no está vinculado a la actualización de clientes." }
} catch {
    Write-Output ("Línea de generación: " + $_.InvocationInfo.ScriptLineNumber)
    Write-Output $_.Exception.Message
    throw
} finally {
    if ($null -ne $workbook) { try { $workbook.Close($false) } catch {} }
    if ($null -ne $excel) { try { $excel.Quit() } catch {} }
    if ($null -ne $workbook) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }
    if ($null -ne $excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Start-Sleep -Milliseconds 500
Get-Process EXCEL -ErrorAction SilentlyContinue | Where-Object {
    $_.Id -notin $existingExcelIds -and $_.MainWindowHandle -eq 0
} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Output ("Generado: " + $outputPath)
