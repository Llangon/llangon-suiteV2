Option Explicit

Private Const MAX_XML_BYTES As Long = 2097152
Private mPlaceImportLastError As String

Public Sub ImportPlace()
    Dim source As String, answer As VbMsgBoxResult, selectedFile As Variant
    source = NamedText("llg_source_place")
    If source = "" Then
        answer = MsgBox( _
            "Para importar una URL de PLACE, péguela completa en la celda «Origen PLACE» y vuelva a pulsar este botón." & vbCrLf & vbCrLf & _
            "¿Desea seleccionar ahora un fichero XML de su disco?", _
            vbYesNoCancel + vbInformation, "Importar PLACE")
        If answer = vbYes Then
            selectedFile = Application.GetOpenFilename("Documentos XML (*.xml),*.xml", , "Seleccione el XML de PLACE")
            If VarType(selectedFile) = vbBoolean Then Exit Sub
            source = CStr(selectedFile)
        ElseIf answer = vbNo Then
            Application.Goto NamedRange("llg_source_place"), True
            Exit Sub
        Else
            Exit Sub
        End If
    End If
    source = NormalizePlaceSource(source)
    Call ImportPlaceSource(source, True)
End Sub

Public Function NormalizePlaceSource(ByVal source As String) As String
    source = Trim$(source)
    Do While InStr(1, source, "&amp;", vbTextCompare) > 0
        source = Replace(source, "&amp;", "&", 1, -1, vbTextCompare)
    Loop
    NormalizePlaceSource = source
End Function

Public Function SelfTestPlaceLongUrl() As String
    Dim source As String, normalized As String
    source = "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?cifrado=" & String$(95, "A") & "&amp;DocumentIdParam=" & String$(120, "B")
    normalized = NormalizePlaceSource(source)
    If Len(normalized) <= 254 Then Err.Raise vbObjectError + 2321, "Ficha Llangon", "La prueba no cubre enlaces PLACE largos."
    If InStr(1, normalized, "&amp;", vbTextCompare) > 0 Then Err.Raise vbObjectError + 2322, "Ficha Llangon", "No se normalizó el separador HTML del enlace PLACE."
    If InStr(1, normalized, "&DocumentIdParam=", vbBinaryCompare) = 0 Then Err.Raise vbObjectError + 2323, "Ficha Llangon", "El enlace PLACE perdió parámetros."
    SelfTestPlaceLongUrl = "OK: URL PLACE larga sin truncado y separadores normalizados"
End Function

Public Function ImportPlaceSource(ByVal source As String, Optional ByVal showMessages As Boolean = True) As Long
    Dim values As Object, warnings As Collection, errorText As String
    Dim conflicts As Long, answer As VbMsgBoxResult, message As String
    mPlaceImportLastError = ""
    source = NormalizePlaceSource(source)
    On Error GoTo Handler
    Set warnings = New Collection
    Set values = GetDataFromPlace(source, warnings, errorText)
    If values Is Nothing Then
        If showMessages Then
            MsgBox errorText, vbCritical, "Importar PLACE"
        Else
            mPlaceImportLastError = errorText
        End If
        Exit Function
    End If
    conflicts = CountPlaceConflicts(values)
    If conflicts > 0 Then
        If showMessages Then
            answer = MsgBox("PLACE aporta " & conflicts & " valor(es) distintos de los ya escritos." & vbCrLf & vbCrLf & "¿Desea sustituir únicamente esos campos? Los campos ausentes en el origen no se borrarán.", vbYesNo + vbQuestion, "Importar PLACE")
            If answer <> vbYes Then Exit Function
        Else
            mPlaceImportLastError = "La prueba PLACE encontró conflictos inesperados."
            Exit Function
        End If
    End If
    ApplyDataToFicha values
    SetNamedValue "llg_control_source", "place"
    SetNamedValue "llg_control_last_import_at", Format$(Now, "yyyy-mm-dd hh:nn:ss")
    SetNamedValue "llg_source_place", source
    message = "Datos de PLACE aplicados correctamente. No se ha vaciado ningún campo por ausencia en el origen."
    If warnings.Count > 0 Then message = message & vbCrLf & vbCrLf & "Avisos: " & warnings.Count
    ImportPlaceSource = values.Count
    If showMessages Then MsgBox message, vbInformation, "Importar PLACE"
    Exit Function

