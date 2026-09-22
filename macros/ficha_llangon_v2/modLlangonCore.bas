Option Explicit

Public Const LLANGON_TEMPLATE_VERSION As String = "2.1.0"
Public Const LLANGON_PAYLOAD_VERSION As String = "1.1"
Private mLastReviewMessage As String
Private mReviewStage As String

Public Function SelfTestCompile() As String
    SelfTestCompile = "Ficha Llangon " & LLANGON_TEMPLATE_VERSION & " / payload " & LLANGON_PAYLOAD_VERSION
End Function

Public Function ReviewFichaLastMessage() As String
    ReviewFichaLastMessage = mLastReviewMessage
End Function

Public Function NamedRange(ByVal rangeName As String) As Range
    On Error Resume Next
    Set NamedRange = ThisWorkbook.Names(rangeName).RefersToRange
    On Error GoTo 0
End Function

Public Function NamedText(ByVal rangeName As String) As String
    Dim rng As Range, cell As Range, value As Variant, result As String
    Set rng = NamedRange(rangeName)
    If rng Is Nothing Then Exit Function
    If rng.Cells.CountLarge = 1 Then
        value = rng.Value
        If Not IsError(value) Then NamedText = Trim$(CStr(value))
        Exit Function
    End If
    For Each cell In rng.Cells
        If Not cell.MergeCells Or cell.Address = cell.MergeArea.Cells(1, 1).Address Then
            value = cell.Value
            If Not IsError(value) Then
                If Trim$(CStr(value)) <> "" Then
                    If result <> "" Then result = result & vbLf
                    result = result & Trim$(CStr(value))
                End If
            End If
        End If
    Next cell
    NamedText = result
End Function

Public Sub SetNamedValue(ByVal rangeName As String, ByVal value As Variant)
    Dim rng As Range
    Set rng = NamedRange(rangeName)
    If rng Is Nothing Then Err.Raise vbObjectError + 2101, "Ficha Llangon", "Falta el campo interno " & rangeName & "."
    rng.Value = value
End Sub

Public Sub EnsureDocumentMetadata()
    If NamedText("llg_control_document_id") = "" Then
        On Error Resume Next
        SetNamedValue "llg_control_document_id", Replace(Replace(CreateObject("Scriptlet.TypeLib").GUID, "{", ""), "}", "")
        If Err.Number <> 0 Then
            Err.Clear
            Randomize
            SetNamedValue "llg_control_document_id", Format$(Now, "yyyymmddhhnnss") & "-" & Format$(CLng(Rnd() * 999999), "000000")
        End If
        On Error GoTo 0
    End If
    If NamedText("llg_control_created_at") = "" Then SetNamedValue "llg_control_created_at", Format$(Now, "yyyy-mm-dd\Thh:nn:ss")
    SetNamedValue "llg_control_template_version", LLANGON_TEMPLATE_VERSION
    SetNamedValue "llg_control_payload_version", LLANGON_PAYLOAD_VERSION
End Sub

Public Function IsAffirmative(ByVal value As String) As Boolean
    value = LCase$(Trim$(value))
    IsAffirmative = (value = "sí" Or value = "si")
End Function

Private Function IsAllowedState(ByVal value As String) As Boolean
    Select Case LCase$(Trim$(value))
        Case "", "sí", "si", "no", "no consta", "no aplica"
            IsAllowedState = True
    End Select
End Function

Private Sub AddIssue(ByVal target As Collection, ByVal message As String)
    target.Add message
End Sub

Private Function JoinIssues(ByVal title As String, ByVal values As Collection, ByVal maximum As Long) As String
    Dim i As Long, limit As Long, result As String
    If values.Count = 0 Then Exit Function
    result = title & " (" & values.Count & "):" & vbCrLf
    limit = values.Count
    If limit > maximum Then limit = maximum
    For i = 1 To limit
        result = result & "- " & CStr(values(i)) & vbCrLf
    Next i
    If values.Count > limit Then result = result & "- ... y " & (values.Count - limit) & " más." & vbCrLf
    JoinIssues = result
End Function

Private Function ValidHttpUrl(ByVal value As String) As Boolean
    value = LCase$(Trim$(value))
    ValidHttpUrl = (value = "" Or Left$(value, 7) = "http://" Or Left$(value, 8) = "https://")
