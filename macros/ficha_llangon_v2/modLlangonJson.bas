Option Explicit

Private Function JsonQuote(ByVal value As String) As String
    Dim i As Long, ch As String, code As Long, result As String
    For i = 1 To Len(value)
        ch = Mid$(value, i, 1)
        code = AscW(ch)
        Select Case ch
            Case Chr$(34): result = result & "\"""
            Case "\": result = result & "\\"
            Case vbCr: result = result & "\r"
            Case vbLf: result = result & "\n"
            Case vbTab: result = result & "\t"
            Case Else
                If code >= 0 And code < 32 Then
                    result = result & "\u" & Right$("0000" & Hex$(code), 4)
                Else
                    result = result & ch
                End If
        End Select
    Next i
    JsonQuote = Chr$(34) & result & Chr$(34)
End Function

Private Function JsonNameValue(ByVal name As String, ByVal value As String) As String
    JsonNameValue = JsonQuote(name) & ":" & JsonQuote(value)
End Function

Private Function JsonIntegerOrNull(ByVal value As String) As String
    If Trim$(value) <> "" And IsNumeric(value) Then
        JsonIntegerOrNull = CStr(CLng(value))
    Else
        JsonIntegerOrNull = "null"
    End If
End Function

Private Function JsonBoolean(ByVal value As String) As String
    value = LCase$(Trim$(value))
    If value = "false" Or value = "0" Or value = "no" Then
        JsonBoolean = "false"
    Else
        JsonBoolean = "true"
    End If
End Function

Private Function CellText(ByVal cell As Range) As String
    Dim value As Variant
    value = cell.Value
    If IsError(value) Then Exit Function
    CellText = Trim$(CStr(value))
End Function

Private Function JsonNumberOrString(ByVal value As Variant) As String
    Dim text As String
    If IsError(value) Then JsonNumberOrString = JsonQuote(""): Exit Function
    text = Trim$(CStr(value))
    If text = "" Then JsonNumberOrString = JsonQuote(""): Exit Function
    If IsNumeric(value) Then
        JsonNumberOrString = Replace(CStr(CDbl(value)), Application.International(xlDecimalSeparator), ".")
    Else
        JsonNumberOrString = JsonQuote(text)
    End If
End Function

Private Function DateIso(ByVal rangeName As String) As String
    Dim rng As Range
    Set rng = NamedRange(rangeName)
    If rng Is Nothing Then Exit Function
    If IsError(rng.Value) Then Exit Function
    If IsDate(rng.Value) Then DateIso = Format$(CDate(rng.Value), "yyyy-mm-dd") Else DateIso = Trim$(CStr(rng.Value))
End Function

Private Function TimeIso(ByVal rangeName As String) As String
    Dim rng As Range, value As Variant
    Set rng = NamedRange(rangeName)
    If rng Is Nothing Then Exit Function
    value = rng.Value
    If IsError(value) Then Exit Function
    If IsNumeric(value) Then
        If CDbl(value) >= 0# And CDbl(value) < 1# Then
            TimeIso = Format$(CDate(CDbl(value)), "hh:nn")
        Else
            TimeIso = Trim$(CStr(value))
        End If
    ElseIf IsDate(value) Then
        TimeIso = Format$(CDate(value), "hh:nn")
    Else
        TimeIso = Trim$(CStr(value))
    End If
End Function

Private Function LotesJson() As String
    Dim dataRange As Range, row As Range, result As String
    Set dataRange = SectionBodyRange("Lotes (opcional)", "Garantías y participación", 2)
    If dataRange Is Nothing Then LotesJson = "[]": Exit Function
    For Each row In dataRange.Rows
        If CellText(row.Cells(1, 2)) <> "" Or CellText(row.Cells(1, 1)) <> "" Then
            If result <> "" Then result = result & ","
            result = result & "{" & _
                JsonNameValue("numero", CellText(row.Cells(1, 1))) & "," & _
                JsonNameValue("titulo", CellText(row.Cells(1, 2))) & "," & _
                """presupuesto"":" & JsonNumberOrString(row.Cells(1, 5).Value) & "," & _
                """valor_estimado"":" & JsonNumberOrString(row.Cells(1, 6).Value) & "," & _
                JsonNameValue("comentarios", CellText(row.Cells(1, 7))) & "}"
        End If
    Next row
    LotesJson = "[" & result & "]"
End Function

