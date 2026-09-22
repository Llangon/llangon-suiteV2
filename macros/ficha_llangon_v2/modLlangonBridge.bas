Option Explicit

Private Function QuoteArg(ByVal value As String) As String
    QuoteArg = Chr$(34) & Replace(value, Chr$(34), Chr$(34) & Chr$(34)) & Chr$(34)
End Function

Private Function ParentFolder(ByVal value As String) As String
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    On Error Resume Next
    ParentFolder = fso.GetParentFolderName(value)
    On Error GoTo 0
End Function

Public Function ResolveBridgePath() As String
    Dim candidate As String, currentPath As String, i As Long
    If LCase$(Trim$(Environ$("LLANGON_EXCEL_BRIDGE_DISABLE"))) = "1" Then Exit Function
    candidate = Trim$(Environ$("LLANGON_EXCEL_BRIDGE"))
    If candidate <> "" And Dir$(candidate) <> "" Then ResolveBridgePath = candidate: Exit Function

    candidate = Environ$("LOCALAPPDATA") & "\LlangonSuite\bridge\llangon-excel-bridge.cmd"
    If Dir$(candidate) <> "" Then ResolveBridgePath = candidate: Exit Function

    currentPath = ThisWorkbook.Path
    For i = 1 To 8
        candidate = currentPath & "\scripts\windows\llangon_excel_bridge.cmd"
        If Dir$(candidate) <> "" Then ResolveBridgePath = candidate: Exit Function
        currentPath = ParentFolder(currentPath)
        If currentPath = "" Then Exit For
    Next i
End Function

Private Function TempPath(ByVal extension As String) As String
    Randomize
    TempPath = Environ$("TEMP") & "\llangon_ficha_" & Format$(Now, "yyyymmdd_hhnnss") & "_" & Format$(CLng(Rnd() * 999999), "000000") & extension
End Function

Private Function RunHiddenAndWait(ByVal commandLine As String) As Long
    Dim shell As Object
    Set shell = CreateObject("WScript.Shell")
    RunHiddenAndWait = shell.Run(commandLine, 0, True)
End Function

Public Function LoadUtf8Text(ByVal path As String) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.LoadFromFile path
    LoadUtf8Text = stream.ReadText
    stream.Close
End Function

Public Sub SaveUtf8Text(ByVal path As String, ByVal value As String)
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.WriteText value
    stream.SaveToFile path, 2
    stream.Close
End Sub

Private Function ResultValue(ByVal path As String, ByVal key As String) As String
    Dim lines As Variant, fields As Variant, i As Long
    If Dir$(path) = "" Then Exit Function
    lines = Split(Replace(LoadUtf8Text(path), vbCrLf, vbLf), vbLf)
    For i = LBound(lines) To UBound(lines)
        fields = Split(CStr(lines(i)), vbTab, 2)
        If UBound(fields) = 1 Then
            If LCase$(Trim$(CStr(fields(0)))) = LCase$(key) Then ResultValue = Trim$(CStr(fields(1))): Exit Function
        End If
    Next i
End Function

Public Function ParseTsvLine(ByVal line As String) As Variant
    Dim values As New Collection, value As String, i As Long, ch As String, quoted As Boolean
    i = 1
    Do While i <= Len(line)
        ch = Mid$(line, i, 1)
        If ch = Chr$(34) Then
            If quoted And i < Len(line) And Mid$(line, i + 1, 1) = Chr$(34) Then
                value = value & Chr$(34): i = i + 1
            Else
                quoted = Not quoted
            End If
        ElseIf ch = vbTab And Not quoted Then
            values.Add value: value = ""
        Else
            value = value & ch
        End If
        i = i + 1
    Loop
    values.Add value
    Dim result() As String
    ReDim result(0 To values.Count - 1)
    For i = 1 To values.Count: result(i - 1) = CStr(values(i)): Next i
    ParseTsvLine = result
End Function