End Function

Public Function FindSectionRow(ByVal title As String) As Long
    Dim found As Range
    Set found = ThisWorkbook.Worksheets("Ficha").Columns("B").Find( _
        What:=title, After:=ThisWorkbook.Worksheets("Ficha").Range("B1"), _
        LookIn:=xlValues, LookAt:=xlWhole, SearchOrder:=xlByRows, _
        SearchDirection:=xlNext, MatchCase:=False)
    If Not found Is Nothing Then FindSectionRow = found.Row
End Function

Public Function SectionBodyRange(ByVal sectionTitle As String, ByVal nextSectionTitle As String, _
                                 ByVal headerRows As Long, Optional ByVal footerLabel As String = "") As Range
    Dim ws As Worksheet, firstRow As Long, lastRow As Long, nextRow As Long, rowNumber As Long
    Set ws = ThisWorkbook.Worksheets("Ficha")
    firstRow = FindSectionRow(sectionTitle)
    If firstRow = 0 Then Exit Function
    firstRow = firstRow + headerRows
    If nextSectionTitle <> "" Then nextRow = FindSectionRow(nextSectionTitle)
    If nextRow > firstRow Then
        lastRow = nextRow - 1
    Else
        lastRow = ws.Cells(ws.Rows.Count, "B").End(xlUp).Row
        If ws.PageSetup.PrintArea <> "" Then lastRow = ws.Range(ws.PageSetup.PrintArea).Rows(ws.Range(ws.PageSetup.PrintArea).Rows.Count).Row
    End If
    If footerLabel <> "" Then
        For rowNumber = firstRow To lastRow
            If Application.CountIf(ws.Range("B" & rowNumber & ":H" & rowNumber), footerLabel) > 0 Then
                lastRow = rowNumber - 1
                Exit For
            End If
        Next rowNumber
    End If
    If lastRow >= firstRow Then Set SectionBodyRange = ws.Range("B" & firstRow & ":H" & lastRow)
End Function

Public Function RangeHasContent(ByVal target As Range) As Boolean
    Dim row As Range, cell As Range
    If target Is Nothing Then Exit Function
    For Each row In target.Rows
        For Each cell In row.Cells
            If Not cell.MergeCells Or cell.Address = cell.MergeArea.Cells(1, 1).Address Then
                If Trim$(CStr(cell.Value)) <> "" Then RangeHasContent = True: Exit Function
            End If
        Next cell
    Next row
End Function

Private Function CalendarCoversYear(ByVal targetYear As Long) As Boolean
    Dim table As ListObject, cell As Range
    On Error Resume Next
    Set table = ThisWorkbook.Worksheets("_Listas").ListObjects("tblFestivos")
    On Error GoTo 0
    If table Is Nothing Then Exit Function
    If table.DataBodyRange Is Nothing Then Exit Function
    For Each cell In table.ListColumns("Fecha").DataBodyRange.Cells
        If IsDate(cell.Value) Then
            If Year(CDate(cell.Value)) = targetYear Then CalendarCoversYear = True: Exit Function
        End If
    Next cell
End Function

Private Function IsRegisteredHoliday(ByVal targetDate As Date) As Boolean
    Dim table As ListObject, cell As Range
    On Error Resume Next
    Set table = ThisWorkbook.Worksheets("_Listas").ListObjects("tblFestivos")
    On Error GoTo 0
    If table Is Nothing Then Exit Function
    If table.DataBodyRange Is Nothing Then Exit Function
    For Each cell In table.ListColumns("Fecha").DataBodyRange.Cells
        If IsDate(cell.Value) Then
            If CLng(CDate(cell.Value)) = CLng(targetDate) Then IsRegisteredHoliday = True: Exit Function
        End If
    Next cell
End Function