Handler:
    mPlaceImportLastError = Err.Description
    If showMessages Then MsgBox "No se pudo importar PLACE." & vbCrLf & vbCrLf & mPlaceImportLastError, vbCritical, "Importar PLACE"
End Function

Public Function PlaceImportLastError() As String
    PlaceImportLastError = mPlaceImportLastError
End Function

Public Function GetDataFromPlace(ByVal source As String, ByVal warnings As Collection, ByRef errorText As String) As Object
    Dim xml As Object, data As Object, node As Object, planned As Object, extensionNode As Object
    Dim durationValue As String, durationUnit As String, extensionText As String
    Dim startText As String, endText As String, plannedDescription As String, maximumExtensions As String
    If IsRemoteSource(source) Then
        Set data = GetDataFromPlaceBridge(source, warnings, errorText)
        If Not data Is Nothing Then Set GetDataFromPlace = data
        Exit Function
    End If
    If Not LoadPlaceXml(source, xml, errorText) Then Exit Function
    Set data = CreateObject("Scripting.Dictionary")
    data.CompareMode = vbTextCompare

    PutValue data, "tender.fecha_limite", ParseIsoDate(FirstNodeText(xml, _
        "//*[local-name()='TenderSubmissionDeadlinePeriod']/*[local-name()='EndDate']", _
        "//*[local-name()='ParticipationRequestReceptionPeriod']/*[local-name()='EndDate']"))
    PutValue data, "tender.hora_limite", ParseIsoTime(FirstNodeText(xml, _
        "//*[local-name()='TenderSubmissionDeadlinePeriod']/*[local-name()='EndTime']", _
        "//*[local-name()='ParticipationRequestReceptionPeriod']/*[local-name()='EndTime']"))
    PutValue data, "tender.objeto", FirstNodeText(xml, "//*[local-name()='ProcurementProject']/*[local-name()='Name']")
    PutValue data, "tender.expediente", FirstNodeText(xml, "//*[local-name()='ContractFolderID']")
    PutValue data, "tender.organismo", FirstNodeText(xml, _
        "//*[local-name()='LocatedContractingParty']//*[local-name()='PartyName']/*[local-name()='Name']", _
        "//*[local-name()='ContractingParty']//*[local-name()='PartyName']/*[local-name()='Name']")
    PutValue data, "tender.enlace", FirstNodeText(xml, _
        AdditionalDocumentXPath("/*[local-name()='Attachment']/*[local-name()='ExternalReference']/*[local-name()='URI']"), _
        AdditionalDocumentXPath("/*[local-name()='Attachment']/*[local-name()='URI']"))

    Set node = FirstNode(xml, _
        "//*[local-name()='ProcurementProject']/*[local-name()='TypeCode'][contains(@listURI, 'ContractCode')]", _
        "//*[local-name()='ProcurementProject']/*[local-name()='TypeCode']")
    PutValue data, "tender.tipo_contrato", NodeAttributeOrText(node, "name")

    Set node = FirstNode(xml, "//*[local-name()='TenderingProcess']/*[local-name()='ProcedureCode']")
    PutValue data, "tender.procedimiento", NodeAttributeOrText(node, "name")
    PutValue data, "tender.regulacion_armonizada", BooleanTextToState(FirstNodeText(xml, "//*[local-name()='TenderingProcess']/*[local-name()='OverThresholdIndicator']"))
    PutValue data, "tender.plataforma", "PLACE"
    PutValue data, "tender.presupuesto_base", ParseAmount(FirstNodeText(xml, _
        "//*[local-name()='ProcurementProject']/*[local-name()='BudgetAmount']/*[local-name()='TaxExclusiveAmount' and @currencyID='EUR']", _
        "//*[local-name()='ProcurementProject']/*[local-name()='BudgetAmount']/*[local-name()='TaxExclusiveAmount']"))
    PutValue data, "tender.valor_estimado", ParseAmount(FirstNodeText(xml, _
        "//*[local-name()='ProcurementProject']/*[local-name()='BudgetAmount']/*[local-name()='EstimatedOverallContractAmount' and @currencyID='EUR']", _
        "//*[local-name()='ProcurementProject']/*[local-name()='BudgetAmount']/*[local-name()='EstimatedOverallContractAmount']"))

    Set planned = FirstNode(xml, "//*[local-name()='ProcurementProject']/*[local-name()='PlannedPeriod']")
    If Not planned Is Nothing Then
        durationValue = NodeText(planned, "*[local-name()='DurationMeasure']")
        durationUnit = NodeAttribute(FirstNode(planned, "*[local-name()='DurationMeasure']"), "unitCode")
        startText = NodeText(planned, "*[local-name()='StartDate']")
        endText = NodeText(planned, "*[local-name()='EndDate']")
        plannedDescription = NodeText(planned, "*[local-name()='Description']")
        PutValue data, "analysis.plazo", FormatDuration(durationValue, durationUnit, startText, endText)
        PutValue data, "analysis.plazo_comentario", PlannedPeriodComment(startText, endText, plannedDescription)
    End If

    Set extensionNode = FirstNode(xml, "//*[local-name()='TenderingTerms']/*[local-name()='ContractExtension']", "//*[local-name()='ContractExtension']")
    If Not extensionNode Is Nothing Then
        extensionText = FirstNonBlank( _
            NodeText(extensionNode, "*[local-name()='OptionValidityPeriod']/*[local-name()='Description']"), _
            NodeText(extensionNode, "*[local-name()='OptionsDescription']"), _
            NodeText(extensionNode, "*[local-name()='Description']"))
        maximumExtensions = NodeText(extensionNode, "*[local-name()='MaximumNumberNumeric']")
        If HasContractExtension(extensionNode) Then
            PutValue data, "analysis.prorroga", "Sí"
            PutValue data, "analysis.prorroga_comentario", FirstNonBlank(extensionText, MaximumExtensionText(maximumExtensions))
        Else
            PutValue data, "analysis.prorroga", "No"
        End If
    End If
    If data.Count < 3 Then warnings.Add "El XML contiene pocos datos reconocibles."
    Set GetDataFromPlace = data
