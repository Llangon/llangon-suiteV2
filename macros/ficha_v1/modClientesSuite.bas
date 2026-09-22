Option Explicit

Private Const CLIENT_SHEET As String = "Clientes"
Private Const CLIENT_TABLE As String = "tblClientes"

Private Function QuoteClientArg(ByVal value As String) As String
    QuoteClientArg = Chr$(34) & Replace(value, Chr$(34), Chr$(34) & Chr$(34)) & Chr$(34)
End Function

Private Function ClientTempPath(ByVal extension As String) As String
    Randomize
    ClientTempPath = Environ$("TEMP") & "\llangon_clientes_" & _
        Format$(Now, "yyyymmdd_hhnnss") & "_" & Format$(CLng(Rnd() * 999999), "000000") & extension
End Function

Public Function RutaBridgeClientes() As String
    Dim candidate As String
    If LCase$(Trim$(Environ$("LLANGON_EXCEL_BRIDGE_DISABLE"))) = "1" Then Exit Function
    candidate = Trim$(Environ$("LLANGON_EXCEL_BRIDGE"))
    If candidate <> "" And Dir$(candidate) <> "" Then RutaBridgeClientes = candidate: Exit Function
    candidate = Environ$("LOCALAPPDATA") & "\LlangonSuite\bridge\llangon-excel-bridge.cmd"
    If Dir$(candidate) <> "" Then RutaBridgeClientes = candidate
End Function

Private Function RunClientBridge(ByVal commandLine As String) As Long
    Dim shell As Object
    Set shell = CreateObject("WScript.Shell")
    RunClientBridge = shell.Run(commandLine, 0, True)
End Function

Private Function ReadUtf8ClientFile(ByVal path As String) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.LoadFromFile path
    ReadUtf8ClientFile = stream.ReadText
    stream.Close
End Function

Private Sub WriteUtf8ClientFile(ByVal path As String, ByVal value As String)
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.WriteText value
    stream.SaveToFile path, 2
    stream.Close
End Sub

Private Function ClientResultValue(ByVal path As String, ByVal key As String) As String
    Dim lines As Variant, fields As Variant, i As Long
    If Dir$(path) = "" Then Exit Function
    lines = Split(Replace(ReadUtf8ClientFile(path), vbCrLf, vbLf), vbLf)
    For i = LBound(lines) To UBound(lines)
        fields = Split(CStr(lines(i)), vbTab, 2)
        If UBound(fields) = 1 Then
            If StrComp(Trim$(CStr(fields(0))), key, vbTextCompare) = 0 Then
                ClientResultValue = Trim$(CStr(fields(1)))
                Exit Function
            End If
        End If
    Next i
End Function

Private Function ParseClientTsvLine(ByVal line As String) As Variant
    Dim values As New Collection, value As String, i As Long, ch As String, quoted As Boolean
    Dim result() As String
    i = 1
    Do While i <= Len(line)
        ch = Mid$(line, i, 1)
        If ch = Chr$(34) Then
            If quoted And i < Len(line) And Mid$(line, i + 1, 1) = Chr$(34) Then
                value = value & Chr$(34)
                i = i + 1
            Else
                quoted = Not quoted
            End If
        ElseIf ch = vbTab And Not quoted Then
            values.Add value
            value = ""
        Else
            value = value & ch
        End If
        i = i + 1
    Loop
    values.Add value
    ReDim result(0 To values.Count - 1)
    For i = 1 To values.Count
        result(i - 1) = CStr(values(i))
    Next i
    ParseClientTsvLine = result
End Function

Private Function ParseClientTsvRecords(ByVal content As String) As Collection
    Dim records As New Collection, record As String, normalized As String
    Dim i As Long, ch As String, quoted As Boolean
    normalized = Replace(Replace(content, vbCrLf, vbLf), vbCr, vbLf)
    i = 1
    Do While i <= Len(normalized)
        ch = Mid$(normalized, i, 1)
        If ch = Chr$(34) Then
            record = record & ch
            If quoted And i < Len(normalized) And Mid$(normalized, i + 1, 1) = Chr$(34) Then
                record = record & Chr$(34)
                i = i + 1
            Else
                quoted = Not quoted
            End If
        ElseIf ch = vbLf And Not quoted Then
            records.Add record
            record = ""
        Else
            record = record & ch
        End If
        i = i + 1
    Loop
    If record <> "" Then records.Add record
    If quoted Then Err.Raise vbObjectError + 2509, "Clientes Llangon", "La Suite devolvió un texto entrecomillado incompleto."
    Set ParseClientTsvRecords = records
End Function

