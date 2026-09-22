Option Explicit

Private Const REPORT_GREEN As Long = 2797114
Private Const REPORT_DARK As Long = 2631715
Private Const REPORT_LIGHT As Long = 15858161
Private Const REPORT_GREY As Long = 16185078

Private Sub ReportSection(ByVal ws As Worksheet, ByRef rowNumber As Long, ByVal title As String)
    With ws.Range("A" & rowNumber & ":H" & rowNumber)
        .Merge
        .Value = title
        .Interior.Color = RGB(23, 107, 50)
        .Font.Name = "Aptos Display"
        .Font.Size = 11
        .Font.Bold = True
        .Font.Color = vbWhite
        .RowHeight = 24
        .VerticalAlignment = xlCenter
    End With
    rowNumber = rowNumber + 1
End Sub

Private Sub ReportPair(ByVal ws As Worksheet, ByRef rowNumber As Long, ByVal label As String, ByVal value As String)
    If Trim$(value) = "" Then Exit Sub
    With ws.Range("A" & rowNumber)
        .Value = label
        .Interior.Color = RGB(243, 245, 244)
        .Font.Name = "Aptos"
        .Font.Size = 9
        .Font.Bold = True
        .Font.Color = RGB(23, 107, 50)
        .Borders.Color = RGB(203, 216, 207)
    End With
    With ws.Range("B" & rowNumber & ":H" & rowNumber)
        .Merge
        .Value = value
        .Interior.Color = vbWhite
        .Font.Name = "Aptos"
        .Font.Size = 9
        .Font.Color = RGB(38, 50, 56)
        .WrapText = True
        .VerticalAlignment = xlTop
        .Borders.Color = RGB(203, 216, 207)
    End With
    ws.Rows(rowNumber).RowHeight = IIf(Len(value) > 220, 60, IIf(Len(value) > 100, 42, 25))
    rowNumber = rowNumber + 1
End Sub

Private Function DisplayDate(ByVal rangeName As String) As String
    Dim rng As Range
    Set rng = NamedRange(rangeName)
    If Not rng Is Nothing Then
        If IsDate(rng.Value) Then DisplayDate = Format$(CDate(rng.Value), "dd/mm/yyyy") Else DisplayDate = Trim$(CStr(rng.Value))
    End If
End Function

Private Function DisplayTime(ByVal rangeName As String) As String
    Dim rng As Range, value As Variant
    Set rng = NamedRange(rangeName)
    If Not rng Is Nothing Then
        value = rng.Value
        If IsNumeric(value) Then
            If CDbl(value) >= 0# And CDbl(value) < 1# Then
                DisplayTime = Format$(CDate(CDbl(value)), "hh:nn")
            Else
                DisplayTime = Trim$(CStr(value))
            End If
        ElseIf IsDate(value) Then
            DisplayTime = Format$(CDate(value), "hh:nn")
        Else
            DisplayTime = Trim$(CStr(value))
        End If
    End If
End Function

Private Function DisplayMoney(ByVal rangeName As String) As String
    Dim rng As Range
    Set rng = NamedRange(rangeName)
    If rng Is Nothing Then Exit Function
    If Trim$(CStr(rng.Value)) = "" Then Exit Function
    If IsNumeric(rng.Value) Then DisplayMoney = Format$(CDbl(rng.Value), "#,##0.00") & " €" Else DisplayMoney = CStr(rng.Value)
End Function

Private Function JoinDetail(ByVal first As String, ByVal second As String) As String
    If Trim$(first) <> "" And Trim$(second) <> "" Then JoinDetail = first & ". " & second Else JoinDetail = first & second
End Function

Private Function RecipientLegalName() As String
    RecipientLegalName = NamedText("llg_recipient_razon_social")
    If RecipientLegalName = "" Then RecipientLegalName = NamedText("llg_recipient_client_display")
End Function

Private Function ConfidentialityFooter() As String
    ConfidentialityFooter = Replace(NamedText("llg_document_confidentiality_notice"), "{DESTINATARIO}", RecipientLegalName(), 1, -1, vbTextCompare)