End Function

Private Function GetDataFromPlaceBridge(ByVal source As String, ByVal warnings As Collection, ByRef errorText As String) As Object
    Dim body As String, data As Object
    If Not FetchPlaceViaBridge(source, body, errorText) Then Exit Function
    Set data = ParsePlaceBridgeBody(body, warnings, errorText)
    If data Is Nothing Then Exit Function
    If data.Count < 3 Then warnings.Add "PLACE ha devuelto pocos datos reconocibles."
    Set GetDataFromPlaceBridge = data
End Function

Private Function PlaceBridgeValue(ByVal logicalId As String, ByVal rawValue As String) As Variant
    Select Case LCase$(Trim$(logicalId))
        Case "tender.fecha_limite": PlaceBridgeValue = ParseIsoDate(rawValue)
        Case "tender.hora_limite": PlaceBridgeValue = ParseIsoTime(rawValue)
        Case "tender.presupuesto_base", "tender.valor_estimado": PlaceBridgeValue = ParseAmount(rawValue)
        Case Else: PlaceBridgeValue = rawValue
    End Select
End Function

Public Function SelfTestPlaceParser() As String
    Dim path As String, xmlText As String, values As Object, warnings As New Collection
    Dim errorText As String, savedNumber As Long, savedDescription As String, savedSource As String
    path = Environ$("TEMP") & "\llangon_place_selftest_" & Format$(Now, "yyyymmdd_hhnnss") & ".xml"
    On Error GoTo Failed
    xmlText = "<?xml version=""1.0"" encoding=""UTF-8""?>" & _
        "<ext:ContractFolderStatus xmlns:ext=""urn:place"" xmlns:cac=""urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"" xmlns:cbc=""urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"">" & _
        "<cbc:ContractFolderID>XML-AUTO-33/2030</cbc:ContractFolderID>" & _
        "<cac:ProcurementProject><cbc:Name>Servicio ficticio de aceptación</cbc:Name><cbc:TypeCode name=""Servicios"">2</cbc:TypeCode>" & _
        "<cac:PlannedPeriod><cbc:StartDate>2026-12-05+01:00</cbc:StartDate><cbc:EndDate>2026-12-30+01:00</cbc:EndDate></cac:PlannedPeriod>" & _
        "<cac:ContractExtension><cbc:MaximumNumberNumeric>2</cbc:MaximumNumberNumeric></cac:ContractExtension></cac:ProcurementProject>" & _
        "<cac:TenderingProcess><cbc:ProcedureCode name=""Abierto"">1</cbc:ProcedureCode><cac:TenderSubmissionDeadlinePeriod>" & _
        "<cbc:EndDate>2030-10-15</cbc:EndDate><cbc:EndTime>14:00:00</cbc:EndTime></cac:TenderSubmissionDeadlinePeriod></cac:TenderingProcess>" & _
        "</ext:ContractFolderStatus>"
    SaveUtf8Text path, xmlText
    Set values = GetDataFromPlace(path, warnings, errorText)
    If values Is Nothing Then Err.Raise vbObjectError + 2310, "Ficha Llangon", errorText
    If CStr(values("tender.expediente")) <> "XML-AUTO-33/2030" Then Err.Raise vbObjectError + 2311, "Ficha Llangon", "PLACE no devolvió el expediente esperado."
    If CStr(values("tender.objeto")) <> "Servicio ficticio de aceptación" Then Err.Raise vbObjectError + 2312, "Ficha Llangon", "PLACE no devolvió el objeto esperado."
    If CStr(values("analysis.plazo")) <> "25 días" Then Err.Raise vbObjectError + 2313, "Ficha Llangon", "PLACE no interpretó el plazo entre fechas."
    If CStr(values("analysis.plazo_comentario")) <> "Del 05/12/2026 al 30/12/2026" Then Err.Raise vbObjectError + 2315, "Ficha Llangon", "PLACE no conservó las fechas del plazo."
    If CStr(values("analysis.prorroga")) <> "Sí" Then Err.Raise vbObjectError + 2316, "Ficha Llangon", "PLACE no detectó la prórroga."
    If CStr(values("analysis.prorroga_comentario")) <> "Máximo de 2 prórrogas." Then Err.Raise vbObjectError + 2317, "Ficha Llangon", "PLACE no detalló el máximo de prórrogas."
    If Not IsDate(values("tender.fecha_limite")) Then Err.Raise vbObjectError + 2314, "Ficha Llangon", "PLACE no devolvió una fecha válida."
    SelfTestPlaceParser = "OK: XML PLACE local, plazo entre fechas y prórrogas"
    GoTo Cleanup