Private Function LoadClientsIntoCache(ByVal tsvPath As String) As Long
    Dim lines As Variant, fields As Variant, rows As New Collection
    Dim i As Long, j As Long, table As ListObject, ws As Worksheet, output() As Variant
    Dim oldValues As Variant, oldRowCount As Long, savedNumber As Long
    Dim savedDescription As String, savedSource As String, oldChoiceRef As String
    lines = Split(Replace(LoadUtf8Text(tsvPath), vbCrLf, vbLf), vbLf)
    For i = LBound(lines) To UBound(lines)
        If Trim$(CStr(lines(i))) <> "" And Left$(CStr(lines(i)), 1) <> "#" Then
            fields = ParseTsvLine(CStr(lines(i)))
            If LCase$(CStr(fields(0))) <> "id" And UBound(fields) >= 6 Then rows.Add fields
        End If
    Next i
    If rows.Count = 0 Then Err.Raise vbObjectError + 2201, "Ficha Llangon", "La Suite no devolvió clientes."

    Set ws = ThisWorkbook.Worksheets("_Listas")
    Set table = ws.ListObjects("tblClientes")
    oldRowCount = table.Range.Rows.Count
    oldValues = table.Range.Value
    oldChoiceRef = ThisWorkbook.Names("llg_client_choices").RefersTo
    On Error GoTo RestoreCache
    table.Resize ws.Range("G1:M" & (rows.Count + 1))
    ReDim output(1 To rows.Count, 1 To 7)
    For i = 1 To rows.Count
        fields = rows(i)
        For j = 0 To 6: output(i, j + 1) = fields(j): Next j
    Next i
    table.DataBodyRange.Value = output
    ThisWorkbook.Names("llg_client_choices").RefersTo = "='_Listas'!$H$2:$H$" & (rows.Count + 1)
    LoadClientsIntoCache = rows.Count
    Exit Function

RestoreCache:
    savedNumber = Err.Number
    savedDescription = Err.Description
    savedSource = Err.Source
    On Error Resume Next
    table.Resize ws.Range("G1:M" & oldRowCount)
    table.Range.Value = oldValues
    ThisWorkbook.Names("llg_client_choices").RefersTo = oldChoiceRef
    On Error GoTo 0
    Err.Raise savedNumber, savedSource, savedDescription
End Function

Public Function SelfTestClientCache() As String
    Dim ws As Worksheet, table As ListObject, oldValues As Variant, oldRowCount As Long
    Dim path As String, body As String, loaded As Long, passed As Boolean
    Dim savedNumber As Long, savedDescription As String, savedSource As String, oldChoiceRef As String
    Set ws = ThisWorkbook.Worksheets("_Listas")
    Set table = ws.ListObjects("tblClientes")
    oldRowCount = table.Range.Rows.Count
    oldValues = table.Range.Value
    oldChoiceRef = ThisWorkbook.Names("llg_client_choices").RefersTo
    path = TempPath(".tsv")
    On Error GoTo Failed
    body = "#schema_version" & vbTab & "1" & vbLf
    body = body & "id" & vbTab & "label" & vbTab & "display_name" & vbTab & "razon_social" & vbTab & "nombre_comercial" & vbTab & "active" & vbTab & "updated_at" & vbLf
    body = body & "91001" & vbTab & "Árbol - Árbol Norte, S.L. [ID 91001]" & vbTab & "Árbol" & vbTab & "Árbol Norte, S.L." & vbTab & "Árbol" & vbTab & "1" & vbTab & "2026-01-01T10:00:00" & vbLf
    body = body & "91002" & vbTab & "Árbol - Árbol Sur, S.L. [ID 91002]" & vbTab & "Árbol" & vbTab & "Árbol Sur, S.L." & vbTab & "Árbol" & vbTab & "1" & vbTab & "2026-01-02T10:00:00" & vbLf
    body = body & "91003" & vbTab & "Ñandú Histórico, S.A. (inactivo)" & vbTab & "Ñandú Histórico, S.A." & vbTab & "Ñandú Histórico, S.A." & vbTab & "" & vbTab & "0" & vbTab & "2025-01-01T10:00:00" & vbLf
    SaveUtf8Text path, body
    loaded = LoadClientsIntoCache(path)
    If loaded <> 3 Then Err.Raise vbObjectError + 2210, "Ficha Llangon", "La caché sintética no contiene tres clientes."
    If table.ListRows.Count <> 3 Then Err.Raise vbObjectError + 2211, "Ficha Llangon", "La tabla de clientes no se redimensionó correctamente."
    If InStr(1, CStr(table.DataBodyRange.Cells(1, 2).Value), "[ID 91001]", vbBinaryCompare) = 0 Then Err.Raise vbObjectError + 2212, "Ficha Llangon", "No se conservó el identificador para nombres duplicados."
    If InStr(1, CStr(table.DataBodyRange.Cells(3, 2).Value), "Ñandú", vbBinaryCompare) = 0 Then Err.Raise vbObjectError + 2213, "Ficha Llangon", "No se conservaron los caracteres españoles."
    If CStr(table.DataBodyRange.Cells(3, 6).Value) <> "0" Then Err.Raise vbObjectError + 2214, "Ficha Llangon", "No se conservó el estado inactivo."
    If InStr(1, ThisWorkbook.Names("llg_client_choices").RefersTo, "$H$4", vbTextCompare) = 0 Then Err.Raise vbObjectError + 2215, "Ficha Llangon", "El desplegable no se amplió con la caché."
    passed = True
    GoTo Cleanup