Private Sub SetClientTableContent(ByVal table As ListObject, ByVal values As Variant)
    Dim rowCount As Long, columnCount As Long, i As Long, j As Long
    Dim dataValues() As Variant
    rowCount = UBound(values, 1)
    columnCount = UBound(values, 2)
    For j = 1 To columnCount
        table.ListColumns(j).Name = "__llg_tmp_" & CStr(j)
    Next j
    For j = 1 To columnCount
        table.ListColumns(j).Name = CStr(values(1, j))
    Next j
    If rowCount > 1 Then
        ReDim dataValues(1 To rowCount - 1, 1 To columnCount)
        For i = 2 To rowCount
            For j = 1 To columnCount
                dataValues(i - 1, j) = values(i, j)
            Next j
        Next i
        table.DataBodyRange.Value = dataValues
    ElseIf Not table.DataBodyRange Is Nothing Then
        table.DataBodyRange.ClearContents
    End If
End Sub

Public Function CargarClientesDesdeTsv(ByVal tsvPath As String) As Long
    Dim ws As Worksheet, table As ListObject, records As Collection, fields As Variant, headers As Variant
    Dim rows As New Collection, output() As Variant, oldValues As Variant, seenHeaders As Object
    Dim i As Long, j As Long, columnCount As Long, labelColumn As Long
    Dim oldLastRow As Long, oldLastColumn As Long, newLastRow As Long, newLastColumn As Long
    Dim oldRangeAddress As String, savedNumber As Long, savedDescription As String, savedSource As String

    Set records = ParseClientTsvRecords(ReadUtf8ClientFile(tsvPath))
    For i = 1 To records.Count
        If Trim$(CStr(records(i))) <> "" And Left$(CStr(records(i)), 1) <> "#" Then
            fields = ParseClientTsvLine(CStr(records(i)))
            If columnCount = 0 Then
                headers = fields
                columnCount = UBound(headers) + 1
                If columnCount < 7 Or columnCount > 16384 Then Err.Raise vbObjectError + 2503, "Clientes Llangon", "La estructura de columnas devuelta por la Suite no es válida."
                Set seenHeaders = CreateObject("Scripting.Dictionary")
                seenHeaders.CompareMode = vbTextCompare
                For j = 0 To columnCount - 1
                    If Trim$(CStr(headers(j))) = "" Then Err.Raise vbObjectError + 2504, "Clientes Llangon", "La Suite devolvió una columna sin nombre."
                    If seenHeaders.Exists(Trim$(CStr(headers(j)))) Then Err.Raise vbObjectError + 2505, "Clientes Llangon", "La Suite devolvió columnas duplicadas."
                    seenHeaders.Add Trim$(CStr(headers(j))), True
                    If LCase$(Trim$(CStr(headers(j)))) = "label" Then labelColumn = j + 1
                Next j
            Else
                If UBound(fields) + 1 <> columnCount Then Err.Raise vbObjectError + 2506, "Clientes Llangon", "Una fila de clientes no coincide con la cabecera dinámica."
                rows.Add fields
            End If
        End If
    Next i
    If columnCount = 0 Then Err.Raise vbObjectError + 2507, "Clientes Llangon", "La Suite no devolvió la cabecera de clientes."
    If labelColumn = 0 Then Err.Raise vbObjectError + 2508, "Clientes Llangon", "La Suite no devolvió la etiqueta necesaria para los desplegables."
    If rows.Count = 0 Then Err.Raise vbObjectError + 2501, "Clientes Llangon", "La Suite no devolvió clientes."

    Set ws = ThisWorkbook.Worksheets(CLIENT_SHEET)
    Set table = ws.ListObjects(CLIENT_TABLE)
    oldRangeAddress = table.Range.Address
    oldLastRow = table.Range.Row + table.Range.Rows.Count - 1
    oldLastColumn = table.Range.Column + table.Range.Columns.Count - 1
    oldValues = table.Range.Value
    On Error GoTo RestorePrevious

    newLastRow = rows.Count + 6
    newLastColumn = columnCount
    table.Resize ws.Range(ws.Cells(6, 1), ws.Cells(newLastRow, newLastColumn))
    Set table = ws.ListObjects(CLIENT_TABLE)
    ReDim output(1 To rows.Count + 1, 1 To columnCount)
    For j = 0 To columnCount - 1
        output(1, j + 1) = headers(j)
    Next j
    For i = 1 To rows.Count
        fields = rows(i)
        For j = 0 To columnCount - 1
            output(i + 1, j + 1) = fields(j)
        Next j
    Next i
    SetClientTableContent table, output
    If oldLastRow > newLastRow Then ws.Range(ws.Cells(newLastRow + 1, 1), ws.Cells(oldLastRow, oldLastColumn)).ClearContents
    If oldLastColumn > newLastColumn Then ws.Range(ws.Cells(6, newLastColumn + 1), ws.Cells(newLastRow, oldLastColumn)).ClearContents
    FormatDynamicClientColumns ws, headers, columnCount
    ThisWorkbook.Names("ListaClientes").RefersTo = "='Clientes'!" & _
        ws.Range(ws.Cells(7, labelColumn), ws.Cells(newLastRow, labelColumn)).Address
    CargarClientesDesdeTsv = rows.Count
    Exit Function