Failed:
    savedNumber = Err.Number
    savedDescription = Err.Description
    savedSource = Err.Source
Cleanup:
    On Error Resume Next
    If Dir$(path) <> "" Then Kill path
    On Error GoTo 0
    If savedNumber <> 0 Then Err.Raise savedNumber, savedSource, savedDescription
End Function

Public Function SelfTestPlaceBridgeTsv() As String
    Dim body As String, values As Object, warnings As New Collection, errorText As String
    body = "#schema_version" & vbTab & "1" & vbLf & _
        "#source_url" & vbTab & "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=ficticio" & vbLf & _
        "#warning" & vbTab & "Aviso ficticio" & vbLf & _
        "logical_id" & vbTab & "value" & vbLf & _
        "tender.expediente" & vbTab & "PLACE-BRIDGE-44/2030" & vbLf & _
        "tender.objeto" & vbTab & "Servicio ficticio por bridge" & vbLf & _
        "tender.fecha_limite" & vbTab & "2030-11-20" & vbLf & _
        "tender.presupuesto_base" & vbTab & "12345.67" & vbLf & _
        "analysis.plazo" & vbTab & "25 días" & vbLf & _
        "analysis.plazo_comentario" & vbTab & "Del 05/12/2026 al 30/12/2026" & vbLf & _
        "analysis.prorroga" & vbTab & "Sí" & vbLf & _
        "analysis.prorroga_comentario" & vbTab & "Máximo de 2 prórrogas." & vbLf & _
        "tender.plataforma" & vbTab & "PLACE" & vbLf
    Set values = ParsePlaceBridgeBody(body, warnings, errorText)
    If values Is Nothing Then Err.Raise vbObjectError + 2320, "Ficha Llangon", errorText
    If CStr(values("tender.expediente")) <> "PLACE-BRIDGE-44/2030" Then Err.Raise vbObjectError + 2321, "Ficha Llangon", "El bridge PLACE no conservó el expediente."
    If Not IsDate(values("tender.fecha_limite")) Then Err.Raise vbObjectError + 2322, "Ficha Llangon", "El bridge PLACE no convirtió la fecha."
    If warnings.Count <> 1 Then Err.Raise vbObjectError + 2323, "Ficha Llangon", "El bridge PLACE no conservó los avisos."
    If CStr(values("analysis.plazo")) <> "25 días" Or CStr(values("analysis.prorroga_comentario")) <> "Máximo de 2 prórrogas." Then Err.Raise vbObjectError + 2324, "Ficha Llangon", "El bridge PLACE no conservó plazo y prórrogas."
    SelfTestPlaceBridgeTsv = "OK: contrato TSV PLACE, plazo, prórrogas y avisos"
