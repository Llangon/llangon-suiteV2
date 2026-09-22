param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$workbookPath = (Resolve-Path $Workbook).Path
$outputDir = [System.IO.Path]::GetFullPath($OutputDirectory)
$overlayImagePath = Join-Path $repoRoot "firebase\public_firebase\static\assets\public-hero-procurement.png"
$inCellImagePath = Join-Path $repoRoot "webapp\infonalia_webapp\static\logo-llangon.png"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Export-NativeCase {
    param([string]$Name, [scriptblock]$Populate, [switch]$InsertRows)
    $copyPath = Join-Path $outputDir ($Name + ".xlsm")
    $pdfPath = Join-Path $outputDir ($Name + ".pdf")
    Remove-Item -LiteralPath $copyPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pdfPath -Force -ErrorAction SilentlyContinue

    $excel = $null
    $book = $null
    try {
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        $excel.EnableEvents = $false
        $excel.AutomationSecurity = 3
        $book = $excel.Workbooks.Open($workbookPath, 0, $false)
        $book.SaveCopyAs($copyPath)
        $book.Close($false)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)
        $book = $excel.Workbooks.Open($copyPath, 0, $false)
        $sheet = $book.Worksheets.Item("Ficha")
        & $Populate $sheet $book
        if ($InsertRows) {
            $originalEndRow = [int]$book.Names.Item("llg_print_end").RefersToRange.Row
            $insertStartRow = $originalEndRow - 1
            $insertEndRow = $insertStartRow + 4
            $sheet.Rows(($insertStartRow.ToString() + ":" + $insertEndRow.ToString())).Insert(-4121) | Out-Null
            $sheet.Range("B" + $insertStartRow).Value2 = "Observación adicional 1 tras insertar cinco filas."
            $sheet.Range("B" + ($insertStartRow + 1)).Value2 = "Observación adicional 2; el final de impresión debe desplazarse."
        }
        $book.Save()

        $namesBefore = @{}
        foreach ($nameItem in $book.Names) { $namesBefore[$nameItem.Name] = $nameItem.RefersTo }
        $modulesBefore = @($book.VBProject.VBComponents | Where-Object { $_.Type -eq 1 } | ForEach-Object { $_.Name } | Sort-Object)
        $sheet.ExportAsFixedFormat(0, $pdfPath)
        $modulesAfter = @($book.VBProject.VBComponents | Where-Object { $_.Type -eq 1 } | ForEach-Object { $_.Name } | Sort-Object)
        if ((Compare-Object $modulesBefore $modulesAfter).Count -ne 0) { throw "La publicación alteró el proyecto VBA." }
        if (-not (Test-Path -LiteralPath $pdfPath)) { throw "Excel no generó $Name.pdf" }

        $result = [ordered]@{
            name = $Name
            pdf = $pdfPath
            size_bytes = (Get-Item -LiteralPath $pdfPath).Length
            macros_disabled = $true
            print_area = $sheet.PageSetup.PrintArea
            print_titles = $sheet.PageSetup.PrintTitleRows
            print_end = $book.Names.Item("llg_print_end").RefersTo
            sheets = @($book.Worksheets | ForEach-Object { $_.Name })
            modules = $modulesAfter
        }
        return $result
    } catch {
        Write-Host ("Caso " + $Name + " · línea " + $_.InvocationInfo.ScriptLineNumber)
        Write-Host $_.ScriptStackTrace
        Write-Host $_.Exception.ToString()
        throw
    } finally {
        if ($null -ne $book) { try { $book.Close($false) } catch {} }
        if ($null -ne $excel) { try { $excel.Quit() } catch {} }
        if ($null -ne $book) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book) }
        if ($null -ne $excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

$normal = Export-NativeCase "Ficha_v3_QA_normal" {
    param($sheet, $book)
    $sheet.Range("L5").Value2 = "SERVILINE FOODS SOCIEDAD LIMITADA"
    $sheet.Range("L8").Value2 = "Documento confidencial para uso exclusivo de {DESTINATARIO}. Prohibida su difusión sin autorización."
    $sheet.Range("C13").Value2 = "QA-NATIVO-001"
    $sheet.Range("F13").Value2 = [datetime]"2030-10-15"
    $sheet.Range("H13").Value2 = [datetime]"1899-12-30T14:00:00"
    $sheet.Range("C14").Value2 = "Servicio de alimentación y apoyo logístico para centros públicos"
    $sheet.Range("C16").Value2 = "https://contrataciondelestado.es/ejemplo-qa"
    $sheet.Range("C17").Value2 = "Organismo Público de Demostración"
    $sheet.Range("F17").Value2 = "PLACE"
    $sheet.Range("C18").Value2 = "Servicios"
    $sheet.Range("F18").Value2 = "Abierto"
    $sheet.Range("C24").Value2 = 125000
    $sheet.Range("F24").Value2 = 250000
    $sheet.Range("C25").Value2 = "24 meses"
    $sheet.Range("C32").Value2 = 1
    $sheet.Range("C32").Offset(0, 1).Value2 = "Servicio principal"
    $sheet.Range("G32").Value2 = 125000
    $sheet.Range("B53").Value2 = "Plan de trabajo"
    $sheet.Range("D53").Value2 = "Organización, metodología y seguimiento."
    $sheet.Range("H53").Value2 = 40
    $sheet.Range("B68").Value2 = "Oferta económica"
    $sheet.Range("D68").Value2 = "Valoración según la fórmula indicada en el PCAP."
    $sheet.Range("H68").Value2 = 60
    $sheet.Range("B82").Value2 = "Gestión responsable de residuos durante la ejecución."
    $sheet.Range("B92").Value2 = "Comprobar la coherencia entre la memoria y la oferta económica."
}

$dynamic = Export-NativeCase "Ficha_v3_QA_dinamica" {
    param($sheet, $book)
    $sheet.Range("L5").Value2 = "CLIENTE DE PRUEBA DINÁMICA, S.L."
    $sheet.Range("C13").Value2 = "QA-NATIVO-002"
    $sheet.Range("C14").Value2 = "Prueba de crecimiento dinámico de la ficha"
    $sheet.Range("B92").Value2 = "Primera observación antes de insertar filas."
} -InsertRows

$images = Export-NativeCase "Ficha_v3_QA_imagenes" {
    param($sheet, $book)
    $sheet.Range("L5").Value2 = "CLIENTE DE PRUEBA DE IMÁGENES, S.L."
    $sheet.Range("C13").Value2 = "QA-NATIVO-IMG"
    $sheet.Range("C14").Value2 = "Prueba de imágenes superpuestas y dentro de celda"

    $overlayAnchor = $sheet.Range("D69")
    $overlay = $sheet.Shapes.AddPicture($overlayImagePath, 0, -1, [double]$overlayAnchor.Left, [double]$overlayAnchor.Top, 230, 78)
    $overlay.Name = "qa_imagen_superpuesta"
    $overlay.Placement = 1

    $sheet.Rows(34).RowHeight = 62
    $inCellAnchor = $sheet.Range("D34")
    $inCell = $sheet.Shapes.AddPicture($inCellImagePath, 0, -1, [double]$inCellAnchor.Left, [double]$inCellAnchor.Top, 120, 42)
    $inCell.Name = "qa_imagen_en_celda"
    $inCell.PlacePictureInCell()
}

$results = @($normal, $dynamic, $images)
$jsonPath = Join-Path $outputDir "native_print_acceptance.json"
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
$results | ConvertTo-Json -Depth 6