RestorePrevious:
    savedNumber = Err.Number
    savedDescription = Err.Description
    savedSource = Err.Source
    On Error Resume Next
    Set table = ws.ListObjects(CLIENT_TABLE)
    table.Resize ws.Range(oldRangeAddress)
    Set table = ws.ListObjects(CLIENT_TABLE)
    SetClientTableContent table, oldValues
    On Error GoTo 0
    Err.Raise savedNumber, savedSource, savedDescription
End Function

Private Sub FormatDynamicClientColumns(ByVal ws As Worksheet, ByVal headers As Variant, ByVal columnCount As Long)
    Dim i As Long, key As String, width As Double
    ws.Range("A1").MergeArea.UnMerge
    ws.Range(ws.Cells(1, 1), ws.Cells(1, columnCount)).Merge
    ws.Range("D4").MergeArea.UnMerge
    ws.Range(ws.Cells(4, 4), ws.Cells(4, columnCount)).Merge
    For i = 0 To columnCount - 1
        key = LCase$(Trim$(CStr(headers(i))))
        Select Case key
            Case "id", "activo", "active": width = 10
            Case "label": width = 42
            Case "display_name", "razon_social", "nombre_comercial", "domicilio_fiscal", "observaciones_internas", "condiciones_particulares": width = 30
            Case "email_principal", "email_alternativo", "representante_email": width = 25
            Case "created_at", "updated_at", "desactivado_at": width = 21
            Case Else: width = 18
        End Select
        ws.Columns(i + 1).ColumnWidth = width
    Next i
End Sub

Public Sub ActualizarClientes()
    Dim bridge As String, outputPath As String, resultPath As String, commandLine As String
    Dim exitCode As Long, count As Long, detail As String, generatedAt As String
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(CLIENT_SHEET)
    bridge = RutaBridgeClientes()
    If bridge = "" Then
        ws.Range("E2").Value = "Puente local no instalado"
        MsgBox "No se encuentra el puente local de Llangon Suite." & vbCrLf & vbCrLf & _
            "Instálelo una sola vez ejecutando scripts\windows\install_llangon_excel_bridge.ps1 desde la Suite.", _
            vbExclamation, "Actualizar clientes"
        Exit Sub
    End If

    On Error GoTo UpdateFailed
    outputPath = ClientTempPath(".tsv")
    resultPath = ClientTempPath(".result.tsv")
    commandLine = QuoteClientArg(bridge) & " clients --output " & QuoteClientArg(outputPath) & _
        " --result " & QuoteClientArg(resultPath)
    exitCode = RunClientBridge(commandLine)
    If exitCode <> 0 Or Dir$(outputPath) = "" Then
        detail = ClientResultValue(resultPath, "message")
        If detail = "" Then detail = "El puente local no devolvió una lista válida."
        Err.Raise vbObjectError + 2502, "Clientes Llangon", detail
    End If

    count = CargarClientesDesdeTsv(outputPath)
    generatedAt = ClientResultValue(resultPath, "generated_at")
    If generatedAt = "" Then generatedAt = Format$(Now, "yyyy-mm-dd hh:nn:ss")
    ws.Range("B2").Value = Replace(Replace(Left$(generatedAt, 19), "T", " "), "Z", "")
    ws.Range("E2").Value = count & " clientes · solo lectura"
    MsgBox "Lista de clientes actualizada correctamente: " & count & " registros.", vbInformation, "Actualizar clientes"
    GoTo Cleanup

UpdateFailed:
    ws.Range("E2").Value = "Error de actualización"
    MsgBox "No se pudo actualizar la lista. Se conserva el contenido anterior." & vbCrLf & vbCrLf & _
        Err.Description, vbExclamation, "Actualizar clientes"
Cleanup:
    On Error Resume Next
    If Dir$(outputPath) <> "" Then Kill outputPath
    If Dir$(resultPath) <> "" Then Kill resultPath
    On Error GoTo 0
End Sub

