param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [string]$EvidenceDirectory,
    [string]$ReportPath,
    [string]$PlaceAcceptanceUrl = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=DX08KX8uP257h85%2Fpmmsfw%3D%3D"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourceWorkbook = (Resolve-Path $Workbook).Path
if ([System.IO.Path]::GetExtension($sourceWorkbook) -ne ".xlsm") { throw "La prueba requiere un XLSM." }
if (-not $EvidenceDirectory) { $EvidenceDirectory = Join-Path $repoRoot "output\pdf\ficha_llangon_v2" }
if (-not $ReportPath) { $ReportPath = Join-Path $repoRoot "output\ficha_llangon_v2_excel_acceptance.json" }
$evidenceDirectoryPath = [System.IO.Path]::GetFullPath($EvidenceDirectory)
$reportPathValue = [System.IO.Path]::GetFullPath($ReportPath)
New-Item -ItemType Directory -Path $evidenceDirectoryPath -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $reportPathValue) -Force | Out-Null

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-UniquePath {
    param([string]$Requested)
    if (-not (Test-Path -LiteralPath $Requested)) { return $Requested }
    $directory = Split-Path -Parent $Requested
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($Requested)
    $extension = [System.IO.Path]::GetExtension($Requested)
    for ($revision = 2; $revision -lt 1000; $revision++) {
        $candidate = Join-Path $directory ($stem + "_r" + $revision + $extension)
        if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw "No se pudo determinar un nombre de evidencia libre."
}

function Get-NamedRange {
    param($Book, [string]$Name)
    return $Book.Names.Item($Name).RefersToRange
}

function Set-NamedValue {
    param($Book, [string]$Name, $Value)
    $targetRange = Get-NamedRange $Book $Name
    $targetRange.Value2 = $Value
}

function Set-NamedFormula {
    param($Book, [string]$Name, [string]$Formula)
    $targetRange = Get-NamedRange $Book $Name
    $targetRange.Formula = $Formula
}

function Get-UsedText {
    param($Sheet)
    $values = $Sheet.UsedRange.Value2
    if ($values -is [System.Array]) {
        $parts = New-Object System.Collections.Generic.List[string]
        for ($row = $values.GetLowerBound(0); $row -le $values.GetUpperBound(0); $row++) {
            for ($column = $values.GetLowerBound(1); $column -le $values.GetUpperBound(1); $column++) {
                $cellValue = $values.GetValue($row, $column)
                if ($null -ne $cellValue) { [void]$parts.Add([string]$cellValue) }
            }
        }
        return [string]::Join("`n", $parts)
    }
    return [string]$values
}

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
$testRoot = Join-Path $tempBase ("LlangonFichaExcelAcceptance_" + [Guid]::NewGuid().ToString("N"))
$testWorkbook = Join-Path $testRoot "Ficha_Llangon_v2_acceptance.xlsm"
$payloadPath = Join-Path $testRoot "payload.json"
$resultPath = Join-Path $testRoot "render.result.tsv"
$fallbackPdf = Get-UniquePath (Join-Path $evidenceDirectoryPath "Ficha_Llangon_v2_fallback_Excel_COM.pdf")
$reportLabPdf = Get-UniquePath (Join-Path $evidenceDirectoryPath "Ficha_Llangon_v2_payload_Excel_COM.pdf")
$sourceHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceWorkbook).Hash
$bridgeInstaller = Join-Path $repoRoot "scripts\windows\install_llangon_excel_bridge.ps1"
$installedBridge = Join-Path $env:LOCALAPPDATA "LlangonSuite\bridge\llangon-excel-bridge.cmd"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$previousBridge = $env:LLANGON_EXCEL_BRIDGE
$previousBridgeDisable = $env:LLANGON_EXCEL_BRIDGE_DISABLE
$excel = $null
$book = $null
$checks = New-Object System.Collections.Generic.List[string]
$result = $null