End Function

Private Function ParsePlaceBridgeBody(ByVal body As String, ByVal warnings As Collection, ByRef errorText As String) As Object
    Dim lines As Variant, fields As Variant, i As Long, logicalId As String, data As Object
    Set data = CreateObject("Scripting.Dictionary")
    data.CompareMode = vbTextCompare
    lines = Split(Replace(body, vbCrLf, vbLf), vbLf)
    For i = LBound(lines) To UBound(lines)
        If Trim$(CStr(lines(i))) <> "" Then
            fields = ParseTsvLine(CStr(lines(i)))
            If UBound(fields) >= 1 Then
                logicalId = Trim$(CStr(fields(0)))
                If LCase$(logicalId) = "#warning" Then
                    warnings.Add CStr(fields(1))
                ElseIf Left$(logicalId, 1) <> "#" And LCase$(logicalId) <> "logical_id" Then
                    PutValue data, logicalId, PlaceBridgeValue(logicalId, CStr(fields(1)))
                End If
            End If
        End If
    Next i
    Set ParsePlaceBridgeBody = data
End Function

Private Function LoadPlaceXml(ByVal source As String, ByRef xml As Object, ByRef errorText As String) As Boolean
    On Error GoTo Handler
    Set xml = CreateObject("MSXML2.DOMDocument.6.0")
    xml.async = False
    xml.validateOnParse = False
    xml.resolveExternals = False
    xml.SetProperty "SelectionLanguage", "XPath"
    If Dir$(source) = "" Then errorText = "No se encuentra el archivo XML indicado.": Exit Function
    If FileLen(source) > MAX_XML_BYTES Then errorText = "El XML supera el límite de 2 MB.": Exit Function
    If Not xml.Load(source) Then errorText = XmlError(xml): Exit Function
    LoadPlaceXml = True
    Exit Function
Handler:
    errorText = "No se pudo cargar el XML de PLACE: " & Err.Description
End Function