End Function

Private Sub WriteLotes(ByVal ws As Worksheet, ByRef rowNumber As Long)
    Dim dataRange As Range, row As Range, hasData As Boolean
    Set dataRange = SectionBodyRange("Lotes (opcional)", "Garantías y participación", 2)
    If dataRange Is Nothing Then Exit Sub
    For Each row In dataRange.Rows
        If Trim$(CStr(row.Cells(1, 2).Value)) <> "" Or Trim$(CStr(row.Cells(1, 1).Value)) <> "" Then hasData = True: Exit For
    Next row
    If Not hasData Then Exit Sub
    ReportSection ws, rowNumber, "3. Lotes"
    ws.Range("A" & rowNumber).Value = "N.º"
    ws.Range("B" & rowNumber).Value = "Lote"
    ws.Range("D" & rowNumber).Value = "Presupuesto"
    ws.Range("E" & rowNumber).Value = "Valor est."
    ws.Range("F" & rowNumber).Value = "Comentarios"
    ws.Range("B" & rowNumber & ":C" & rowNumber).Merge
    ws.Range("F" & rowNumber & ":H" & rowNumber).Merge
    With ws.Range("A" & rowNumber & ":H" & rowNumber)
        .Interior.Color = RGB(23, 107, 50): .Font.Color = vbWhite: .Font.Bold = True: .Font.Size = 8: .HorizontalAlignment = xlCenter
    End With
    rowNumber = rowNumber + 1
    For Each row In dataRange.Rows
        If Trim$(CStr(row.Cells(1, 2).Value)) <> "" Or Trim$(CStr(row.Cells(1, 1).Value)) <> "" Then
            ws.Range("A" & rowNumber).Value = row.Cells(1, 1).Value
            ws.Range("B" & rowNumber & ":C" & rowNumber).Merge: ws.Range("B" & rowNumber).Value = row.Cells(1, 2).Value
            ws.Range("D" & rowNumber).Value = row.Cells(1, 5).Value
            ws.Range("E" & rowNumber).Value = row.Cells(1, 6).Value
            ws.Range("F" & rowNumber & ":H" & rowNumber).Merge: ws.Range("F" & rowNumber).Value = row.Cells(1, 7).Value
            With ws.Range("A" & rowNumber & ":H" & rowNumber)
                .Font.Name = "Aptos": .Font.Size = 8: .WrapText = True: .VerticalAlignment = xlTop
                .Borders.Color = RGB(203, 216, 207)
            End With
            ws.Rows(rowNumber).RowHeight = 34
            rowNumber = rowNumber + 1
        End If
    Next row
End Sub