New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
Copy-Item -LiteralPath $sourceWorkbook -Destination $testWorkbook
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bridgeInstaller | Out-Null
Assert-True ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $installedBridge)) "No se pudo instalar el bridge local para la prueba de aceptación."
$env:LLANGON_EXCEL_BRIDGE = ""
$env:LLANGON_EXCEL_BRIDGE_DISABLE = "1"

try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $true
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 1
    $excelVersion = [string]$excel.Version
    $book = $excel.Workbooks.Open($testWorkbook, 0, $false)
    $checks.Add("apertura real en Excel")

    $expectedSheets = @("Ficha", "Informe_PDF", "_Listas", "_Llangon")
    foreach ($sheetName in $expectedSheets) { Assert-True ($null -ne $book.Worksheets.Item($sheetName)) "Falta la hoja $sheetName." }
    $ficha = $book.Worksheets.Item("Ficha")
    $informe = $book.Worksheets.Item("Informe_PDF")
    $listas = $book.Worksheets.Item("_Listas")
    $tech = $book.Worksheets.Item("_Llangon")
    Assert-True ($listas.Visible -eq 2 -and $tech.Visible -eq 2) "Las hojas técnicas no están VeryHidden."
    Assert-True ([bool]$informe.ProtectContents) "Informe_PDF no está protegido."
    $checks.Add("estructura, VeryHidden y protecci" + [char]0x00F3 + "n")

    $clientTable = $listas.ListObjects.Item("tblClientes")
    $clientText = ""
    if ($null -ne $clientTable.DataBodyRange) { $clientText = [string](Get-UsedText $clientTable.DataBodyRange.Worksheet) }
    Assert-True ([string]::IsNullOrWhiteSpace([string](Get-NamedRange $book "llg_control_clients_updated_at").Value2)) "Abrir el libro alteró la fecha de clientes."
    Assert-True ($clientTable.ListRows.Count -eq 1) "La plantilla maestra no contiene la única fila técnica esperada."
    $masterClientRow = $clientTable.ListRows.Item(1).Range
    Assert-True ([double]$masterClientRow.Cells(1, 1).Value2 -eq 0) "La fila técnica de clientes tiene un ID inesperado."
    Assert-True ([double]$masterClientRow.Cells(1, 6).Value2 -eq 0) "La fila técnica de clientes tiene un estado inesperado."
    foreach ($column in @(2, 3, 4, 5, 7)) {
        Assert-True ([string]::IsNullOrWhiteSpace([string]$masterClientRow.Cells(1, $column).Value2)) "La plantilla maestra contiene datos reales en la caché."
    }
    $checks.Add("apertura sin consulta ni actualizaci" + [char]0x00F3 + "n de clientes")

    $buttonMap = [ordered]@{
        btnActualizarClientes = "UpdateClients"
        btnImportarPlace = "ImportPlace"
        btnRevisarFicha = "ReviewFichaAction"
        btnPrepararPdf = "PreparePDF"
        btnAbrirInforme = "OpenLastPdfOrReport"
        btnAddJuicio = "AddJudgmentCriterion"
        btnAddFormula = "AddFormulaCriterion"
    }
    foreach ($entry in $buttonMap.GetEnumerator()) {
        $shape = $ficha.Shapes.Item($entry.Key)
        Assert-True ([string]$shape.OnAction -like ("*" + $entry.Value + "*")) "El botón $($entry.Key) no llama a $($entry.Value)."
    }
    Assert-True ([string]$informe.Shapes.Item("btnVolverFicha").OnAction -like "*VolverAFicha*") "Falta el botón de vuelta."
    Assert-True ([string]$informe.Shapes.Item("btnFallbackPdf").OnAction -like "*ExportFallbackExcel*") "Falta el botón de fallback."
    $checks.Add("botones y acciones VBA")

    $macroPrefix = "'" + $book.Name + "'!"
    $compile = [string]$excel.Run($macroPrefix + "SelfTestCompile")
    Assert-True ($compile -like "Ficha Llangon 2.0.1*") "La autocomprobación VBA no devolvió la versión esperada."
    $cacheTest = [string]$excel.Run($macroPrefix + "SelfTestClientCache")
    Assert-True ($cacheTest -like "OK:*") "Falló la prueba de caché VBA."
    $placeTest = [string]$excel.Run($macroPrefix + "SelfTestPlaceParser")
    Assert-True ($placeTest -like "OK:*") "Falló la prueba PLACE VBA."
    $placeBridgeTest = [string]$excel.Run($macroPrefix + "SelfTestPlaceBridgeTsv")
    Assert-True ($placeBridgeTest -like "OK:*") "Falló la prueba del contrato bridge PLACE."
    Assert-True ([string]::IsNullOrWhiteSpace([string]$excel.Run($macroPrefix + "ResolveBridgePath"))) "El modo offline localizó un bridge inesperado."
    $checks.Add("VBA compilado, cach" + [char]0x00E9 + " sint" + [char]0x00E9 + "tica, PLACE local/bridge y modo offline")

    # The synthetic cache self-test deliberately resizes the technical table.
    # Discard that Excel session so the rest of the acceptance starts from an
    # untouched copy of the master workbook.
    $book.Close($false)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)
    $book = $null

    # Exercise the actual client-button core with the installed bridge and the
    # production catalogue in strict read-only mode. The workbook copy is then
    # discarded without saving, so no real client data reaches the template.
    $excel.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    $excel = $null
    $env:LLANGON_EXCEL_BRIDGE_DISABLE = ""
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $true
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 1
    $book = $excel.Workbooks.Open($testWorkbook, 0, $false)
    $macroPrefix = "'" + $book.Name + "'!"
    $resolvedBridge = [string]$excel.Run($macroPrefix + "ResolveBridgePath")
    Assert-True ($resolvedBridge -eq $installedBridge) "La ficha no resolvió el bridge instalado."
    $dbPath = [string](& $python -c "from webapp.infonalia_webapp.tender_documents.client_reader import default_db_path; print(default_db_path())")
    $dbPath = $dbPath.Trim()
    Assert-True (Test-Path -LiteralPath $dbPath) "No se encuentra la base real de clientes para la prueba de solo lectura."
    $dbHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $dbPath).Hash
    $refreshedClients = [int]$excel.Run($macroPrefix + "RefreshClients", $false)
    Assert-True ($refreshedClients -gt 0) "Actualizar clientes no devolvió ningún cliente real."
    $liveClientTable = $book.Worksheets.Item("_Listas").ListObjects.Item("tblClientes")
    Assert-True ($liveClientTable.ListRows.Count -eq $refreshedClients) "La tabla no coincide con el catálogo devuelto por el bridge."
    Assert-True (-not [string]::IsNullOrWhiteSpace([string](Get-NamedRange $book "llg_control_clients_updated_at").Value2)) "Actualizar clientes no registró la fecha de actualización."
    Assert-True ([string](Get-NamedRange $book "llg_control_bridge_version").Value2 -eq "1.1.0") "La ficha no registró la versión esperada del bridge."
    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $dbPath).Hash -eq $dbHashBefore) "La lectura de clientes alteró la base SQLite real."
    $checks.Add("Actualizar clientes real mediante bridge instalado y SQLite intacta")

    $importedPlaceFields = [int]$excel.Run($macroPrefix + "ImportPlaceSource", $PlaceAcceptanceUrl, $false)
    $placeImportError = [string]$excel.Run($macroPrefix + "PlaceImportLastError")
    Assert-True ($importedPlaceFields -ge 8) ("Importar PLACE devolvió pocos campos en la prueba remota real. " + $placeImportError)
    Assert-True ([string](Get-NamedRange $book "llg_tender_expediente").Value2 -eq "0012-19pse") "Importar PLACE no escribió el expediente esperado."
    Assert-True ([string](Get-NamedRange $book "llg_tender_tipo_contrato").Value2 -eq "Servicios") "Importar PLACE no escribió el tipo de contrato esperado."
    Assert-True ([string](Get-NamedRange $book "llg_tender_procedimiento").Value2 -eq "Abierto") "Importar PLACE no escribió el procedimiento esperado."
    Assert-True ([string](Get-NamedRange $book "llg_source_place").Value2 -eq $PlaceAcceptanceUrl) "Importar PLACE no conservó la URL de origen."
    $checks.Add("Importar PLACE real desde p" + [char]0x00E1 + "gina p" + [char]0x00FA + "blica, XML oficial y escritura de campos")
    $book.Close($false)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)
    $book = $null

    # Resume the rest of the acceptance from an untouched workbook copy.
    $book = $excel.Workbooks.Open($testWorkbook, 0, $false)
    $ficha = $book.Worksheets.Item("Ficha")
    $informe = $book.Worksheets.Item("Informe_PDF")
    $listas = $book.Worksheets.Item("_Listas")
    $tech = $book.Worksheets.Item("_Llangon")
    $macroPrefix = "'" + $book.Name + "'!"

    $acceptanceOrganisation = "Organismo Ficticio de Aceptaci" + [char]0x00F3 + "n"
    $automaticCriterion = "Criterio autom" + [char]0x00E1 + "tico ficticio ampliado"
    $dynamicDescription = "Segunda prueba de crecimiento din" + [char]0x00E1 + "mico."
    $acceptanceObservation = "Datos completamente ficticios para aceptaci" + [char]0x00F3 + "n automatizada."

    Set-NamedValue $book "llg_recipient_client_display" "Cliente Ficticio COM, S.L."
    Set-NamedValue $book "llg_recipient_client_id" "990001"
    Set-NamedValue $book "llg_recipient_razon_social" "Cliente Ficticio COM, S.L."
    Set-NamedValue $book "llg_recipient_client_active" "true"
    Set-NamedValue $book "llg_tender_expediente" "EXP-FICTICIO-COM-001"
    Set-NamedValue $book "llg_tender_objeto" "Servicio ficticio para prueba real de Excel"
    Set-NamedValue $book "llg_tender_fecha_limite" "15/10/2030"
    Set-NamedFormula $book "llg_tender_hora_limite" "=TIME(14,0,0)"
    Set-NamedValue $book "llg_tender_enlace" "https://contrataciondelestado.es/ejemplo-ficticio"
    Set-NamedValue $book "llg_tender_organismo" $acceptanceOrganisation
    Set-NamedValue $book "llg_tender_plataforma" "PLACE"
    Set-NamedValue $book "llg_tender_tipo_contrato" "Servicios"
    Set-NamedValue $book "llg_tender_procedimiento" "Abierto"
    Set-NamedValue $book "llg_tender_presupuesto_base" "25000"
    Set-NamedValue $book "llg_tender_valor_estimado" "50000"
    Set-NamedValue $book "llg_analysis_plazo" "12 meses"
    Set-NamedValue $book "llg_analysis_observaciones" $acceptanceObservation

    $criteria = $ficha.ListObjects.Item("tblCriteriosJuicio")
    $rowsBefore = $criteria.ListRows.Count
    $excel.Run($macroPrefix + "AddJudgmentCriterion") | Out-Null
    $criterionRow = $criteria.ListRows.Item($criteria.ListRows.Count)
    $criterionRow.Range.Cells(1, $criteria.ListColumns.Item("Orden").Index).Value2 = [string]($rowsBefore + 1)
    $criterionRow.Range.Cells(1, $criteria.ListColumns.Item("Criterio").Index).Value2 = "Criterio ficticio ampliado"
    $criterionRow.Range.Cells(1, $criteria.ListColumns.Item("Descripcion").Index).Value2 = "Prueba de crecimiento de tabla estructurada."
    $criterionRow.Range.Cells(1, $criteria.ListColumns.Item("Puntos").Index).Value2 = "100"
    Assert-True ($criteria.ListRows.Count -eq $rowsBefore + 1) "La tabla de criterios no se amplió."
    $excel.CalculateFull()
    $judgmentTotalRow = $criteria.Range.Row + $criteria.Range.Rows.Count
    Assert-True ([math]::Abs([double]$ficha.Cells($judgmentTotalRow, 3).Value2 - 100.0) -lt 0.001) "La suma de criterios no se actualizó."

    $formulaCriteria = $ficha.ListObjects.Item("tblCriteriosFormula")
    $formulaRowsBefore = $formulaCriteria.ListRows.Count
    $excel.Run($macroPrefix + "AddFormulaCriterion") | Out-Null
    $formulaCriterionRow = $formulaCriteria.ListRows.Item($formulaCriteria.ListRows.Count)
    $formulaCriterionRow.Range.Cells(1, $formulaCriteria.ListColumns.Item("Orden").Index).Value2 = [string]($formulaRowsBefore + 1)
    $formulaCriterionRow.Range.Cells(1, $formulaCriteria.ListColumns.Item("Criterio").Index).Value2 = $automaticCriterion
    $formulaCriterionRow.Range.Cells(1, $formulaCriteria.ListColumns.Item("Descripcion").Index).Value2 = $dynamicDescription
    $formulaCriterionRow.Range.Cells(1, $formulaCriteria.ListColumns.Item("Puntos").Index).Value2 = "0"
    $formulaCriterionRow.Range.Cells(1, $formulaCriteria.ListColumns.Item("FormulaTexto").Index).Value2 = "P = 0 en esta prueba"
    Assert-True ($formulaCriteria.ListRows.Count -eq $formulaRowsBefore + 1) "La tabla de criterios automáticos no se amplió."
    $errors = [int]$excel.Run($macroPrefix + "ReviewFicha", $false)
    $reviewDetail = [string]$excel.Run($macroPrefix + "ReviewFichaLastMessage")
    Assert-True ($errors -eq 0) ("Revisar ficha devolvió errores para el caso ficticio completo: " + $reviewDetail)
    $checks.Add("criterios ampliables, suma y Revisar ficha")

    $payload = [string]$excel.Run($macroPrefix + "BuildFichaPayloadJson", $false)
    $parsedPayload = $payload | ConvertFrom-Json
    Assert-True ($parsedPayload.tender.expediente -eq "EXP-FICTICIO-COM-001") "El payload no conserva el expediente."
    Assert-True ($parsedPayload.tender.organismo -eq $acceptanceOrganisation) "El payload no conserva correctamente los caracteres Unicode."
    Assert-True ($parsedPayload.analysis.criterios_juicio.Count -eq 1) "El payload no conserva el criterio ampliado."
    Assert-True ($parsedPayload.analysis.criterios_formula.Count -eq 1) "El payload no conserva el criterio automático ampliado."
    [System.IO.File]::WriteAllText($payloadPath, $payload, [System.Text.UTF8Encoding]::new($false))
    $excel.Run($macroPrefix + "RefreshInformePDF") | Out-Null
    Assert-True ((Get-UsedText $informe) -like "*EXP-FICTICIO-COM-001*") "Informe_PDF no se regeneró desde los datos de Ficha."
    $informe.Shapes.Item("btnVolverFicha").Visible = $false
    $informe.Shapes.Item("btnFallbackPdf").Visible = $false
    $informe.ExportAsFixedFormat(0, $fallbackPdf, 0, $true, $false)
    $informe.Shapes.Item("btnVolverFicha").Visible = $true
    $informe.Shapes.Item("btnFallbackPdf").Visible = $true
    Assert-True ((Get-Item -LiteralPath $fallbackPdf).Length -gt 1000) "Excel no generó el PDF de fallback."
    $checks.Add("payload JSON e Informe_PDF derivado con fallback real")

    $book.Save()
    $book.Close($false)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)
    $book = $excel.Workbooks.Open($testWorkbook, 0, $false)
    Assert-True ([string](Get-NamedRange $book "llg_tender_expediente").Value2 -eq "EXP-FICTICIO-COM-001") "El guardado/reapertura perdió datos."
    Assert-True ($book.Worksheets.Item("Ficha").ListObjects.Item("tblCriteriosJuicio").ListRows.Count -eq $rowsBefore + 1) "La reapertura perdió la ampliación de criterios."
    Assert-True ($book.Worksheets.Item("Ficha").ListObjects.Item("tblCriteriosFormula").ListRows.Count -eq $formulaRowsBefore + 1) "La reapertura perdió la ampliación de criterios automáticos."
    $reopenedClientTable = $book.Worksheets.Item("_Listas").ListObjects.Item("tblClientes")
    Assert-True ($reopenedClientTable.ListRows.Count -eq 1) "La prueba de caché no restauró la tabla maestra."
    Assert-True ([string]::IsNullOrWhiteSpace([string]$reopenedClientTable.ListRows.Item(1).Range.Cells(1, 2).Value2)) "La prueba de caché dejó una etiqueta ficticia en el maestro de prueba."
    $compileAfterReopen = [string]$excel.Run(("'" + $book.Name + "'!SelfTestCompile"))
    Assert-True ($compileAfterReopen -like "Ficha Llangon 2.0.1*") "Las macros no funcionan tras reabrir."
    $checks.Add("guardado y reapertura real")
    $book.Close($false)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)
    $book = $null
    $excel.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    $excel = $null

    $bridge = Join-Path $repoRoot "scripts\windows\llangon_excel_bridge.cmd"
    & $bridge render-pdf --input $payloadPath --output $reportLabPdf --result $resultPath
    $bridgeExitCode = $LASTEXITCODE
    $bridgeResult = if (Test-Path -LiteralPath $resultPath) { Get-Content -LiteralPath $resultPath -Raw } else { "sin resultado" }
    Assert-True ($bridgeExitCode -eq 0) ("El bridge no generó el PDF desde el payload producido por Excel. Código " + $bridgeExitCode + ": " + $bridgeResult)
    Assert-True ((Get-Item -LiteralPath $reportLabPdf).Length -gt 1000) "El PDF ReportLab producido desde Excel no es válido."
    $checks.Add("Preparar PDF: payload Excel a bridge ReportLab")

    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $sourceWorkbook).Hash -eq $sourceHashBefore) "La prueba modificó la plantilla maestra."
    $checks.Add("plantilla maestra intacta durante la aceptaci" + [char]0x00F3 + "n")
    $result = [ordered]@{
        status = "ok"
        workbook = $sourceWorkbook
        excel_version = [string]$excelVersion
        checks = @($checks)
        fallback_pdf = $fallbackPdf
        reportlab_pdf = $reportLabPdf
        source_sha256 = $sourceHashBefore
    }
} finally {
    if ($book -ne $null) { try { $book.Close($false) } catch {}; [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book) }
    if ($excel -ne $null) { try { $excel.Quit() } catch {}; [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    $env:LLANGON_EXCEL_BRIDGE = $previousBridge
    $env:LLANGON_EXCEL_BRIDGE_DISABLE = $previousBridgeDisable
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    $resolvedTestRoot = [System.IO.Path]::GetFullPath($testRoot)
    Assert-True ($resolvedTestRoot.StartsWith($tempBase + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) "La carpeta temporal está fuera del directorio temporal del sistema."
    if (Test-Path -LiteralPath $resolvedTestRoot) {
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            try { Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force -ErrorAction Stop; break }
            catch { if ($attempt -lt 5) { Start-Sleep -Milliseconds 300 } }
        }
    }
}

if ($null -eq $result) { throw "La prueba de aceptación no produjo resultado." }
$json = $result | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($reportPathValue, $json, [System.Text.UTF8Encoding]::new($false))
Write-Output $json