Public Function DeadlineWarningText(ByVal deadlineValue As Variant) As String
    Dim deadline As Date, result As String
    Application.Volatile True
    If IsError(deadlineValue) Then Exit Function
    If Trim$(CStr(deadlineValue)) = "" Then Exit Function
    If Not IsDate(deadlineValue) Then
        DeadlineWarningText = "AVISO: fecha límite no válida"
        Exit Function
    End If
    deadline = DateValue(CDate(deadlineValue))
    If deadline < Date Then
        AppendDeadlineWarning result, "fecha vencida"
    ElseIf deadline <= Date + 3 Then
        AppendDeadlineWarning result, "plazo de tres días o menos"
    End If
    If Weekday(deadline, vbMonday) > 5 Then AppendDeadlineWarning result, "fin de semana"
    If IsRegisteredHoliday(deadline) Then AppendDeadlineWarning result, "festivo nacional registrado"
    If Not CalendarCoversYear(Year(deadline)) Then AppendDeadlineWarning result, "calendario sin cobertura para " & Year(deadline)
    If result = "" Then
        DeadlineWarningText = "Fecha revisada"
    Else
        DeadlineWarningText = "AVISO: " & result
    End If
End Function

Private Sub AppendDeadlineWarning(ByRef result As String, ByVal warningText As String)
    If result <> "" Then result = result & " · "
    result = result & warningText
End Sub

Public Function SelfTestDeadlineWarning() As String
    Dim nearText As String, weekendText As String, probe As Date
    nearText = DeadlineWarningText(Date + 2)
    If InStr(1, nearText, "tres días o menos", vbTextCompare) = 0 Then Err.Raise vbObjectError + 2110, "Ficha Llangon", "El aviso visible no detecta un plazo próximo."
    probe = DateSerial(2030, 1, 5)
    weekendText = DeadlineWarningText(probe)
    If InStr(1, weekendText, "fin de semana", vbTextCompare) = 0 Then Err.Raise vbObjectError + 2111, "Ficha Llangon", "El aviso visible no detecta el fin de semana."
    SelfTestDeadlineWarning = "OK: aviso visible de fecha dinámico"
End Function

Private Sub ValidateDependency(ByVal stateName As String, ByVal detailName As String, ByVal label As String, ByVal errors As Collection, ByVal warnings As Collection)
    Dim state As String
    state = NamedText(stateName)
    If Not IsAllowedState(state) Then AddIssue errors, label & ": estado no válido."
    If IsAffirmative(state) And NamedText(detailName) = "" Then AddIssue warnings, label & ": falta el detalle."
End Sub

Private Sub ValidateCriteria(ByVal sectionTitle As String, ByVal nextSectionTitle As String, ByVal label As String, ByVal errors As Collection, ByVal warnings As Collection, ByRef criteriaCount As Long, ByRef pointsTotal As Double)
    Dim dataRange As Range, row As Range, criterion As String, points As Variant
    Set dataRange = SectionBodyRange(sectionTitle, nextSectionTitle, 2, "Total puntos")
    If dataRange Is Nothing Then AddIssue errors, "No se encuentra la sección " & label & ".": Exit Sub
    For Each row In dataRange.Rows
        criterion = Trim$(CStr(row.Cells(1, 1).Value))
        points = row.Cells(1, 7).Value
        If criterion <> "" Or Trim$(CStr(points)) <> "" Then
            criteriaCount = criteriaCount + 1
            If criterion = "" Then AddIssue errors, label & ": hay una fila con puntos pero sin criterio."
            If Trim$(CStr(points)) <> "" Then
                If Not IsNumeric(points) Then
                    AddIssue errors, label & ": una puntuación no es numérica."
                ElseIf CDbl(points) < 0 Then
                    AddIssue errors, label & ": una puntuación es negativa."
                Else
                    pointsTotal = pointsTotal + CDbl(points)
                End If
            End If
        End If
    Next row
End Sub

Private Sub CheckBrokenNames(ByVal errors As Collection)
    Dim item As Name
    For Each item In ThisWorkbook.Names
        If InStr(1, item.RefersTo, "#REF!", vbTextCompare) > 0 Then AddIssue errors, "Referencia interna rota: " & item.Name & "."
    Next item
End Sub