Failed:
    savedNumber = Err.Number
    savedDescription = Err.Description
    savedSource = Err.Source
Cleanup:
    On Error Resume Next
    table.Resize ws.Range("G1:M" & oldRowCount)
    table.Range.Value = oldValues
    ThisWorkbook.Names("llg_client_choices").RefersTo = oldChoiceRef
    If Dir$(path) <> "" Then Kill path
    On Error GoTo 0
    If Not passed Then Err.Raise savedNumber, savedSource, savedDescription
    SelfTestClientCache = "OK: cache sintética, duplicados, Unicode e inactivo"
End Function

Public Sub UpdateClients()
    Call RefreshClients(True)
End Sub

Public Function RefreshClients(Optional ByVal showMessages As Boolean = True) As Long
    Dim bridge As String, outputPath As String, resultPath As String, commandLine As String
    Dim exitCode As Long, count As Long, generatedAt As String, detail As String, message As String
    bridge = ResolveBridgePath()
    If bridge = "" Then
        If showMessages Then MsgBox "No se encuentra el componente local de Llangon Suite. La ficha seguirá usando la última caché disponible.", vbExclamation, "Actualizar clientes"
        Exit Function
    End If
    On Error GoTo UpdateError
    outputPath = TempPath(".tsv")
    resultPath = TempPath(".result.tsv")
    commandLine = QuoteArg(bridge) & " clients --output " & QuoteArg(outputPath) & " --result " & QuoteArg(resultPath)
    exitCode = RunHiddenAndWait(commandLine)
    If exitCode <> 0 Or Dir$(outputPath) = "" Then
        detail = ResultValue(resultPath, "message")
        message = "No se pudo actualizar la lista de clientes. Se conserva la caché anterior."
        If detail <> "" Then message = message & vbCrLf & vbCrLf & detail
        If showMessages Then MsgBox message, vbExclamation, "Actualizar clientes"
        GoTo Cleanup
    End If
    count = LoadClientsIntoCache(outputPath)
    generatedAt = ResultValue(resultPath, "generated_at")
    If generatedAt = "" Then generatedAt = Format$(Now, "yyyy-mm-dd hh:nn:ss")
    SetNamedValue "llg_control_clients_updated_at", Replace(Replace(Left$(generatedAt, 19), "T", " "), "Z", "")
    SetNamedValue "llg_control_bridge_version", ResultValue(resultPath, "bridge_version")
    SetNamedValue "llg_ui_cache_status", "Clientes actualizados: " & Format$(Now, "dd/mm/yyyy hh:nn") & " · " & count & " registros"
    SyncSelectedClientMetadata
    RefreshClients = count
    If showMessages Then MsgBox "Lista de clientes actualizada correctamente: " & count & " registros.", vbInformation, "Actualizar clientes"
    GoTo Cleanup

UpdateError:
    If showMessages Then MsgBox "La actualización no pudo aplicarse. Se conserva la caché anterior disponible en el libro." & vbCrLf & vbCrLf & Err.Description, vbExclamation, "Actualizar clientes"
Cleanup:
    On Error Resume Next
    If Dir$(outputPath) <> "" Then Kill outputPath
    If Dir$(resultPath) <> "" Then Kill resultPath
    On Error GoTo 0
End Function