Private Function IsRemoteSource(ByVal source As String) As Boolean
    source = LCase$(Trim$(source))
    IsRemoteSource = (Left$(source, 7) = "http://" Or Left$(source, 8) = "https://")
End Function

Private Function XmlError(ByVal xml As Object) As String
    XmlError = "El contenido no es un XML válido."
    If Not xml Is Nothing Then
        If xml.ParseError.ErrorCode <> 0 Then XmlError = XmlError & " Línea " & xml.ParseError.Line & ": " & xml.ParseError.Reason
    End If
End Function

Private Sub PutValue(ByVal target As Object, ByVal logicalId As String, ByVal value As Variant)
    If IsError(value) Then Exit Sub
    If Trim$(CStr(value)) <> "" Then target(logicalId) = value
End Sub

Private Function LogicalToName(ByVal logicalId As String) As String
    Select Case logicalId
        Case "tender.fecha_limite": LogicalToName = "llg_tender_fecha_limite"
        Case "tender.hora_limite": LogicalToName = "llg_tender_hora_limite"
        Case "tender.objeto": LogicalToName = "llg_tender_objeto"
        Case "tender.expediente": LogicalToName = "llg_tender_expediente"
        Case "tender.organismo": LogicalToName = "llg_tender_organismo"
        Case "tender.enlace": LogicalToName = "llg_tender_enlace"
        Case "tender.tipo_contrato": LogicalToName = "llg_tender_tipo_contrato"
        Case "tender.procedimiento": LogicalToName = "llg_tender_procedimiento"
        Case "tender.regulacion_armonizada": LogicalToName = "llg_tender_regulacion_armonizada"
        Case "tender.plataforma": LogicalToName = "llg_tender_plataforma"
        Case "tender.presupuesto_base": LogicalToName = "llg_tender_presupuesto_base"
        Case "tender.valor_estimado": LogicalToName = "llg_tender_valor_estimado"
        Case "analysis.plazo": LogicalToName = "llg_analysis_plazo"
        Case "analysis.plazo_comentario": LogicalToName = "llg_analysis_plazo_comentario"
        Case "analysis.prorroga": LogicalToName = "llg_analysis_prorroga"
        Case "analysis.prorroga_comentario": LogicalToName = "llg_analysis_prorroga_comentario"
    End Select
End Function

Private Function CountPlaceConflicts(ByVal values As Object) As Long
    Dim key As Variant, rangeName As String, current As String, incoming As String
    For Each key In values.Keys
        rangeName = LogicalToName(CStr(key))
        If rangeName <> "" Then
            current = Trim$(CStr(NamedRange(rangeName).Value))
            incoming = Trim$(CStr(values(key)))
            If current <> "" And incoming <> "" And StrComp(current, incoming, vbTextCompare) <> 0 Then CountPlaceConflicts = CountPlaceConflicts + 1
        End If
    Next key
End Function

Public Sub ApplyDataToFicha(ByVal values As Object)
    Dim key As Variant, rangeName As String, rng As Range
    For Each key In values.Keys
        rangeName = LogicalToName(CStr(key))
        If rangeName <> "" And Trim$(CStr(values(key))) <> "" Then
            Set rng = NamedRange(rangeName)
            If Not rng Is Nothing Then
                If rangeName = "llg_tender_enlace" Then
                    On Error Resume Next
                    rng.Hyperlinks.Delete
                    On Error GoTo 0
                    rng.Value = CStr(values(key))
                    rng.Hyperlinks.Add Anchor:=rng, Address:=CStr(values(key)), TextToDisplay:=CStr(values(key))
                Else
                    rng.Value = values(key)
                End If
            End If
        End If
    Next key
End Sub

Private Function FirstNode(ByVal root As Object, ParamArray xpaths() As Variant) As Object
    Dim i As Long, node As Object
    On Error Resume Next
    For i = LBound(xpaths) To UBound(xpaths)
        Set node = root.SelectSingleNode(CStr(xpaths(i)))
        If Not node Is Nothing Then Set FirstNode = node: Exit Function
    Next i
    On Error GoTo 0