Public Function ReviewFicha(Optional ByVal showMessage As Boolean = True) As Long
    Dim errors As New Collection, warnings As New Collection, information As New Collection
    Dim deadline As Date, deadlineTime As Date, criteriaCount As Long, pointsTotal As Double
    Dim msg As String, cacheDate As String, staleDays As Long, timeValue As Variant
    Dim fatalNumber As Long, fatalDescription As String

    On Error GoTo FatalError
    mReviewStage = "metadatos"
    EnsureDocumentMetadata
    mReviewStage = "cliente seleccionado"
    SyncSelectedClientMetadata

    mReviewStage = "campos obligatorios"
    If NamedText("llg_recipient_client_display") = "" Then AddIssue errors, "Falta el cliente destinatario."
    If NamedText("llg_tender_expediente") = "" Then AddIssue errors, "Falta el expediente."
    If NamedText("llg_tender_objeto") = "" Then AddIssue errors, "Falta el objeto o título."

    mReviewStage = "fecha y hora límite"
    If NamedText("llg_tender_fecha_limite") = "" Then
        AddIssue errors, "Falta la fecha límite."
    ElseIf Not IsDate(NamedRange("llg_tender_fecha_limite").Value) Then
        AddIssue errors, "La fecha límite no es válida."
    Else
        deadline = CDate(NamedRange("llg_tender_fecha_limite").Value)
        If DateValue(deadline) < Date Then AddIssue warnings, "La fecha límite ya ha vencido."
        If DateValue(deadline) >= Date And DateValue(deadline) <= Date + 3 Then AddIssue warnings, "La fecha límite está a tres días o menos."
        If Weekday(deadline, vbMonday) > 5 Then AddIssue warnings, "La fecha límite cae en fin de semana."
        If IsRegisteredHoliday(deadline) Then AddIssue warnings, "La fecha límite coincide con un festivo nacional registrado."
        If Not CalendarCoversYear(Year(deadline)) Then AddIssue warnings, "El calendario no acredita cobertura para " & Year(deadline) & "."
    End If

    If NamedText("llg_tender_hora_limite") <> "" Then
        timeValue = NamedRange("llg_tender_hora_limite").Value
        If IsNumeric(timeValue) Then
            If CDbl(timeValue) >= 0# And CDbl(timeValue) < 1# Then
                deadlineTime = CDate(CDbl(timeValue))
            Else
                AddIssue errors, "La hora límite no es válida."
            End If
        ElseIf IsDate(timeValue) Then
            deadlineTime = TimeValue(timeValue)
        Else
            AddIssue errors, "La hora límite no es válida."
        End If
        If deadlineTime > 0 And deadlineTime < TimeSerial(12, 0, 0) Then AddIssue warnings, "La hora límite es anterior a las 12:00."
    End If

    mReviewStage = "formatos básicos"
    If Not ValidHttpUrl(NamedText("llg_tender_enlace")) Then AddIssue errors, "El enlace debe comenzar por http:// o https://."
    If NamedText("llg_tender_presupuesto_base") <> "" And Not IsNumeric(NamedRange("llg_tender_presupuesto_base").Value) Then AddIssue errors, "El presupuesto base no es numérico."
    If NamedText("llg_tender_valor_estimado") <> "" And Not IsNumeric(NamedRange("llg_tender_valor_estimado").Value) Then AddIssue errors, "El valor estimado no es numérico."
    If NamedText("llg_analysis_numero_sobres") <> "" And Not IsNumeric(NamedRange("llg_analysis_numero_sobres").Value) Then AddIssue warnings, "Revise el número de sobres."

    mReviewStage = "dependencias"
    ValidateDependency "llg_analysis_prorroga", "llg_analysis_prorroga_comentario", "Prórroga", errors, warnings
    ValidateDependency "llg_analysis_garantia_provisional", "llg_analysis_garantia_provisional_comentario", "Garantía provisional", errors, warnings
    ValidateDependency "llg_analysis_garantia_definitiva", "llg_analysis_garantia_definitiva_comentario", "Garantía definitiva", errors, warnings
    ValidateDependency "llg_analysis_garantia_complementaria", "llg_analysis_garantia_complementaria_comentario", "Garantía complementaria", errors, warnings
    ValidateDependency "llg_analysis_adscripcion_medios", "llg_analysis_adscripcion_medios_comentario", "Adscripción de medios", errors, warnings
    ValidateDependency "llg_analysis_fichas_tecnicas", "llg_analysis_fichas_tecnicas_comentario", "Fichas técnicas", errors, warnings
    ValidateDependency "llg_analysis_memoria_tecnica", "llg_analysis_memoria_tecnica_comentario", "Memoria técnica", errors, warnings
    ValidateDependency "llg_analysis_subcontratacion", "llg_analysis_subcontratacion_comentario", "Subcontratación", errors, warnings
    ValidateDependency "llg_analysis_muestras", "llg_analysis_muestras_comentario", "Muestras", errors, warnings

    mReviewStage = "criterios"
    ValidateCriteria "Criterios sujetos a juicio de valor", "Criterios evaluables mediante fórmula", "Criterios sujetos a juicio de valor", errors, warnings, criteriaCount, pointsTotal
    ValidateCriteria "Criterios evaluables mediante fórmula", "Condiciones especiales de ejecución", "Criterios mediante fórmula", errors, warnings, criteriaCount, pointsTotal
    If criteriaCount = 0 Then AddIssue information, "No se han introducido criterios de adjudicación."
    If criteriaCount > 0 And Abs(pointsTotal - 100#) > 0.001 Then AddIssue warnings, "La suma de criterios es " & Format$(pointsTotal, "0.##") & "; revise si debe sumar 100."
    If Not RangeHasContent(SectionBodyRange("Observaciones", "", 1)) Then AddIssue information, "No hay observaciones generales."

    mReviewStage = "caché y vínculos"
    cacheDate = NamedText("llg_control_clients_updated_at")
    staleDays = Val(NamedText("llg_config_cache_stale_days"))
    If cacheDate = "" Then
        AddIssue information, "La lista de clientes no se ha actualizado desde la Suite."
    ElseIf IsDate(cacheDate) And staleDays > 0 Then
        If DateDiff("d", CDate(cacheDate), Now) > staleDays Then AddIssue warnings, "La caché de clientes tiene más de " & staleDays & " días."
    End If

    If NamedText("llg_recipient_client_id") = "" Then AddIssue warnings, "El cliente no tiene un ID asociado; la ficha sigue siendo válida en modo offline."
    If LCase$(NamedText("llg_recipient_client_active")) = "false" Or NamedText("llg_recipient_client_active") = "0" Then AddIssue warnings, "El cliente seleccionado figura como inactivo; se conserva el vínculo histórico."

    mReviewStage = "integridad y resultado"
    CheckBrokenNames errors
    SetNamedValue "llg_quality_errors", errors.Count
    SetNamedValue "llg_quality_warnings", warnings.Count
    SetNamedValue "llg_quality_info", information.Count
    SetNamedValue "llg_quality_last_review_at", Format$(Now, "yyyy-mm-dd hh:nn:ss")
    If errors.Count > 0 Then
        SetNamedValue "llg_quality_status", "ERROR"
        SetNamedValue "llg_ui_review_status", "ERROR: " & errors.Count & " · Advertencias: " & warnings.Count
    ElseIf warnings.Count > 0 Then
        SetNamedValue "llg_quality_status", "ADVERTENCIAS"
        SetNamedValue "llg_ui_review_status", "Sin errores · Advertencias: " & warnings.Count
    Else
        SetNamedValue "llg_quality_status", "CORRECTA"
        SetNamedValue "llg_ui_review_status", "Ficha revisada sin incidencias"
    End If

    msg = JoinIssues("ERRORES", errors, 8) & vbCrLf & JoinIssues("ADVERTENCIAS", warnings, 8) & vbCrLf & JoinIssues("INFORMACIÓN", information, 5)
    If msg = vbCrLf & vbCrLf Then msg = "Ficha revisada sin incidencias."
    mLastReviewMessage = Trim$(msg)
    If showMessage Then
        MsgBox Trim$(msg), IIf(errors.Count > 0, vbExclamation, vbInformation), "Revisar ficha"
    End If
    ReviewFicha = errors.Count
    Exit Function

FatalError:
    fatalNumber = Err.Number
    fatalDescription = Err.Description
    mLastReviewMessage = "ERROR INTERNO en " & mReviewStage & " · " & fatalNumber & ": " & fatalDescription
    On Error Resume Next
    SetNamedValue "llg_quality_status", "ERROR INTERNO"
    SetNamedValue "llg_ui_review_status", "ERROR INTERNO al revisar la ficha"
    If showMessage Then MsgBox "No se pudo completar la revisión. Compruebe que la plantilla no esté dañada.", vbCritical, "Revisar ficha"
    On Error GoTo 0
    ReviewFicha = 1
End Function

Public Sub ReviewFichaAction()
    Call ReviewFicha(True)
End Sub