Public Function FetchPlaceViaBridge(ByVal source As String, ByRef responseBody As String, ByRef errorText As String) As Boolean
    Dim bridge As String, sourcePath As String, outputPath As String, resultPath As String
    Dim commandLine As String, exitCode As Long, detail As String
    bridge = ResolveBridgePath()
    If bridge = "" Then
        errorText = "No se encuentra el componente local de Llangon Suite. Para importar una URL de PLACE en otro equipo, utilice un XML descargado."
        Exit Function
    End If

    sourcePath = TempPath(".source.txt")
    outputPath = TempPath(".place.tsv")
    resultPath = TempPath(".result.tsv")
    On Error GoTo Handler
    SaveUtf8Text sourcePath, source
    commandLine = QuoteArg(bridge) & " place --source-file " & QuoteArg(sourcePath) & " --output " & QuoteArg(outputPath) & " --result " & QuoteArg(resultPath)
    exitCode = RunHiddenAndWait(commandLine)
    If exitCode <> 0 Or Dir$(outputPath) = "" Then
        detail = ResultValue(resultPath, "message")
        If detail = "" Then detail = "No se pudo consultar PLACE."
        errorText = detail
        GoTo Cleanup
    End If
    responseBody = LoadUtf8Text(outputPath)
    FetchPlaceViaBridge = True
    GoTo Cleanup

Handler:
    errorText = "No se pudo ejecutar la consulta de PLACE: " & Err.Description
Cleanup:
    On Error Resume Next
    If Dir$(sourcePath) <> "" Then Kill sourcePath
    If Dir$(outputPath) <> "" Then Kill outputPath
    If Dir$(resultPath) <> "" Then Kill resultPath
    On Error GoTo 0
End Function

Public Sub SyncSelectedClientMetadata()
    Dim selected As String, table As ListObject, row As ListRow, labelIndex As Long
    selected = NamedText("llg_recipient_client_display")
    If selected = "" Then Exit Sub
    On Error Resume Next
    Set table = ThisWorkbook.Worksheets("_Listas").ListObjects("tblClientes")
    On Error GoTo 0
    If table Is Nothing Then Exit Sub
    If table.DataBodyRange Is Nothing Then Exit Sub
    labelIndex = table.ListColumns("Label").Index
    For Each row In table.ListRows
        If StrComp(Trim$(CStr(row.Range.Cells(1, labelIndex).Value)), selected, vbTextCompare) = 0 Or _
           StrComp(Trim$(CStr(row.Range.Cells(1, table.ListColumns("RazonSocial").Index).Value)), selected, vbTextCompare) = 0 Then
            SetNamedValue "llg_recipient_client_id", row.Range.Cells(1, table.ListColumns("ID").Index).Value
            SetNamedValue "llg_recipient_razon_social", row.Range.Cells(1, table.ListColumns("RazonSocial").Index).Value
            SetNamedValue "llg_recipient_client_active", IIf(CStr(row.Range.Cells(1, table.ListColumns("Activo").Index).Value) = "1", "true", "false")
            Exit Sub
        End If
    Next row
End Sub

