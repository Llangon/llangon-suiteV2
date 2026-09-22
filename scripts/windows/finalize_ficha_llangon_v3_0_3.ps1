param(
    [Parameter(Mandatory = $true)][string]$SourceWorkbook,
    [Parameter(Mandatory = $true)][string]$OutputWorkbook,
    [Parameter(Mandatory = $true)][string]$AcceptanceXml
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourcePath = (Resolve-Path $SourceWorkbook).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputWorkbook)
$xmlPath = (Resolve-Path $AcceptanceXml).Path
$outputDir = Split-Path -Parent $outputPath
$macroDir = Join-Path $repoRoot "macros\ficha_llangon_v2"
$manifestPath = Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\field_manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$existingExcelIds = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Set-WorkbookName {
    param($Workbook, [string]$Name, [string]$Reference)
    try { $Workbook.Names.Item($Name).Delete() } catch {}
    $Workbook.Names.Add($Name, $Reference) | Out-Null
}

function Replace-CodeModule {
    param($Project, [string]$Name, [string]$Code)
    $component = $Project.VBComponents.Item($Name)
    if ($component.CodeModule.CountOfLines -gt 0) {
        $component.CodeModule.DeleteLines(1, $component.CodeModule.CountOfLines)
    }
    $component.CodeModule.AddFromString($Code)
}

function Clear-RangePreservingMerges {
    param($Range)
    $seen = @{}
    foreach ($cell in @($Range.Cells)) {
        $target = $cell
        if ($cell.MergeCells) { $target = $cell.MergeArea.Cells.Item(1, 1) }
        $key = $target.Worksheet.Name + "!" + $target.Address()
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            $target.Value2 = ""
        }
    }
}