Private Sub WriteCriteria(ByVal ws As Worksheet, ByRef rowNumber As Long, ByVal sectionTitle As String, ByVal nextSectionTitle As String, ByVal title As String, ByVal number As Long)
    Dim dataRange As Range, row As Range, hasData As Boolean, total As Double, value As Variant
    Set dataRange = SectionBodyRange(sectionTitle, nextSectionTitle, 2, "Total puntos")
    If dataRange Is Nothing Then Exit Sub
    For Each row In dataRange.Rows
        If Trim$(CStr(row.Cells(1, 1).Value)) <> "" Then hasData = True: Exit For
    Next row
    If Not hasData Then Exit Sub
    ReportSection ws, rowNumber, CStr(number) & ". " & title
    ws.Range("A" & rowNumber).Value = "Criterio"
    ws.Range("D" & rowNumber).Value = "Descripción"
    ws.Range("H" & rowNumber).Value = "Puntos"
    ws.Range("A" & rowNumber & ":C" & rowNumber).Merge
    ws.Range("D" & rowNumber & ":G" & rowNumber).Merge
    With ws.Range("A" & rowNumber & ":H" & rowNumber)
        .Interior.Color = RGB(23, 107, 50): .Font.Color = vbWhite: .Font.Bold = True: .Font.Size = 8: .HorizontalAlignment = xlCenter
    End With
    rowNumber = rowNumber + 1
    For Each row In dataRange.Rows
        If Trim$(CStr(row.Cells(1, 1).Value)) <> "" Then
            ws.Range("A" & rowNumber & ":C" & rowNumber).Merge
            ws.Range("A" & rowNumber).Value = row.Cells(1, 1).Value
            ws.Range("D" & rowNumber & ":G" & rowNumber).Merge
            ws.Range("D" & rowNumber).Value = row.Cells(1, 3).Value
            value = row.Cells(1, 7).Value
            ws.Range("H" & rowNumber).Value = value
            If IsNumeric(value) Then total = total + CDbl(value)
            With ws.Range("A" & rowNumber & ":H" & rowNumber)
                .Font.Name = "Aptos": .Font.Size = 8: .WrapText = True: .VerticalAlignment = xlTop
                .Borders.Color = RGB(203, 216, 207)
            End With
            ws.Rows(rowNumber).RowHeight = IIf(Len(CStr(row.Cells(1, 3).Value)) > 180, 56, 38)
            rowNumber = rowNumber + 1
        End If
    Next row
    ws.Range("A" & rowNumber & ":G" & rowNumber).Merge: ws.Range("A" & rowNumber).Value = "Total"
    ws.Range("H" & rowNumber).Value = total
    With ws.Range("A" & rowNumber & ":H" & rowNumber)
        .Interior.Color = RGB(240, 248, 241): .Font.Bold = True: .Borders.Color = RGB(203, 216, 207)
    End With
    rowNumber = rowNumber + 1
End Sub

Private Sub WriteConditions(ByVal ws As Worksheet, ByRef rowNumber As Long)
    Dim dataRange As Range, row As Range, hasData As Boolean
    Set dataRange = SectionBodyRange("Condiciones especiales de ejecución", "Observaciones", 1)
    If dataRange Is Nothing Then Exit Sub
    For Each row In dataRange.Rows
        If Trim$(CStr(row.Cells(1, 1).Value)) <> "" Then hasData = True: Exit For
    Next row
    If Not hasData Then Exit Sub
    ReportSection ws, rowNumber, "8. Condiciones especiales de ejecución"
    For Each row In dataRange.Rows
        If Trim$(CStr(row.Cells(1, 1).Value)) <> "" Then
            With ws.Range("A" & rowNumber & ":H" & rowNumber)
                .Merge: .Value = row.Cells(1, 1).Value
                .Font.Name = "Aptos": .Font.Size = 9: .WrapText = True: .VerticalAlignment = xlTop
                .Borders.Color = RGB(203, 216, 207): .Interior.Color = vbWhite
            End With
            ws.Rows(rowNumber).RowHeight = IIf(Len(CStr(row.Cells(1, 1).Value)) > 180, 56, 34)
            rowNumber = rowNumber + 1
        End If
    Next row
End Sub

