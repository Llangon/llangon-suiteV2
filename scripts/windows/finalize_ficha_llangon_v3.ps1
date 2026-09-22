param(
    [Parameter(Mandatory = $true)][string]$BaseWorkbook,
    [Parameter(Mandatory = $true)][string]$OutputWorkbook,
    [switch]$FocusedTests
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$basePath = (Resolve-Path $BaseWorkbook).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputWorkbook)
$outputDir = Split-Path -Parent $outputPath
$macroDir = Join-Path $repoRoot "macros\ficha_llangon_v2"
$logoPath = Join-Path $repoRoot "webapp\infonalia_webapp\static\logo-llangon.png"
$manifest = Get-Content -LiteralPath (Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\field_manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$verifier = Join-Path $repoRoot "scripts\verify_ficha_llangon_v3.py"
$ooxmlPatcher = Join-Path $repoRoot "scripts\patch_ficha_llangon_v3_ooxml.py"
$existingExcelIds = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Set-WorkbookName {
    param($Workbook, [string]$Name, [string]$Reference)
    try { $Workbook.Names.Item($Name).Delete() } catch {}
    $Workbook.Names.Add($Name, $Reference) | Out-Null
}

function Add-CodeModule {
    param($Project, [string]$Name, [string]$Code)
    $component = $Project.VBComponents.Add(1)
    $component.Name = $Name
    $component.CodeModule.AddFromString($Code)
}

function Add-ActionButton {
    param($Sheet, [string]$Name, [string]$Caption, [string]$Macro, [double]$Left, [double]$Top, [double]$Width, [double]$Height = 22)
    $shape = $Sheet.Shapes.AddShape(5, $Left, $Top + 1, $Width, $Height)
    $shape.Name = $Name
    $shape.AlternativeText = "LlangonAction"
    $shape.OnAction = $Macro
    $shape.Placement = 1
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
    foreach ($component in @($project.VBComponents)) {
        if ($component.Type -eq 1) { $project.VBComponents.Remove($component) }
    }

    $coreCode = Get-Content -LiteralPath (Join-Path $macroDir "modLlangonCore.bas") -Raw -Encoding UTF8
    $coreCode = $coreCode.Replace('Public Const LLANGON_TEMPLATE_VERSION As String = "2.1.0"', 'Public Const LLANGON_TEMPLATE_VERSION As String = "3.0.1"')
    $coreCode = $coreCode.Replace('Public Const LLANGON_PAYLOAD_VERSION As String = "1.1"', 'Public Const LLANGON_WORKBOOK_SCHEMA_VERSION As String = "3.0"')
    $coreCode = $coreCode.Replace('SelfTestCompile = "Ficha Llangon " & LLANGON_TEMPLATE_VERSION & " / payload " & LLANGON_PAYLOAD_VERSION', 'SelfTestCompile = "Ficha Llangon " & LLANGON_TEMPLATE_VERSION & " / impresión nativa · esquema " & LLANGON_WORKBOOK_SCHEMA_VERSION')
    $coreCode = $coreCode.Replace('SetNamedValue "llg_control_payload_version", LLANGON_PAYLOAD_VERSION', 'SetNamedValue "llg_control_workbook_schema", LLANGON_WORKBOOK_SCHEMA_VERSION')

    $bridgeCode = Get-Content -LiteralPath (Join-Path $macroDir "modLlangonBridge.bas") -Raw -Encoding UTF8
    $pdfMarker = $bridgeCode.IndexOf("Public Sub PreparePDF()", [StringComparison]::Ordinal)
    if ($pdfMarker -lt 0) { throw "No se encontró el límite del código PDF en modLlangonBridge." }
    $bridgeCode = $bridgeCode.Substring(0, $pdfMarker).TrimEnd() + [Environment]::NewLine

    Add-CodeModule $project "modLlangonCore" $coreCode
    Add-CodeModule $project "modLlangonBridge" $bridgeCode
    Add-CodeModule $project "modLlangonPlace" (Get-Content -LiteralPath (Join-Path $macroDir "modLlangonPlace.bas") -Raw -Encoding UTF8)

    try { $workbook.Worksheets.Item("Informe_PDF").Delete() } catch {}
    $ficha = $workbook.Worksheets.Item("Ficha")
    $listas = $workbook.Worksheets.Item("_Listas")
    $tech = $workbook.Worksheets.Item("_Llangon")
    $ficha.Activate() | Out-Null

    $oldNotice = [string]$ficha.Range("J6").Value2
    if ([string]::IsNullOrWhiteSpace($oldNotice)) {
        $oldNotice = "Documento confidencial para uso exclusivo de {DESTINATARIO}. Prohibida su difusión sin autorización."
    }

    $ficha.Range("B4:H5").UnMerge()
    $ficha.Range("B4:H5").Clear()
    $ficha.Range("B4:C4").Merge()
    $ficha.Range("D4:H4").Merge()
    $ficha.Range("B5:H5").Merge()
    $ficha.Range("B4").Value2 = "DESTINATARIO"
    $ficha.Range("D4").Formula = '=IF($L$5="","Sin seleccionar",$L$5)'
    $ficha.Range("B5").Formula = '=SUBSTITUTE($L$8,"{DESTINATARIO}",IF($L$5="","el destinatario seleccionado",$L$5))'
    $ficha.Range("B4:C4").Interior.Color = 2797114
    $ficha.Range("B4:C4").Font.Name = "Aptos"
    $ficha.Range("B4:C4").Font.Bold = $true
    $ficha.Range("B4:C4").Font.Color = 16777215
    $ficha.Range("D4:H4").Interior.Color = 15794160
    $ficha.Range("D4:H4").Font.Name = "Aptos"
    $ficha.Range("D4:H4").Font.Bold = $true
    $ficha.Range("D4:H4").Font.Color = 2631715
    $ficha.Range("B5:H5").Interior.Color = 16186879
    $ficha.Range("B5:H5").Font.Name = "Aptos"
    $ficha.Range("B5:H5").Font.Size = 7.5
    $ficha.Range("B5:H5").Font.Color = 6579300
    $ficha.Range("B5:H5").WrapText = $true
    $ficha.Range("B4:H5").Borders.Color = 13621451
    $ficha.Rows(4).RowHeight = 18
    $ficha.Rows(5).RowHeight = 27

    # La cabecera principal está combinada desde A1:H1; el valor debe escribirse
    # en la esquina superior izquierda de la combinación.
    $ficha.Range("A1").Value2 = "FICHA LLANGON 3"
    $ficha.Range("D2").Value2 = "Ficha de licitación"

    $ficha.Range("B6:H9").UnMerge()
    $ficha.Range("B6:H9").Clear()
    $ficha.Rows("6:10").Hidden = $true

    $ficha.Range("J4:O10").UnMerge()
    $ficha.Range("J4:O10").Clear()
    $ficha.Range("J4:O4").Merge()
    $ficha.Range("J5:K5").Merge(); $ficha.Range("L5:O5").Merge()
    $ficha.Range("J6:K6").Merge(); $ficha.Range("L6:O6").Merge()
    $ficha.Range("J7:K7").Merge(); $ficha.Range("L7:O7").Merge()
    $ficha.Range("J8:K8").Merge(); $ficha.Range("L8:O10").Merge()
    $ficha.Range("J4").Value2 = "DATOS DE PUBLICACIÓN"
    $ficha.Range("J5").Value2 = "Cliente"
    $ficha.Range("J6").Value2 = "Caché"
    $ficha.Range("J7").Value2 = "Revisión"
    $ficha.Range("J8").Value2 = "Confidencialidad"
    $ficha.Range("L5:O5").ClearContents()
    $ficha.Range("L6").Value2 = ""
    $ficha.Range("L7").Value2 = "Pendiente de revisar"
    $ficha.Range("L8").Value2 = $oldNotice
    $ficha.Range("J4:O4").Interior.Color = 6978327
    $ficha.Range("J4:O4").Font.Name = "Aptos"
    $ficha.Range("J4:O4").Font.Bold = $true
    $ficha.Range("J4:O4").Font.Color = 16777215
    $ficha.Range("J5:K8").Interior.Color = 15794160
    $ficha.Range("J5:K8").Font.Name = "Aptos"
    $ficha.Range("J5:K8").Font.Bold = $true
    $ficha.Range("J5:K8").Font.Color = 2631715
    $ficha.Range("L5:O10").Interior.Color = 16186879
    $ficha.Range("L5:O10").Font.Name = "Aptos"
    $ficha.Range("L5:O10").Font.Size = 9
    $ficha.Range("L8:O10").WrapText = $true
    $ficha.Range("J4:O10").Borders.Color = 13621451
    $ficha.Columns("J:O").ColumnWidth = 11
    $ficha.Rows(5).RowHeight = 24
    $ficha.Rows(6).RowHeight = 20
    $ficha.Rows(7).RowHeight = 20
    $ficha.Rows("8:10").RowHeight = 19

    Set-WorkbookName $workbook "llg_recipient_client_display" "='Ficha'!`$L`$5"
    Set-WorkbookName $workbook "llg_ui_cache_status" "='Ficha'!`$L`$6"
    Set-WorkbookName $workbook "llg_ui_review_status" "='Ficha'!`$L`$7"
    Set-WorkbookName $workbook "llg_document_confidentiality_notice" "='Ficha'!`$L`$8"
    try { $workbook.Names.Item("llg_control_payload_version").Delete() } catch {}
    try { $workbook.Names.Item("llg_last_pdf_path").Delete() } catch {}
    Set-WorkbookName $workbook "llg_control_workbook_schema" "='_Llangon'!`$B`$8"
    Set-WorkbookName $workbook "llg_native_print_area" "='Ficha'!`$B`$1:`$H`$101"
    Set-WorkbookName $workbook "llg_print_end" "='Ficha'!`$H`$101"

    foreach ($item in $manifest.scalar_fields) {
        if ($item.logical_id -eq "document.confidentiality_notice") { continue }
        try { $workbook.Names.Item([string]$item.excel_name).RefersToRange.ClearContents() } catch {}
    }
    foreach ($item in $manifest.ranges) {
        try { $workbook.Names.Item([string]$item.excel_name).RefersToRange.ClearContents() } catch {}
    }
    $ficha.Range("L6").Value2 = ""
    $ficha.Range("L7").Value2 = "Pendiente de revisar"
    $ficha.Range("L8").Value2 = $oldNotice
    $ficha.Range("H64").Formula = "=SUM(H53:INDEX(H:H,ROW()-1))"
    $ficha.Range("H79").Formula = "=SUM(H68:INDEX(H:H,ROW()-1))"

    $ficha.Range("L5").Validation.Delete() | Out-Null
    $ficha.Range("L5").Validation.Add(3, 1, 1, "=llg_client_choices")
    $ficha.Range("L5").Validation.IgnoreBlank = $true
    $ficha.Range("L5").Validation.InCellDropdown = $true

    $buttonPositions = @{}
    foreach ($address in @("J1", "M1", "J2")) {
        $anchor = $ficha.Range($address)
        $buttonPositions[$address] = @([double]$anchor.Left, [double]$anchor.Top)
    }
    foreach ($shape in @($ficha.Shapes)) {
        if ($shape.AlternativeText -eq "LlangonAction") {
            $shape.Delete()
        } elseif ($shape.Top -lt $ficha.Rows(6).Top) {
            $shape.Delete()
        }
    }
    Add-ActionButton $ficha "btnActualizarClientes" "Actualizar clientes" "UpdateClients" $buttonPositions["J1"][0] $buttonPositions["J1"][1] 118
    Add-ActionButton $ficha "btnImportarPlace" "Importar PLACE" "ImportPlace" $buttonPositions["M1"][0] $buttonPositions["M1"][1] 118
    Add-ActionButton $ficha "btnRevisarFicha" "Revisar ficha" "ReviewFichaAction" $buttonPositions["J2"][0] $buttonPositions["J2"][1] 241

    $ficha.Range("J113:O115").UnMerge()
    $ficha.Range("J113:O115").Merge()
    $ficha.Range("J113").Value2 = "IMPRESIÓN NATIVA`nPara ampliar la ficha, inserte filas por encima de la última línea de Observaciones. Excel ampliará el área imprimible."
    $ficha.Range("J113:O115").Font.Name = "Aptos"
    $ficha.Range("J113:O115").Font.Size = 8
    $ficha.Range("J113:O115").Font.Color = 6579300
    $ficha.Range("J113:O115").Interior.Color = 16186879
    $ficha.Range("J113:O115").WrapText = $true
    $ficha.Range("J113:O115").Borders.Color = 13621451

    $ficha.PageSetup.PrintArea = "`$B`$1:`$H`$101"
    $ficha.PageSetup.PrintTitleRows = "`$1:`$5"
    $ficha.PageSetup.Orientation = 1
    $ficha.PageSetup.PaperSize = 9
    $ficha.PageSetup.Zoom = $false
    $ficha.PageSetup.FitToPagesWide = 1
    $ficha.PageSetup.FitToPagesTall = $false
    $ficha.PageSetup.LeftMargin = $excel.CentimetersToPoints(1.25)
    $ficha.PageSetup.RightMargin = $excel.CentimetersToPoints(1.25)
    $ficha.PageSetup.TopMargin = $excel.CentimetersToPoints(4.5)
    $ficha.PageSetup.BottomMargin = $excel.CentimetersToPoints(1.45)
    $ficha.PageSetup.HeaderMargin = $excel.CentimetersToPoints(0.35)
    $ficha.PageSetup.FooterMargin = $excel.CentimetersToPoints(0.45)
    $ficha.PageSetup.CenterHorizontally = $true
    $ficha.PageSetup.PrintGridlines = $false
    $ficha.PageSetup.PrintHeadings = $false
    $ficha.PageSetup.LeftHeader = "&G"
    $ficha.PageSetup.LeftHeaderPicture.Filename = $logoPath
    $ficha.PageSetup.LeftHeaderPicture.Width = 75
    $ficha.PageSetup.LeftHeaderPicture.Height = 32
    $ficha.PageSetup.CenterHeader = ""
    $ficha.PageSetup.RightHeader = ""
    $ficha.PageSetup.LeftFooter = ""
    $ficha.PageSetup.CenterFooter = ""
    $ficha.PageSetup.RightFooter = "Página &P de &N"

    $tech.Range("A8").Value2 = "workbook_schema"
    $tech.Range("B7").Value2 = "3.0.1"
    $tech.Range("B8").Value2 = "3.0"
    $tech.Range("A21:B21").ClearContents()
    $tech.Range("B2:B6").ClearContents()
    $tech.Range("B9").ClearContents()
    $tech.Range("B10").Value2 = "manual"
    $tech.Range("B11").ClearContents()
    $tech.Range("B13").ClearContents()
    $tech.Range("B14:B16").Value2 = 0
    $tech.Range("B17").ClearContents()
    $tech.Range("B18").Value2 = "Pendiente"
    try { $tech.ListObjects.Item("tblFieldRegistry").Delete() } catch {}
    $tech.Range("D1:J200").Clear()
    $tech.Range("L2").Value2 = "build_source"
    $tech.Range("M2").Value2 = "scripts/windows/finalize_ficha_llangon_v3.ps1"
    $tech.Range("L3").Value2 = "print_strategy"
    $tech.Range("M3").Value2 = "excel_native"
    $tech.Range("L4").Value2 = "pdf_macro_dependency"
    $tech.Range("M4").Value2 = "none"
    $tech.Range("L5").Value2 = "print_titles"
    $tech.Range("M5").Value2 = "Ficha!1:5"
    $tech.Range("L6").Value2 = "print_end_marker"
    $tech.Range("M6").Value2 = "llg_print_end"
    $listas.Visible = 2
    $tech.Visible = 2

    $workbook.SaveAs($outputPath, 52)
    $workbook.Close($true)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
    $workbook = $null

    $excel.AutomationSecurity = 1
    $workbook = $excel.Workbooks.Open($outputPath, 0, $false)
    if ($FocusedTests) {
        $tests = @("SelfTestCompile", "SelfTestPlaceParser", "SelfTestPlaceBridgeTsv")
    } else {
        $tests = @(
            "SelfTestCompile",
            "SelfTestPlaceParser",
            "SelfTestPlaceBridgeTsv",
            "SelfTestPlaceLongUrl",
            "SelfTestClientCache"
        )
    }
    foreach ($test in $tests) {
        $result = $excel.Run("'" + $workbook.Name + "'!" + $test)
        Write-Host ($test + ": " + [string]$result)
    }

    # Las pruebas no deben dejar estado visible en la copia entregable.
    $workbook.Worksheets.Item("Ficha").Range("L5").Value2 = ""
    $workbook.Worksheets.Item("Ficha").Range("L6").Value2 = ""
    $workbook.Worksheets.Item("Ficha").Range("L7").Value2 = "Pendiente de revisar"

    $expectedModules = @("modLlangonCore", "modLlangonBridge", "modLlangonPlace")
    $actualModules = @($workbook.VBProject.VBComponents | Where-Object { $_.Type -eq 1 } | ForEach-Object { $_.Name } | Sort-Object)
    if ((Compare-Object ($expectedModules | Sort-Object) $actualModules).Count -ne 0) {
        throw "El proyecto VBA final contiene módulos inesperados: $($actualModules -join ', ')."
    }
    $bannedCode = "PreparePDF|OpenLastPdfOrReport|ExportFallbackExcel|RefreshInformePDF|BuildFichaPayloadJson|render-pdf|Informe_PDF|ExportAsFixedFormat"
    foreach ($component in $workbook.VBProject.VBComponents) {
        if ($component.CodeModule.CountOfLines -le 0) { continue }
        $code = $component.CodeModule.Lines(1, $component.CodeModule.CountOfLines)
        if ($code -match $bannedCode) { throw "Queda una dependencia PDF en el módulo $($component.Name)." }
    }
    $listas = $workbook.Worksheets.Item("_Listas")
    $clientTable = $null
    try { $clientTable = $listas.ListObjects.Item("tblClientes") } catch {}
    if ($null -eq $clientTable) {
        $lastClientRow = $listas.Cells.Item($listas.Rows.Count, 7).End(-4162).Row
        $clientTable = $listas.ListObjects.Add(1, $listas.Range("G1:M" + $lastClientRow), $null, 1)
        $clientTable.Name = "tblClientes"
        $clientTable.TableStyle = "TableStyleMedium4"
        Set-WorkbookName $workbook "llg_client_choices" ("='_Listas'!`$H`$2:`$H`$" + $lastClientRow)
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

Start-Sleep -Milliseconds 600
Get-Process EXCEL -ErrorAction SilentlyContinue | Where-Object {
    $_.Id -notin $existingExcelIds -and $_.MainWindowHandle -eq 0
} | Stop-Process -Force -ErrorAction SilentlyContinue
& $python $ooxmlPatcher $outputPath
if ($LASTEXITCODE -ne 0) { throw "No se pudo normalizar el pie de página OOXML." }
& $python $verifier --workbook $outputPath --repo-root $repoRoot
if ($LASTEXITCODE -ne 0) { throw "La verificación estática del XLSM 3.0 no ha sido satisfactoria." }