function Clear-BusinessData {
    param($Workbook, $Ficha, $Tech, $Manifest)
    foreach ($item in $Manifest.scalar_fields) {
        if ($item.logical_id -eq "document.confidentiality_notice") { continue }
        try { Clear-RangePreservingMerges $Workbook.Names.Item([string]$item.excel_name).RefersToRange } catch {}
    }
    foreach ($item in $Manifest.ranges) {
        try { Clear-RangePreservingMerges $Workbook.Names.Item([string]$item.excel_name).RefersToRange } catch {}
    }
    $Ficha.Range("L5").Value2 = ""
    $Ficha.Range("L6").Value2 = ""
    $Ficha.Range("L7").Value2 = "Pendiente de revisar"
    $Tech.Range("B2:B6").ClearContents()
    $Tech.Range("B9:B12").ClearContents()
    $Tech.Range("B14:B16").Value2 = 0
    $Tech.Range("B17").ClearContents()
    $Tech.Range("B18").Value2 = "Pendiente"
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
    $ficha = $workbook.Worksheets.Item("Ficha")
    $tech = $workbook.Worksheets.Item("_Llangon")
    $listas = $workbook.Worksheets.Item("_Listas")
    $project = $workbook.VBProject

    Replace-CodeModule $project "modLlangonPlace" (Get-Content -LiteralPath (Join-Path $macroDir "modLlangonPlace.bas") -Raw -Encoding UTF8)
    $coreCode = Get-Content -LiteralPath (Join-Path $macroDir "modLlangonCore.bas") -Raw -Encoding UTF8
    $coreCode = $coreCode.Replace('Public Const LLANGON_TEMPLATE_VERSION As String = "2.1.0"', 'Public Const LLANGON_TEMPLATE_VERSION As String = "3.0.4"')
    $coreCode = $coreCode.Replace('Public Const LLANGON_PAYLOAD_VERSION As String = "1.1"', 'Public Const LLANGON_WORKBOOK_SCHEMA_VERSION As String = "3.0"')
    $coreCode = $coreCode.Replace('SelfTestCompile = "Ficha Llangon " & LLANGON_TEMPLATE_VERSION & " / payload " & LLANGON_PAYLOAD_VERSION', 'SelfTestCompile = "Ficha Llangon " & LLANGON_TEMPLATE_VERSION & " / impresión nativa · esquema " & LLANGON_WORKBOOK_SCHEMA_VERSION')
    $coreCode = $coreCode.Replace('SetNamedValue "llg_control_payload_version", LLANGON_PAYLOAD_VERSION', 'SetNamedValue "llg_control_workbook_schema", LLANGON_WORKBOOK_SCHEMA_VERSION')
    Replace-CodeModule $project "modLlangonCore" $coreCode
    try { $project.VBComponents.Remove($project.VBComponents.Item("modLlangonPrompts")) } catch {}

    foreach ($shapeName in @("btnPromptLotes", "btnPromptJuicio", "btnPromptFormula", "btnPromptCondiciones")) {
        try { $ficha.Shapes.Item($shapeName).Delete() } catch {}
    }
    foreach ($address in @("J25:N29", "J45:M57", "J60:M72", "J75:M83")) {
        $ficha.Range($address).Clear()
    }
    foreach ($name in @("llg_tsv_lotes", "llg_tsv_criterios_juicio", "llg_tsv_criterios_formula", "llg_tsv_condiciones_especiales")) {
        try { $workbook.Names.Item($name).Delete() } catch {}
    }

    Set-WorkbookName $workbook "llg_range_lotes" "='Ficha'!`$B`$27:`$H`$29"
    Set-WorkbookName $workbook "llg_range_criterios_juicio" "='Ficha'!`$B`$47:`$H`$57"
    Set-WorkbookName $workbook "llg_range_criterios_formula" "='Ficha'!`$B`$62:`$H`$72"
    Set-WorkbookName $workbook "llg_range_condiciones_especiales" "='Ficha'!`$B`$76:`$H`$83"
    Set-WorkbookName $workbook "llg_native_print_area" "='Ficha'!`$B`$1:`$H`$95"
    Set-WorkbookName $workbook "llg_print_end" "='Ficha'!`$H`$95"

    Clear-BusinessData $workbook $ficha $tech $manifest
    $workbook.Names.Item("llg_tender_AvisoFecha").RefersToRange.Formula = '=IF(llg_tender_fecha_limite="","",IF(NOT(ISNUMBER(llg_tender_fecha_limite)),"AVISO: fecha límite no válida",IF(TEXTJOIN(" · ",TRUE,IF(llg_tender_fecha_limite<TODAY(),"fecha vencida",""),IF(AND(llg_tender_fecha_limite>=TODAY(),llg_tender_fecha_limite<=TODAY()+3),"plazo de tres días o menos",""),IF(WEEKDAY(llg_tender_fecha_limite,2)>5,"fin de semana",""),IF(COUNTIF(tblFestivos[Fecha],llg_tender_fecha_limite)>0,"festivo nacional registrado",""),IF(COUNTIFS(tblFestivos[Fecha],">="&DATE(YEAR(llg_tender_fecha_limite),1,1),tblFestivos[Fecha],"<="&DATE(YEAR(llg_tender_fecha_limite),12,31))=0,"calendario sin cobertura para "&YEAR(llg_tender_fecha_limite),""))="","Fecha revisada","AVISO: "&TEXTJOIN(" · ",TRUE,IF(llg_tender_fecha_limite<TODAY(),"fecha vencida",""),IF(AND(llg_tender_fecha_limite>=TODAY(),llg_tender_fecha_limite<=TODAY()+3),"plazo de tres días o menos",""),IF(WEEKDAY(llg_tender_fecha_limite,2)>5,"fin de semana",""),IF(COUNTIF(tblFestivos[Fecha],llg_tender_fecha_limite)>0,"festivo nacional registrado",""),IF(COUNTIFS(tblFestivos[Fecha],">="&DATE(YEAR(llg_tender_fecha_limite),1,1),tblFestivos[Fecha],"<="&DATE(YEAR(llg_tender_fecha_limite),12,31))=0,"calendario sin cobertura para "&YEAR(llg_tender_fecha_limite),"")))))'
    $workbook.Names.Item("llg_tender_AvisoFecha").RefersToRange.Font.Bold = $true
    $workbook.Names.Item("llg_tender_AvisoFecha").RefersToRange.Font.Color = 192
    $ficha.Range("H58").Formula = '=IF(COUNTA(B47:INDEX(H:H,ROW()-1))=0,"",SUM(H47:INDEX(H:H,ROW()-1)))'
    $ficha.Range("H73").Formula = '=IF(COUNTA(B62:INDEX(H:H,ROW()-1))=0,"",SUM(H62:INDEX(H:H,ROW()-1)))'
    $ficha.Range("B1").Formula = '=IF(COUNTA(L5,F9,H9,C9,C11)=0,"",IF(L5="","","#Destinatario de esta ficha: "&L5&"# ")&IF(F9="","",TEXT(F9,"dd/mm/yyyy"))&IF(H9="",""," "&TEXT(H9,"hh:mm"))&IF(C9="",""," - "&C9)&IF(C11="",""," - "&C11))'
    $ficha.PageSetup.PrintArea = "`$B`$1:`$H`$95"
    $ficha.PageSetup.PrintTitleRows = "`$1:`$5"

    $tech.Range("B7").Value2 = "3.0.4"
    $tech.Range("B8").Value2 = "3.0"
    $tech.Range("L7:M8").ClearContents()
    $tech.Range("M2").Value2 = "scripts/windows/finalize_ficha_llangon_v3_0_3.ps1"
    $tech.Range("M3").Value2 = "excel_native"
    $tech.Range("M4").Value2 = "none"
    $tech.Range("M5").Value2 = "Ficha!1:5"
    $tech.Range("M6").Value2 = "llg_print_end"
    $listas.Visible = 2
    $tech.Visible = 2
    $ficha.Activate() | Out-Null

    $workbook.SaveAs($outputPath, 52)
    $workbook.Close($true)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
    $workbook = $null

    $excel.AutomationSecurity = 1
    $workbook = $excel.Workbooks.Open($outputPath, 0, $false)
    foreach ($test in @("SelfTestCompile", "SelfTestDeadlineWarning", "SelfTestPlaceParser", "SelfTestPlaceBridgeTsv")) {
        $result = $excel.Run("'" + $workbook.Name + "'!" + $test)
        Write-Output ($test + ": " + [string]$result)
    }

    $imported = $excel.Run("'" + $workbook.Name + "'!ImportPlaceSource", $xmlPath, $false)
    if ([int]$imported -le 0) {
        $importError = $excel.Run("'" + $workbook.Name + "'!PlaceImportLastError")
        throw "La prueba con el XML real no pudo importar datos: $importError"
    }
    $expected = @{
        "llg_analysis_plazo" = "25 días"
        "llg_analysis_plazo_comentario" = "Del 05/12/2026 al 30/12/2026"
        "llg_analysis_prorroga" = "Sí"
        "llg_analysis_prorroga_comentario" = "Máximo de 2 prórrogas."
    }
    foreach ($name in $expected.Keys) {
        $actual = [string]$workbook.Names.Item($name).RefersToRange.Value2
        if ($actual -ne $expected[$name]) { throw "$name devolvió '$actual' en vez de '$($expected[$name])'." }
    }
    Write-Output "XML real: plazo y prórrogas correctos"

    $ficha = $workbook.Worksheets.Item("Ficha")
    $tech = $workbook.Worksheets.Item("_Llangon")
    Clear-BusinessData $workbook $ficha $tech $manifest
    $workbook.Names.Item("llg_tender_AvisoFecha").RefersToRange.Formula = '=IF(llg_tender_fecha_limite="","",IF(NOT(ISNUMBER(llg_tender_fecha_limite)),"AVISO: fecha límite no válida",IF(TEXTJOIN(" · ",TRUE,IF(llg_tender_fecha_limite<TODAY(),"fecha vencida",""),IF(AND(llg_tender_fecha_limite>=TODAY(),llg_tender_fecha_limite<=TODAY()+3),"plazo de tres días o menos",""),IF(WEEKDAY(llg_tender_fecha_limite,2)>5,"fin de semana",""),IF(COUNTIF(tblFestivos[Fecha],llg_tender_fecha_limite)>0,"festivo nacional registrado",""),IF(COUNTIFS(tblFestivos[Fecha],">="&DATE(YEAR(llg_tender_fecha_limite),1,1),tblFestivos[Fecha],"<="&DATE(YEAR(llg_tender_fecha_limite),12,31))=0,"calendario sin cobertura para "&YEAR(llg_tender_fecha_limite),""))="","Fecha revisada","AVISO: "&TEXTJOIN(" · ",TRUE,IF(llg_tender_fecha_limite<TODAY(),"fecha vencida",""),IF(AND(llg_tender_fecha_limite>=TODAY(),llg_tender_fecha_limite<=TODAY()+3),"plazo de tres días o menos",""),IF(WEEKDAY(llg_tender_fecha_limite,2)>5,"fin de semana",""),IF(COUNTIF(tblFestivos[Fecha],llg_tender_fecha_limite)>0,"festivo nacional registrado",""),IF(COUNTIFS(tblFestivos[Fecha],">="&DATE(YEAR(llg_tender_fecha_limite),1,1),tblFestivos[Fecha],"<="&DATE(YEAR(llg_tender_fecha_limite),12,31))=0,"calendario sin cobertura para "&YEAR(llg_tender_fecha_limite),"")))))'
    $ficha.Range("H58").Formula = '=IF(COUNTA(B47:INDEX(H:H,ROW()-1))=0,"",SUM(H47:INDEX(H:H,ROW()-1)))'
    $ficha.Range("H73").Formula = '=IF(COUNTA(B62:INDEX(H:H,ROW()-1))=0,"",SUM(H62:INDEX(H:H,ROW()-1)))'

    $expectedModules = @("modLlangonCore", "modLlangonBridge", "modLlangonPlace")
    $actualModules = @($workbook.VBProject.VBComponents | Where-Object { $_.Type -eq 1 } | ForEach-Object { $_.Name } | Sort-Object)
    if ((Compare-Object ($expectedModules | Sort-Object) $actualModules).Count -ne 0) {
        throw "El proyecto VBA contiene módulos inesperados: $($actualModules -join ', ')."
    }
    $forbidden = "CopyPrompt|BuildPrompt|PromptLotes|PromptJuicio|PromptFormula|PromptCondiciones|llg_tsv_|Área de pegado TSV"
    foreach ($component in $workbook.VBProject.VBComponents) {
        if ($component.CodeModule.CountOfLines -le 0) { continue }
        $code = $component.CodeModule.Lines(1, $component.CodeModule.CountOfLines)
        if ($code -match $forbidden) { throw "Queda código de prompts/TSV en $($component.Name)." }
    }
    foreach ($formulaAddress in @("B27:H29", "B47:H57", "B62:H72", "B76:H83")) {
        foreach ($cell in @($ficha.Range($formulaAddress).Cells)) {
            if ($cell.HasFormula) { throw "Queda una fórmula de enlace en $($cell.Address())." }
        }
    }
    $workbook.Save()
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