Public Sub RefreshInformePDF()
    Dim ws As Worksheet, rowNumber As Long, deadline As String
    Dim observationRange As Range, observationRow As Range
    Set ws = ThisWorkbook.Worksheets("Informe_PDF")
    On Error Resume Next
    ws.Unprotect
    ws.Range("A6:H1000").UnMerge
    ws.Range("A6:H1000").Clear
    On Error GoTo 0

    rowNumber = 6
    With ws.Range("A6:H6")
        .Merge
        .Value = NamedText("llg_tender_objeto")
        .Font.Name = "Aptos Display": .Font.Size = 14: .Font.Bold = True: .Font.Color = RGB(38, 50, 56)
        .WrapText = True: .VerticalAlignment = xlCenter: .HorizontalAlignment = xlLeft: .RowHeight = 42
    End With
    rowNumber = 7
    ReportPair ws, rowNumber, "Expediente", NamedText("llg_tender_expediente")
    ReportPair ws, rowNumber, "Destinatario", RecipientLegalName()
    deadline = DisplayDate("llg_tender_fecha_limite")
    If DisplayTime("llg_tender_hora_limite") <> "" Then deadline = deadline & " · " & DisplayTime("llg_tender_hora_limite")
    ReportPair ws, rowNumber, "Fecha límite", deadline

    ReportSection ws, rowNumber, "1. Identificación"
    ReportPair ws, rowNumber, "Organismo", NamedText("llg_tender_organismo")
    ReportPair ws, rowNumber, "Plataforma", NamedText("llg_tender_plataforma")
    ReportPair ws, rowNumber, "Tipo de contrato", NamedText("llg_tender_tipo_contrato")
    ReportPair ws, rowNumber, "Procedimiento", NamedText("llg_tender_procedimiento")
    ReportPair ws, rowNumber, "Regulación armonizada", NamedText("llg_tender_regulacion_armonizada")
    ReportPair ws, rowNumber, "Enlace", NamedText("llg_tender_enlace")

    ReportSection ws, rowNumber, "2. Datos económicos y plazos"
    ReportPair ws, rowNumber, "Presupuesto base", DisplayMoney("llg_tender_presupuesto_base")
    ReportPair ws, rowNumber, "Valor estimado", DisplayMoney("llg_tender_valor_estimado")
    ReportPair ws, rowNumber, "Plazo", JoinDetail(NamedText("llg_analysis_plazo"), NamedText("llg_analysis_plazo_comentario"))
    ReportPair ws, rowNumber, "Prórroga", JoinDetail(NamedText("llg_analysis_prorroga"), NamedText("llg_analysis_prorroga_comentario"))
    ReportPair ws, rowNumber, "Forma de adjudicación", NamedText("llg_analysis_forma_adjudicacion")
    WriteLotes ws, rowNumber

    ReportSection ws, rowNumber, "4. Garantías y participación"
    ReportPair ws, rowNumber, "Garantía provisional", JoinDetail(NamedText("llg_analysis_garantia_provisional"), NamedText("llg_analysis_garantia_provisional_comentario"))
    ReportPair ws, rowNumber, "Garantía definitiva", JoinDetail(NamedText("llg_analysis_garantia_definitiva"), NamedText("llg_analysis_garantia_definitiva_comentario"))
    ReportPair ws, rowNumber, "Garantía complementaria", JoinDetail(NamedText("llg_analysis_garantia_complementaria"), NamedText("llg_analysis_garantia_complementaria_comentario"))
    ReportPair ws, rowNumber, "Adscripción de medios", JoinDetail(NamedText("llg_analysis_adscripcion_medios"), NamedText("llg_analysis_adscripcion_medios_comentario"))
    ReportPair ws, rowNumber, "Número de sobres", NamedText("llg_analysis_numero_sobres")
    ReportPair ws, rowNumber, "Fichas técnicas", JoinDetail(NamedText("llg_analysis_fichas_tecnicas"), NamedText("llg_analysis_fichas_tecnicas_comentario"))
    ReportPair ws, rowNumber, "Memoria técnica", JoinDetail(NamedText("llg_analysis_memoria_tecnica"), NamedText("llg_analysis_memoria_tecnica_comentario"))
    ReportPair ws, rowNumber, "Subcontratación", JoinDetail(NamedText("llg_analysis_subcontratacion"), NamedText("llg_analysis_subcontratacion_comentario"))

    ReportSection ws, rowNumber, "5. Muestras"
    ReportPair ws, rowNumber, "Exigidas", NamedText("llg_analysis_muestras")
    ReportPair ws, rowNumber, "Momento", NamedText("llg_analysis_muestras_momento")
    ReportPair ws, rowNumber, "Detalle", NamedText("llg_analysis_muestras_comentario")
    WriteCriteria ws, rowNumber, "Criterios sujetos a juicio de valor", "Criterios evaluables mediante fórmula", "Criterios sujetos a juicio de valor", 6
    WriteCriteria ws, rowNumber, "Criterios evaluables mediante fórmula", "Condiciones especiales de ejecución", "Criterios evaluables mediante fórmula", 7
    WriteConditions ws, rowNumber
    Set observationRange = SectionBodyRange("Observaciones", "", 1)
    If RangeHasContent(observationRange) Then
        ReportSection ws, rowNumber, "9. Observaciones"
        For Each observationRow In observationRange.Rows
            If Trim$(CStr(observationRow.Cells(1, 1).Value)) <> "" Then
                With ws.Range("A" & rowNumber & ":H" & rowNumber)
                    .Merge: .Value = observationRow.Cells(1, 1).Value
                    .Font.Name = "Aptos": .Font.Size = 9: .WrapText = True: .VerticalAlignment = xlTop
                    .Borders.Color = RGB(203, 216, 207): .Interior.Color = vbWhite
                End With
                ws.Rows(rowNumber).RowHeight = IIf(Len(CStr(observationRow.Cells(1, 1).Value)) > 180, 56, 34)
                rowNumber = rowNumber + 1
            End If
        Next observationRow
    End If

    With ws.PageSetup
        .PrintArea = "$A$1:$H$" & rowNumber
        .Orientation = xlPortrait
        .PaperSize = xlPaperA4
        .Zoom = False
        .FitToPagesWide = 1
        .FitToPagesTall = False
        .LeftMargin = Application.CentimetersToPoints(1.4)
        .RightMargin = Application.CentimetersToPoints(1.4)
        .TopMargin = Application.CentimetersToPoints(2)
        .BottomMargin = Application.CentimetersToPoints(2)
        .CenterHeader = "Destinatario: " & RecipientLegalName()
        .LeftFooter = ConfidentialityFooter()
        .CenterFooter = ""
        .RightFooter = "Página &P de &N"
    End With
    ws.Protect DrawingObjects:=False, Contents:=True, Scenarios:=True, UserInterfaceOnly:=True, AllowFormattingRows:=True