End Function

Private Function FirstNodeText(ByVal root As Object, ParamArray xpaths() As Variant) As String
    Dim node As Object, i As Long
    On Error Resume Next
    For i = LBound(xpaths) To UBound(xpaths)
        Set node = root.SelectSingleNode(CStr(xpaths(i)))
        If Not node Is Nothing Then FirstNodeText = Trim$(node.Text): Exit Function
    Next i
    On Error GoTo 0
End Function

Private Function NodeText(ByVal root As Object, ByVal xpath As String) As String
    Dim node As Object
    If root Is Nothing Then Exit Function
    On Error Resume Next
    Set node = root.SelectSingleNode(xpath)
    If Not node Is Nothing Then NodeText = Trim$(node.Text)
End Function

Private Function NodeAttribute(ByVal node As Object, ByVal name As String) As String
    Dim attr As Object
    If node Is Nothing Then Exit Function
    On Error Resume Next
    Set attr = node.Attributes.getNamedItem(name)
    If Not attr Is Nothing Then NodeAttribute = Trim$(attr.Text)
End Function

Private Function NodeAttributeOrText(ByVal node As Object, ByVal name As String) As String
    NodeAttributeOrText = NodeAttribute(node, name)
    If NodeAttributeOrText = "" And Not node Is Nothing Then NodeAttributeOrText = Trim$(node.Text)
End Function

Private Function AdditionalDocumentXPath(ByVal childXPath As String) As String
    AdditionalDocumentXPath = "//*[local-name()='AdditionalDocumentReference'][translate(normalize-space(*[local-name()='ID']), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='DETALLE_LICITACION']" & childXPath
End Function

Private Function ParseIsoDate(ByVal value As String) As Variant
    value = Trim$(value)
    If Len(value) >= 10 And Mid$(value, 5, 1) = "-" And Mid$(value, 8, 1) = "-" Then
        ParseIsoDate = DateSerial(CInt(Left$(value, 4)), CInt(Mid$(value, 6, 2)), CInt(Mid$(value, 9, 2)))
    ElseIf IsDate(value) Then
        ParseIsoDate = CDate(value)
    Else
        ParseIsoDate = value
    End If
End Function

Private Function ParseIsoTime(ByVal value As String) As String
    value = Trim$(value)
    If InStr(1, value, "T", vbTextCompare) > 0 Then value = Mid$(value, InStr(1, value, "T", vbTextCompare) + 1)
    If Len(value) >= 5 And InStr(value, ":") > 0 Then ParseIsoTime = Left$(value, 5) Else ParseIsoTime = value
End Function

Private Function ParseAmount(ByVal value As String) As Variant
    Dim normalized As String, decimalSeparator As String, lastComma As Long, lastDot As Long
    normalized = Replace(Replace(Replace(Trim$(value), ChrW$(160), ""), " ", ""), ChrW$(8364), "")
    normalized = Replace(normalized, "EUR", "", 1, -1, vbTextCompare)
    If normalized = "" Then Exit Function
    decimalSeparator = Application.International(xlDecimalSeparator)
    lastComma = InStrRev(normalized, ","): lastDot = InStrRev(normalized, ".")
    If lastComma > 0 And lastDot > 0 Then
        If lastComma > lastDot Then normalized = Replace(Replace(normalized, ".", ""), ",", decimalSeparator) Else normalized = Replace(Replace(normalized, ",", ""), ".", decimalSeparator)
    ElseIf lastComma > 0 Then
        normalized = Replace(normalized, ",", decimalSeparator)
    ElseIf lastDot > 0 Then
        normalized = Replace(normalized, ".", decimalSeparator)
    End If
    If IsNumeric(normalized) Then ParseAmount = CDbl(normalized) Else ParseAmount = value
End Function

Private Function BooleanTextToState(ByVal value As String) As String
    Select Case LCase$(Trim$(value))
        Case "true", "1", "si", "sí", "yes": BooleanTextToState = "Sí"
        Case "false", "0", "no": BooleanTextToState = "No"
    End Select