Public Sub PreparePDF()
    Dim errors As Long, warnings As Long, draft As Boolean, bridge As String
    Dim payloadPath As String, resultPath As String, workbookCopyPath As String
    Dim outputPath As String, commandLine As String, exitCode As Long
    Dim finalPath As String, pages As String, imageCount As String, detail As String, answer As VbMsgBoxResult
    On Error GoTo PdfError
    EnsureDocumentMetadata
    errors = ReviewFicha(False)
    warnings = Val(NamedText("llg_quality_warnings"))
    If errors > 0 Then
        answer = MsgBox("La ficha contiene " & errors & " error(es). No puede emitirse como final." & vbCrLf & vbCrLf & "¿Desea generar un borrador identificado?", vbYesNo + vbExclamation, "Preparar PDF")
        If answer <> vbYes Then Exit Sub
        draft = True
    ElseIf warnings > 0 Then
        answer = MsgBox("La ficha no contiene errores, pero sí " & warnings & " advertencia(s)." & vbCrLf & vbCrLf & "¿Desea continuar con el PDF final?", vbYesNo + vbQuestion, "Preparar PDF")
        If answer <> vbYes Then Exit Sub
    End If

    bridge = ResolveBridgePath()
    If bridge = "" Then
        MsgBox "No se encuentra el motor PDF local. Puede abrir Informe_PDF y utilizar la exportación de contingencia de Excel.", vbExclamation, "Preparar PDF"
        AbrirInforme
        Exit Sub
    End If
    payloadPath = TempPath(".json")
    resultPath = TempPath(".result.tsv")
    workbookCopyPath = TempPath(".xlsm")
    outputPath = PdfOutputPath(draft, False)
    SaveUtf8Text payloadPath, BuildFichaPayloadJson(draft)
    ThisWorkbook.SaveCopyAs workbookCopyPath
    commandLine = QuoteArg(bridge) & " render-pdf --input " & QuoteArg(payloadPath) & " --output " & QuoteArg(outputPath) & " --result " & QuoteArg(resultPath) & " --workbook " & QuoteArg(workbookCopyPath)
    If draft Then commandLine = commandLine & " --draft"
    exitCode = RunHiddenAndWait(commandLine)
    If exitCode <> 0 Then
        detail = ResultValue(resultPath, "message")
        If detail <> "" Then detail = vbCrLf & vbCrLf & detail
        MsgBox "No se pudo generar el PDF. La ficha permanece intacta y puede utilizar Informe_PDF como contingencia." & detail, vbExclamation, "Preparar PDF"
        GoTo Cleanup
    End If
    finalPath = ResultValue(resultPath, "output")
    pages = ResultValue(resultPath, "pages")
    imageCount = ResultValue(resultPath, "images")
    If finalPath = "" Or Dir$(finalPath) = "" Then
        MsgBox "El motor no confirmó un PDF válido. Utilice Informe_PDF como contingencia.", vbExclamation, "Preparar PDF"
        GoTo Cleanup
    End If
    SetNamedValue "llg_last_pdf_path", finalPath
    answer = MsgBox("PDF generado correctamente" & IIf(pages <> "", " (" & pages & " páginas)", "") & "." & IIf(imageCount <> "", vbCrLf & "Imágenes trasladadas desde la ficha: " & imageCount & ".", "") & vbCrLf & vbCrLf & finalPath & vbCrLf & vbCrLf & "¿Desea abrirlo?", vbYesNo + vbInformation, "Preparar PDF")
    If answer = vbYes Then ThisWorkbook.FollowHyperlink finalPath
    GoTo Cleanup
PdfError:
    MsgBox "No se pudo preparar el PDF. La ficha permanece intacta." & vbCrLf & vbCrLf & Err.Description, vbExclamation, "Preparar PDF"
Cleanup:
    On Error Resume Next
    If Dir$(payloadPath) <> "" Then Kill payloadPath
    If Dir$(resultPath) <> "" Then Kill resultPath
    If Dir$(workbookCopyPath) <> "" Then Kill workbookCopyPath
    On Error GoTo 0
End Sub

Public Function PdfOutputPath(ByVal draft As Boolean, ByVal fallback As Boolean) As String
    Dim folder As String, expediente As String, cliente As String, suffix As String
    folder = ThisWorkbook.Path
    If folder = "" Then folder = Environ$("USERPROFILE") & "\Documents"
    expediente = SafeFilePart(NamedText("llg_tender_expediente"))
    cliente = SafeFilePart(NamedText("llg_recipient_client_display"))
    If expediente = "" Then expediente = "Sin_expediente"
    If cliente = "" Then cliente = "Sin_cliente"
    If draft Then suffix = "_BORRADOR"
    If fallback Then suffix = suffix & "_Excel"
    PdfOutputPath = folder & "\Ficha_Licitacion_" & expediente & "_" & cliente & suffix & ".pdf"
End Function

Private Function SafeFilePart(ByVal value As String) As String
    Dim invalid As Variant, item As Variant
    invalid = Array("\", "/", ":", "*", "?", Chr$(34), "<", ">", "|")
    value = Trim$(value)
    For Each item In invalid: value = Replace(value, CStr(item), "_"): Next item
    If Len(value) > 55 Then value = Left$(value, 55)
    SafeFilePart = value
End Function

Public Sub OpenLastPdfOrReport()
    Dim path As String
    path = NamedText("llg_last_pdf_path")
    If path <> "" And Dir$(path) <> "" Then
        ThisWorkbook.FollowHyperlink path
    Else
        AbrirInforme
    End If
End Sub