End Sub

Public Sub AbrirInforme()
    RefreshInformePDF
    ThisWorkbook.Worksheets("Informe_PDF").Visible = xlSheetVisible
    ThisWorkbook.Worksheets("Informe_PDF").Activate
End Sub

Private Function UniquePdfPath(ByVal requested As String) As String
    Dim i As Long, base As String
    If Dir$(requested) = "" Then UniquePdfPath = requested: Exit Function
    base = Left$(requested, Len(requested) - 4)
    For i = 2 To 999
        If Dir$(base & "_r" & i & ".pdf") = "" Then UniquePdfPath = base & "_r" & i & ".pdf": Exit Function
    Next i
End Function

Public Sub ExportFallbackExcel()
    Dim errors As Long, outputPath As String, backButton As Shape, exportButton As Shape
    On Error GoTo ExportError
    errors = ReviewFicha(False)
    RefreshInformePDF
    outputPath = UniquePdfPath(PdfOutputPath(errors > 0, True))
    Set backButton = ThisWorkbook.Worksheets("Informe_PDF").Shapes("btnVolverFicha")
    Set exportButton = ThisWorkbook.Worksheets("Informe_PDF").Shapes("btnFallbackPdf")
    backButton.Visible = False
    exportButton.Visible = False
    ThisWorkbook.Worksheets("Informe_PDF").ExportAsFixedFormat Type:=xlTypePDF, Filename:=outputPath, Quality:=xlQualityStandard, IncludeDocProperties:=True, IgnorePrintAreas:=False, OpenAfterPublish:=False
    backButton.Visible = True
    exportButton.Visible = True
    SetNamedValue "llg_last_pdf_path", outputPath
    MsgBox "PDF de contingencia generado mediante Excel:" & vbCrLf & outputPath, vbInformation, "Exportación Excel"
    Exit Sub

ExportError:
    On Error Resume Next
    If Not backButton Is Nothing Then backButton.Visible = True
    If Not exportButton Is Nothing Then exportButton.Visible = True
    On Error GoTo 0
    MsgBox "No se pudo generar el PDF de contingencia. La ficha permanece intacta.", vbExclamation, "Exportación Excel"
End Sub

Public Sub VolverAFicha()
    ThisWorkbook.Worksheets("Ficha").Activate
End Sub