End Function

Private Function FormatDuration(ByVal value As String, ByVal unitCode As String, ByVal startText As String, ByVal endText As String) As String
    Dim startDate As Variant, endDate As Variant, days As Long
    If Trim$(value) <> "" Then
        FormatDuration = Trim$(value) & " " & UnitLabel(unitCode, Val(value))
    ElseIf Trim$(startText) <> "" And Trim$(endText) <> "" Then
        startDate = ParseIsoDate(startText)
        endDate = ParseIsoDate(endText)
        If IsDate(startDate) And IsDate(endDate) Then
            days = DateDiff("d", CDate(startDate), CDate(endDate))
            If days >= 0 Then FormatDuration = CStr(days) & " " & IIf(days = 1, "día", "días")
        End If
    End If
End Function

Private Function PlannedPeriodComment(ByVal startText As String, ByVal endText As String, ByVal description As String) As String
    Dim dateRange As String
    If Trim$(startText) <> "" And Trim$(endText) <> "" Then
        dateRange = "Del " & DateForText(startText) & " al " & DateForText(endText)
    ElseIf Trim$(startText) <> "" Then
        dateRange = "Desde el " & DateForText(startText)
    ElseIf Trim$(endText) <> "" Then
        dateRange = "Hasta el " & DateForText(endText)
    End If
    If dateRange <> "" And Trim$(description) <> "" Then
        PlannedPeriodComment = dateRange & ". " & Trim$(description)
    Else
        PlannedPeriodComment = FirstNonBlank(dateRange, description)
    End If
End Function

Private Function UnitLabel(ByVal unitCode As String, ByVal amount As Double) As String
    Select Case UCase$(Trim$(unitCode))
        Case "ANN", "YEAR", "YER": UnitLabel = IIf(amount = 1, "año", "años")
        Case "MON": UnitLabel = IIf(amount = 1, "mes", "meses")
        Case "WEE": UnitLabel = IIf(amount = 1, "semana", "semanas")
        Case "DAY": UnitLabel = IIf(amount = 1, "día", "días")
        Case "HUR": UnitLabel = IIf(amount = 1, "hora", "horas")
    End Select
End Function

Private Function DateForText(ByVal value As String) As String
    Dim parsed As Variant
    parsed = ParseIsoDate(value)
    If IsDate(parsed) Then DateForText = Format$(CDate(parsed), "dd/mm/yyyy") Else DateForText = CStr(parsed)
End Function

Private Function HasContractExtension(ByVal node As Object) As Boolean
    Dim maximum As String
    If node Is Nothing Then Exit Function
    maximum = NodeText(node, "*[local-name()='MaximumNumberNumeric']")
    If maximum <> "" Then
        HasContractExtension = Val(Replace(maximum, ",", ".")) > 0
    Else
        HasContractExtension = FirstNonBlank(NodeText(node, "*[local-name()='OptionValidityPeriod']/*[local-name()='Description']"), NodeText(node, "*[local-name()='OptionsDescription']"), NodeText(node, "*[local-name()='Description']")) <> ""
    End If
End Function

Private Function MaximumExtensionText(ByVal value As String) As String
    Dim amount As Double, shown As String, label As String
    If Trim$(value) = "" Then Exit Function
    amount = Val(Replace(value, ",", "."))
    If amount <= 0 Then Exit Function
    If amount = Fix(amount) Then shown = CStr(CLng(amount)) Else shown = Replace(CStr(amount), ".", ",")
    label = IIf(amount = 1, "prórroga", "prórrogas")
    MaximumExtensionText = "Máximo de " & shown & " " & label & "."
End Function

Private Function FirstNonBlank(ParamArray values() As Variant) As String
    Dim i As Long
    For i = LBound(values) To UBound(values)
        If Trim$(CStr(values(i))) <> "" Then FirstNonBlank = Trim$(CStr(values(i))): Exit Function
    Next i
End Function