Public Function SelfTestClientesSuite() As String
    Dim ws As Worksheet, table As ListObject, path As String, body As String
    Dim oldValues As Variant, oldRangeAddress As String, oldUpdated As Variant, oldStatus As Variant, oldListRef As String
    Dim currentLastRow As Long, currentLastColumn As Long
    Dim loaded As Long, passed As Boolean, savedNumber As Long, savedDescription As String
    Set ws = ThisWorkbook.Worksheets(CLIENT_SHEET)
    Set table = ws.ListObjects(CLIENT_TABLE)
    oldRangeAddress = table.Range.Address
    oldValues = table.Range.Value
    oldUpdated = ws.Range("B2").Value
    oldStatus = ws.Range("E2").Value
    oldListRef = ThisWorkbook.Names("ListaClientes").RefersTo
    path = ClientTempPath(".tsv")
    On Error GoTo Failed
    body = "#schema_version" & vbTab & "2" & vbLf & _
        "#dynamic_columns" & vbTab & "true" & vbLf & _
        "id" & vbTab & "label" & vbTab & "display_name" & vbTab & "razon_social" & vbTab & "nombre_comercial" & vbTab & "active" & vbTab & "updated_at" & vbTab & "nif_cif" & vbTab & "domicilio_fiscal" & vbTab & "observaciones_internas" & vbTab & "campo_futuro" & vbLf & _
        "91001" & vbTab & "Árbol - Árbol Norte, S.L. [ID 91001]" & vbTab & "Árbol" & vbTab & "Árbol Norte, S.L." & vbTab & "Árbol" & vbTab & "1" & vbTab & "2026-01-01T10:00:00" & vbTab & "B91001001" & vbTab & "Calle Norte 1" & vbTab & Chr$(34) & "Primera línea" & vbLf & "Segunda línea con " & Chr$(34) & Chr$(34) & "comillas" & Chr$(34) & Chr$(34) & Chr$(34) & vbTab & "Valor nuevo" & vbLf & _
        "91002" & vbTab & "Ñandú Histórico, S.A. (inactivo)" & vbTab & "Ñandú Histórico, S.A." & vbTab & "Ñandú Histórico, S.A." & vbTab & "" & vbTab & "0" & vbTab & "2025-01-01T10:00:00" & vbTab & "A91002002" & vbTab & "Calle Sur 2" & vbTab & "Sin observaciones" & vbTab & "Otro valor" & vbLf
    WriteUtf8ClientFile path, body
    loaded = CargarClientesDesdeTsv(path)
    Set table = ws.ListObjects(CLIENT_TABLE)
    If loaded <> 2 Then Err.Raise vbObjectError + 2510, "Clientes Llangon", "No se cargaron dos clientes simulados."
    If table.ListColumns.Count <> 11 Then Err.Raise vbObjectError + 2513, "Clientes Llangon", "La tabla no adoptó las columnas dinámicas."
    If InStr(1, CStr(table.DataBodyRange.Cells(1, 10).Value), vbLf, vbBinaryCompare) = 0 Then Err.Raise vbObjectError + 2515, "Clientes Llangon", "No se conservó un texto multilínea."
    If CStr(table.DataBodyRange.Cells(1, 11).Value) <> "Valor nuevo" Then Err.Raise vbObjectError + 2514, "Clientes Llangon", "No se importó un campo futuro simulado."
    If InStr(1, CStr(table.DataBodyRange.Cells(2, 2).Value), "Ñandú", vbBinaryCompare) = 0 Then Err.Raise vbObjectError + 2511, "Clientes Llangon", "No se conservó el texto Unicode."
    If CStr(table.DataBodyRange.Cells(2, 6).Value) <> "0" Then Err.Raise vbObjectError + 2512, "Clientes Llangon", "No se conservó el estado inactivo."
    passed = True
    GoTo Restore
Failed:
    savedNumber = Err.Number
    savedDescription = Err.Description
Restore:
    On Error Resume Next
    Set table = ws.ListObjects(CLIENT_TABLE)
    currentLastRow = table.Range.Row + table.Range.Rows.Count - 1
    currentLastColumn = table.Range.Column + table.Range.Columns.Count - 1
    ws.Range(ws.Cells(6, 1), ws.Cells(currentLastRow, currentLastColumn)).ClearContents
    table.Resize ws.Range(oldRangeAddress)
    Set table = ws.ListObjects(CLIENT_TABLE)
    SetClientTableContent table, oldValues
    ws.Range("B2").Value = oldUpdated
    ws.Range("E2").Value = oldStatus
    ThisWorkbook.Names("ListaClientes").RefersTo = oldListRef
    If Dir$(path) <> "" Then Kill path
    On Error GoTo 0
    If Not passed Then Err.Raise savedNumber, "Clientes Llangon", savedDescription
    SelfTestClientesSuite = "OK: columnas dinámicas, multilinea, campo futuro, Unicode e inactivos"
End Function