Private Function CriteriaJson(ByVal sectionTitle As String, ByVal nextSectionTitle As String) As String
    Dim dataRange As Range, row As Range, result As String, orderNumber As Long
    Set dataRange = SectionBodyRange(sectionTitle, nextSectionTitle, 2, "Total puntos")
    If dataRange Is Nothing Then CriteriaJson = "[]": Exit Function
    For Each row In dataRange.Rows
        If CellText(row.Cells(1, 1)) <> "" Or CellText(row.Cells(1, 7)) <> "" Then
            If result <> "" Then result = result & ","
            orderNumber = orderNumber + 1
            result = result & "{" & _
                JsonNameValue("orden", CStr(orderNumber)) & "," & _
                JsonNameValue("criterio", CellText(row.Cells(1, 1))) & "," & _
                JsonNameValue("descripcion", CellText(row.Cells(1, 3))) & "," & _
                """puntos"":" & JsonNumberOrString(row.Cells(1, 7).Value) & "}"
        End If
    Next row
    CriteriaJson = "[" & result & "]"
End Function

Private Function ConditionsJson() As String
    Dim dataRange As Range, row As Range, result As String, orderNumber As Long
    Set dataRange = SectionBodyRange("Condiciones especiales de ejecución", "Observaciones", 1)
    If dataRange Is Nothing Then ConditionsJson = "[]": Exit Function
    For Each row In dataRange.Rows
        If CellText(row.Cells(1, 1)) <> "" Then
            If result <> "" Then result = result & ","
            orderNumber = orderNumber + 1
            result = result & "{" & _
                JsonNameValue("orden", CStr(orderNumber)) & "," & _
                JsonNameValue("condicion", CellText(row.Cells(1, 1))) & "}"
        End If
    Next row
    ConditionsJson = "[" & result & "]"
End Function

Private Function ObservationsJson() As String
    Dim dataRange As Range, row As Range, result As String, text As String
    Set dataRange = SectionBodyRange("Observaciones", "", 1)
    If dataRange Is Nothing Then ObservationsJson = "[]": Exit Function
    For Each row In dataRange.Rows
        text = CellText(row.Cells(1, 1))
        If text <> "" Then
            If result <> "" Then result = result & ","
            result = result & JsonQuote(text)
        End If
    Next row
    ObservationsJson = "[" & result & "]"
End Function

Private Function CalendarYearsJson() As String
    Dim table As ListObject, cell As Range, values As Object, key As Variant, result As String
    Set values = CreateObject("Scripting.Dictionary")
    Set table = ThisWorkbook.Worksheets("_Listas").ListObjects("tblFestivos")
    If Not table.DataBodyRange Is Nothing Then
        For Each cell In table.ListColumns("Fecha").DataBodyRange.Cells
            If IsDate(cell.Value) Then values(CStr(Year(CDate(cell.Value)))) = True
        Next cell
    End If
    For Each key In values.Keys
        If result <> "" Then result = result & ","
        result = result & CStr(key)
    Next key
    CalendarYearsJson = "[" & result & "]"
End Function

Public Function BuildFichaPayloadJson(ByVal draft As Boolean) As String
    Dim result As String
    EnsureDocumentMetadata
    SyncSelectedClientMetadata
    result = "{""control"":{" & JsonNameValue("document_id", NamedText("llg_control_document_id")) & ","
    result = result & JsonNameValue("template_id", "ficha_llangon") & ","
    result = result & JsonNameValue("template_version", LLANGON_TEMPLATE_VERSION) & ","
    result = result & JsonNameValue("payload_schema_version", LLANGON_PAYLOAD_VERSION) & ","
    result = result & JsonNameValue("created_at", NamedText("llg_control_created_at")) & ","
    result = result & JsonNameValue("source", NamedText("llg_control_source")) & ","
    result = result & JsonNameValue("last_import_at", NamedText("llg_control_last_import_at")) & ","
    result = result & JsonNameValue("last_clients_sync_at", NamedText("llg_control_clients_updated_at")) & ","
    result = result & JsonNameValue("confidentiality_notice", NamedText("llg_document_confidentiality_notice")) & "},"

    result = result & """recipient"":{""client_id"":" & JsonIntegerOrNull(NamedText("llg_recipient_client_id")) & ","
    result = result & JsonNameValue("client_display", NamedText("llg_recipient_client_display")) & ","
    result = result & JsonNameValue("razon_social_snapshot", NamedText("llg_recipient_razon_social")) & ","
    result = result & """client_active"":" & JsonBoolean(NamedText("llg_recipient_client_active")) & "},"

    result = result & """tender"":{""licitacion_id"":" & JsonIntegerOrNull(NamedText("llg_control_licitacion_id")) & ","
    result = result & JsonNameValue("expediente", NamedText("llg_tender_expediente")) & ","
    result = result & JsonNameValue("objeto", NamedText("llg_tender_objeto")) & ","
    result = result & JsonNameValue("fecha_limite", DateIso("llg_tender_fecha_limite")) & ","
    result = result & JsonNameValue("hora_limite", TimeIso("llg_tender_hora_limite")) & ","
    result = result & JsonNameValue("enlace", NamedText("llg_tender_enlace")) & ","
    result = result & JsonNameValue("organismo", NamedText("llg_tender_organismo")) & ","
    result = result & JsonNameValue("plataforma", NamedText("llg_tender_plataforma")) & ","
    result = result & JsonNameValue("tipo_contrato", NamedText("llg_tender_tipo_contrato")) & ","
    result = result & JsonNameValue("procedimiento", NamedText("llg_tender_procedimiento")) & ","
    result = result & JsonNameValue("regulacion_armonizada", NamedText("llg_tender_regulacion_armonizada")) & ","
    result = result & """presupuesto_base"":" & JsonNumberOrString(NamedRange("llg_tender_presupuesto_base").Value) & ","
    result = result & """valor_estimado"":" & JsonNumberOrString(NamedRange("llg_tender_valor_estimado").Value) & ","
    result = result & """lotes"":" & LotesJson() & "},"

    result = result & """analysis"":{" & JsonNameValue("plazo", NamedText("llg_analysis_plazo")) & ","
    result = result & JsonNameValue("plazo_comentario", NamedText("llg_analysis_plazo_comentario")) & ","
    result = result & JsonNameValue("prorroga", NamedText("llg_analysis_prorroga")) & ","
    result = result & JsonNameValue("prorroga_comentario", NamedText("llg_analysis_prorroga_comentario")) & ","
    result = result & JsonNameValue("forma_adjudicacion", NamedText("llg_analysis_forma_adjudicacion")) & ","
    result = result & JsonNameValue("garantia_provisional", NamedText("llg_analysis_garantia_provisional")) & ","
    result = result & JsonNameValue("garantia_provisional_comentario", NamedText("llg_analysis_garantia_provisional_comentario")) & ","
    result = result & JsonNameValue("garantia_definitiva", NamedText("llg_analysis_garantia_definitiva")) & ","
    result = result & JsonNameValue("garantia_definitiva_comentario", NamedText("llg_analysis_garantia_definitiva_comentario")) & ","
    result = result & JsonNameValue("garantia_complementaria", NamedText("llg_analysis_garantia_complementaria")) & ","
    result = result & JsonNameValue("garantia_complementaria_comentario", NamedText("llg_analysis_garantia_complementaria_comentario")) & ","
    result = result & JsonNameValue("adscripcion_medios", NamedText("llg_analysis_adscripcion_medios")) & ","
    result = result & JsonNameValue("adscripcion_medios_comentario", NamedText("llg_analysis_adscripcion_medios_comentario")) & ","
    result = result & JsonNameValue("numero_sobres", NamedText("llg_analysis_numero_sobres")) & ","
    result = result & JsonNameValue("fichas_tecnicas", NamedText("llg_analysis_fichas_tecnicas")) & ","
    result = result & JsonNameValue("fichas_tecnicas_comentario", NamedText("llg_analysis_fichas_tecnicas_comentario")) & ","
    result = result & JsonNameValue("memoria_tecnica", NamedText("llg_analysis_memoria_tecnica")) & ","
    result = result & JsonNameValue("memoria_tecnica_comentario", NamedText("llg_analysis_memoria_tecnica_comentario")) & ","
    result = result & JsonNameValue("subcontratacion", NamedText("llg_analysis_subcontratacion")) & ","
    result = result & JsonNameValue("subcontratacion_comentario", NamedText("llg_analysis_subcontratacion_comentario")) & ","
    result = result & JsonNameValue("muestras", NamedText("llg_analysis_muestras")) & ","
    result = result & JsonNameValue("muestras_momento", NamedText("llg_analysis_muestras_momento")) & ","
    result = result & JsonNameValue("muestras_comentario", NamedText("llg_analysis_muestras_comentario")) & ","
    result = result & """observaciones"":" & ObservationsJson() & ","
    result = result & """criterios_juicio"":" & CriteriaJson("Criterios sujetos a juicio de valor", "Criterios evaluables mediante fórmula") & ","
    result = result & """criterios_formula"":" & CriteriaJson("Criterios evaluables mediante fórmula", "Condiciones especiales de ejecución") & ","
    result = result & """condiciones_especiales"":" & ConditionsJson() & "},"
    result = result & """quality"":{""draft"":" & IIf(draft, "true", "false") & ",""calendar_years"":" & CalendarYearsJson() & "}}"
    BuildFichaPayloadJson = result
End Function
