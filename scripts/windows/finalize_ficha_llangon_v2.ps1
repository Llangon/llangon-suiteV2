param(
    [Parameter(Mandatory = $true)][string]$BaseWorkbook,
    [Parameter(Mandatory = $true)][string]$OutputWorkbook,
    [switch]$SkipBridgeInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$basePath = (Resolve-Path $BaseWorkbook).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputWorkbook)
$outputDir = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$layoutPath = Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\workbook_layout.json"
$layout = Get-Content -LiteralPath $layoutPath -Raw -Encoding UTF8 | ConvertFrom-Json
$manifestPath = Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\field_manifest.json"
$templateVersion = [string](Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json).template_version
$macroDir = Join-Path $repoRoot "macros\ficha_llangon_v2"
$macroFiles = Get-ChildItem -LiteralPath $macroDir -Filter "*.bas" | Sort-Object Name
if ($macroFiles.Count -eq 0) { throw "No se encuentran las fuentes VBA." }
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$verifier = Join-Path $repoRoot "scripts\verify_ficha_llangon_v2.py"
$bridgeInstaller = Join-Path $repoRoot "scripts\windows\install_llangon_excel_bridge.ps1"
$completed = $false

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    Write-Host "Paso Excel 1/8: abrir libro base"
    $workbook = $excel.Workbooks.Open($basePath, 0, $false)

    try {
        Write-Host "Paso Excel 2/8: importar fuentes VBA"
        $project = $workbook.VBProject
        foreach ($macroFile in $macroFiles) {
            $component = $project.VBComponents.Add(1)
            $component.Name = [System.IO.Path]::GetFileNameWithoutExtension($macroFile.Name)
            $code = Get-Content -LiteralPath $macroFile.FullName -Raw -Encoding UTF8
            $component.CodeModule.AddFromString($code)
        }
    } catch {
        throw "Excel no permite importar las fuentes VBA. Active temporalmente 'Confiar en el acceso al modelo de objetos de proyectos de VBA' para reconstruir la plantilla. Detalle: $($_.Exception.Message)"
    }

    Write-Host "Paso Excel 3/8: crear nombres estables"
    foreach ($property in $layout.names.PSObject.Properties) {
        $name = $property.Name
        $reference = [string]$property.Value
        $parts = $reference.Split("!")
        $sheetName = $parts[0]
        $cellReference = $parts[1]
        Write-Host "  nombre: $name -> $sheetName!$cellReference"
        $workbook.Names.Add($name, "='" + $sheetName + "'!" + $cellReference) | Out-Null
    }
    Write-Host "  nombre: llg_client_choices"
    $workbook.Names.Add("llg_client_choices", "='_Listas'!`$H`$2:`$H`$2") | Out-Null

    $ficha = $workbook.Worksheets.Item("Ficha")
    $informe = $workbook.Worksheets.Item("Informe_PDF")
    $listas = $workbook.Worksheets.Item("_Listas")
    $tech = $workbook.Worksheets.Item("_Llangon")

    Write-Host "Paso Excel 4/8: fórmulas y validaciones"
    $ficha.Range("C68").Formula = "=SUM(tblCriteriosJuicio[Puntos])"
    $ficha.Range("C84").Formula = "=SUM(tblCriteriosFormula[Puntos])"
    $ficha.Range("F22").Formula = "=IF(F16="""",""Pendiente de fecha"",IF(F16<TODAY(),""AVISO: fecha vencida"",IF(WEEKDAY(F16,2)>5,""AVISO: fin de semana"",IF(COUNTIF(tblFestivos[Fecha],F16)>0,""AVISO: festivo registrado"",IF(F16<=TODAY()+3,""AVISO: plazo próximo"",""Fecha revisada"")))))"
    $ficha.Range("C45").Validation.Delete()
    $ficha.Range("C45").Validation.Add(1, 1, 7, 0)
    $ficha.Range("C45").Validation.IgnoreBlank = $true
    $ficha.Range("C10").Validation.Delete()
    $ficha.Range("C10").Validation.Add(3, 1, 1, "=llg_client_choices")
    $ficha.Range("C10").Validation.IgnoreBlank = $true
    $ficha.Range("C10").Validation.InCellDropdown = $true

    Write-Host "Paso Excel 5/8: vista y botones"
    $ficha.Activate()
    $excel.ActiveWindow.DisplayGridlines = $false
    $excel.ActiveWindow.Zoom = 90
    $excel.ActiveWindow.FreezePanes = $false
    $ficha.Range("B9").Select()
    $excel.ActiveWindow.FreezePanes = $true

    function Add-ActionButton {
        param($Sheet, [string]$Name, [string]$Caption, [string]$Macro, [double]$Left, [double]$Top, [double]$Width, [double]$Height = 27)
        $shape = $Sheet.Shapes.AddShape(5, $Left, $Top, $Width, $Height)
        $shape.Name = $Name
        $shape.AlternativeText = "LlangonAction"
        $shape.OnAction = $Macro
        $shape.Fill.ForeColor.RGB = 2797114
        $shape.Line.ForeColor.RGB = 1547064
        $shape.TextFrame2.TextRange.Text = $Caption
        $shape.TextFrame2.TextRange.Font.Name = "Aptos"
        $shape.TextFrame2.TextRange.Font.Size = 10
        $shape.TextFrame2.TextRange.Font.Bold = -1
        $shape.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = 16777215
        $shape.TextFrame2.VerticalAnchor = 3
        $shape.TextFrame2.TextRange.ParagraphFormat.Alignment = 2
        return $shape
    }

    foreach ($shape in @($ficha.Shapes)) {
        if ($shape.AlternativeText -eq "LlangonAction") { $shape.Delete() }
    }
    $buttonTop = $ficha.Range("B7").Top + 2
    $left = $ficha.Range("B7").Left
    $gap = 5
    $width = 103
    Add-ActionButton $ficha "btnActualizarClientes" "Actualizar clientes" "UpdateClients" $left $buttonTop $width | Out-Null
    Add-ActionButton $ficha "btnImportarPlace" "Importar PLACE" "ImportPlace" ($left + ($width + $gap)) $buttonTop $width | Out-Null
    Add-ActionButton $ficha "btnRevisarFicha" "Revisar ficha" "ReviewFichaAction" ($left + 2 * ($width + $gap)) $buttonTop $width | Out-Null
    Add-ActionButton $ficha "btnPrepararPdf" "Preparar PDF" "PreparePDF" ($left + 3 * ($width + $gap)) $buttonTop $width | Out-Null
    Add-ActionButton $ficha "btnAbrirInforme" "Abrir informe / PDF" "OpenLastPdfOrReport" ($left + 4 * ($width + $gap)) $buttonTop 125 | Out-Null
    Add-ActionButton $ficha "btnAddJuicio" "+ criterio de juicio" "AddJudgmentCriterion" $ficha.Range("F54").Left ($ficha.Range("F54").Top - 1) 115 20 | Out-Null
    Add-ActionButton $ficha "btnAddFormula" "+ criterio automático" "AddFormulaCriterion" $ficha.Range("F70").Left ($ficha.Range("F70").Top - 1) 115 20 | Out-Null

    Add-ActionButton $informe "btnVolverFicha" "Volver a Ficha" "VolverAFicha" $informe.Range("F4").Left $informe.Range("F4").Top 95 | Out-Null
    Add-ActionButton $informe "btnFallbackPdf" "Exportar PDF Excel" "ExportFallbackExcel" ($informe.Range("F4").Left + 100) $informe.Range("F4").Top 115 | Out-Null

    Write-Host "Paso Excel 6/8: impresión, protección y metadatos"
    $ficha.PageSetup.PrintArea = "`$B`$1:`$H`$111"
    $ficha.PageSetup.Orientation = 1
    $ficha.PageSetup.PaperSize = 9
    $ficha.PageSetup.Zoom = $false
    $ficha.PageSetup.FitToPagesWide = 1
    $ficha.PageSetup.FitToPagesTall = $false
    $ficha.PageSetup.LeftMargin = $excel.CentimetersToPoints(1.2)
    $ficha.PageSetup.RightMargin = $excel.CentimetersToPoints(1.2)
    $ficha.PageSetup.TopMargin = $excel.CentimetersToPoints(1.3)
    $ficha.PageSetup.BottomMargin = $excel.CentimetersToPoints(1.3)
    $ficha.PageSetup.RightFooter = "Página &P de &N"

    $informe.Protect("", $true, $true, $true, $true)
    $listas.Visible = 2
    $tech.Visible = 2

    try {
        $custom = $workbook.CustomDocumentProperties
        $custom.Add("LlangonTemplateId", $false, 4, "ficha_llangon") | Out-Null
        $custom.Add("LlangonTemplateVersion", $false, 4, $templateVersion) | Out-Null
        $custom.Add("LlangonPayloadVersion", $false, 4, "1.0") | Out-Null
    } catch {
        # Named metadata remains authoritative if Office blocks custom properties.
    }

    Write-Host "Paso Excel 7/8: guardar XLSM y ejecutar autocomprobaciones"
    $workbook.SaveAs($outputPath, 52)
    $compileResult = $excel.Run("'" + $workbook.Name + "'!SelfTestCompile")
    if ($compileResult -notlike ("Ficha Llangon " + $templateVersion + "*")) { throw "La autocomprobación VBA no devolvió el resultado esperado." }
    $placeResult = $excel.Run("'" + $workbook.Name + "'!SelfTestPlaceParser")
    if ($placeResult -notlike "OK:*") { throw "La autocomprobación PLACE VBA no devolvió el resultado esperado." }
    $placeBridgeResult = $excel.Run("'" + $workbook.Name + "'!SelfTestPlaceBridgeTsv")
    if ($placeBridgeResult -notlike "OK:*") { throw "La autocomprobación del contrato bridge PLACE no devolvió el resultado esperado." }
    $workbook.Save()
    $completed = $true
    Write-Host "Plantilla finalizada: $outputPath"
    Write-Host "Autocomprobación VBA: $compileResult"
    Write-Host "Autocomprobación PLACE: $placeResult"
    Write-Host "Autocomprobación bridge PLACE: $placeBridgeResult"
} finally {
    if ($workbook -ne $null) { try { $workbook.Close($false) } catch {} }
    if ($excel -ne $null) { try { $excel.Quit() } catch {} }
    if ($workbook -ne $null) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }
    if ($excel -ne $null) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

if ($completed) {
    Write-Host "Paso Excel 8/8: verificar paquete XLSM"
    & $python $verifier --workbook $outputPath --repo-root $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "La verificación estática del XLSM no ha sido satisfactoria." }
    if (-not $SkipBridgeInstall) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bridgeInstaller
        if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar el componente local requerido por la ficha." }
    }
}
