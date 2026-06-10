Option Explicit

Sub CrearEmailOutlook_Llangon()
    Dim oldScreenUpdating As Boolean
    Dim oldEnableEvents As Boolean
    Dim oldStatusBar As Variant
    
    oldScreenUpdating = Application.ScreenUpdating
    oldEnableEvents = Application.EnableEvents
    oldStatusBar = Application.StatusBar
    
    On Error GoTo ManejarError
    
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Hoja1")
    
    Dim filas As Variant
    filas = ObtenerFilasSeleccionadas(ws)
    
    If IsEmpty(filas) Then
        MsgBox "Selecciona una o varias filas de expedientes antes de crear el correo.", vbExclamation
        GoTo Finalizar
    End If
    
    Dim totalExpedientes As Long
    totalExpedientes = UBound(filas) - LBound(filas) + 1
    
    Dim confirmacion As String
    Dim textoConfirmacion As String
    
    textoConfirmacion = "Vas a crear un correo con " & totalExpedientes & " expediente(s)."
    textoConfirmacion = textoConfirmacion & vbCrLf & vbCrLf & "Escribe CORREO para confirmar:"
    
    confirmacion = InputBox(textoConfirmacion, Txt("Confirmar creaci{o}n de correo"))
    
    If StrComp(Trim$(confirmacion), "CORREO", vbTextCompare) <> 0 Then
        MsgBox Txt("Creaci{o}n del correo cancelada."), vbInformation
        GoTo Finalizar
    End If
    
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.StatusBar = "Preparando correo de Infonalia..."
    
    OrdenarFilasPorFecha ws, filas
    
    Dim olApp As Object
    Dim olMail As Object
    Set olApp = ObtenerOutlook()
    
    If olApp Is Nothing Then
        Err.Raise vbObjectError + 1001, , "No se pudo abrir Outlook."
    End If
    
    Set olMail = olApp.CreateItem(0)
    
    Dim destinatarioEmail As String
    Dim remitenteEmail As String
    destinatarioEmail = Trim$(InputBox("Indica el correo destinatario:", "Crear correo"))
    If destinatarioEmail = "" Then
        MsgBox "No se ha indicado ningún destinatario.", vbExclamation
        GoTo Finalizar
    End If
    remitenteEmail = ObtenerEmailRemitente(olApp)
    
    If remitenteEmail = "" Then remitenteEmail = destinatarioEmail
    
    Dim logoHtml As String
    logoHtml = AdjuntarLogo(olMail)
    
    Dim fechasInfonalia As Object
    Set fechasInfonalia = CreateObject("Scripting.Dictionary")
    
    Dim i As Long
    For i = LBound(filas) To UBound(filas)
        AgregarFechaInfonalia fechasInfonalia, ValorCampo(ws, "Fecha_Infonalia", CLng(filas(i)))
    Next i
    
    Dim strAsuntoFechas As String
    Dim strDiasAsuntoCuerpo As String
    ConstruirTextosFechas fechasInfonalia, strAsuntoFechas, strDiasAsuntoCuerpo
    
    Dim strSaludo As String
    strSaludo = ObtenerSaludo()
    
    Dim textoHTML As String
    textoHTML = ""
    textoHTML = textoHTML & "<html><head><meta http-equiv='Content-Type' content='text/html; charset=utf-8'></head>"
    textoHTML = textoHTML & "<body style='margin:0;padding:0;background-color:#f4f6f8;font-family:Segoe UI,Arial,sans-serif;color:#1f2933;'>"
    textoHTML = textoHTML & ConstruirCabecera(logoHtml)
    textoHTML = textoHTML & ConstruirIntroduccion(strSaludo, strDiasAsuntoCuerpo, totalExpedientes)
    
    For i = LBound(filas) To UBound(filas)
        Application.StatusBar = "Creando tarjeta " & (i - LBound(filas) + 1) & " de " & totalExpedientes & "..."
        textoHTML = textoHTML & ConstruirTarjetaExpediente(ws, CLng(filas(i)), remitenteEmail)
    Next i
    
    textoHTML = textoHTML & "<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#f4f6f8;padding:8px 0 28px 0;'><tr><td align='center'>"
    textoHTML = textoHTML & "<table width='720' cellpadding='0' cellspacing='0' style='width:720px;max-width:720px;'><tr><td style='font-size:12px;color:#6b7280;text-align:center;'>"
    textoHTML = textoHTML & "Correo generado desde Infonalia.</td></tr></table></td></tr></table>"
    textoHTML = textoHTML & "</body></html>"
    
    With olMail
        .To = destinatarioEmail
        .Subject = strAsuntoFechas
        .BodyFormat = 2
        .HTMLBody = textoHTML
        .Display
    End With
    
Finalizar:
    Set olMail = Nothing
    Set olApp = Nothing
    
    Application.ScreenUpdating = oldScreenUpdating
    Application.EnableEvents = oldEnableEvents
    
    If VarType(oldStatusBar) = vbBoolean Then
        If oldStatusBar = False Then
            Application.StatusBar = False
        Else
            Application.StatusBar = oldStatusBar
        End If
    Else
        Application.StatusBar = oldStatusBar
    End If
    
    Exit Sub
    
ManejarError:
    MsgBox "No se pudo crear el correo." & vbCrLf & vbCrLf & Err.Description, vbCritical
    Resume Finalizar
End Sub

Private Function ObtenerFilasSeleccionadas(ByVal ws As Worksheet) As Variant
    If TypeName(Selection) <> "Range" Then Exit Function
    
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    
    Dim area As Range
    Dim filaSeleccionada As Range
    Dim fila As Long
    
    For Each area In Selection.Areas
        For Each filaSeleccionada In area.Rows
            fila = filaSeleccionada.Row
            
            If EsFilaDatos(ws, fila) Then
                If Not dict.Exists(CStr(fila)) Then dict.Add CStr(fila), fila
            End If
        Next filaSeleccionada
    Next area
    
    If dict.Count = 0 Then Exit Function
    
    Dim filas() As Long
    ReDim filas(1 To dict.Count)
    
    Dim clave As Variant
    Dim i As Long
    i = 1
    
    For Each clave In dict.Keys
        filas(i) = CLng(dict(clave))
        i = i + 1
    Next clave
    
    ObtenerFilasSeleccionadas = filas
End Function

Private Function EsFilaDatos(ByVal ws As Worksheet, ByVal fila As Long) As Boolean
    On Error GoTo fallo
    
    Dim filaEncabezado As Long
    filaEncabezado = ws.Range("Expediente").Row
    
    If fila <= filaEncabezado Then
        EsFilaDatos = False
        Exit Function
    End If
    
    Dim expediente As String
    Dim objeto As String
    
    expediente = Trim$(CStr(ValorCampo(ws, "Expediente", fila)))
    objeto = Trim$(CStr(ValorCampo(ws, "Objeto_del_contrato", fila)))
    
    EsFilaDatos = (expediente <> "" Or objeto <> "")
    Exit Function
    
fallo:
    EsFilaDatos = False
End Function

Private Function ValorCampo(ByVal ws As Worksheet, ByVal nombreCampo As String, ByVal fila As Long) As Variant
    On Error GoTo fallo
    
    ValorCampo = ws.Cells(fila, ws.Range(nombreCampo).Column).Value
    Exit Function
    
fallo:
    ValorCampo = ""
End Function

Private Function ValorCampoConFallback(ByVal ws As Worksheet, ByVal nombreCampo As String, ByVal fila As Long, ByVal columnaFallback As Long) As Variant
    Dim valor As Variant
    
    valor = ValorCampo(ws, nombreCampo, fila)
    
    If Trim$(CStr(valor)) <> "" Then
        ValorCampoConFallback = valor
        Exit Function
    End If
    
    On Error GoTo fallo
    ValorCampoConFallback = ws.Cells(fila, columnaFallback).Value
    Exit Function
    
fallo:
    ValorCampoConFallback = valor
End Function

Private Sub OrdenarFilasPorFecha(ByVal ws As Worksheet, ByRef filas As Variant)
    Dim i As Long
    Dim j As Long
    Dim tmp As Long
    
    For i = LBound(filas) To UBound(filas) - 1
        For j = i + 1 To UBound(filas)
            If ClaveOrdenFila(ws, CLng(filas(j))) < ClaveOrdenFila(ws, CLng(filas(i))) Then
                tmp = CLng(filas(i))
                filas(i) = CLng(filas(j))
                filas(j) = tmp
            End If
        Next j
    Next i
End Sub

Private Function ClaveOrdenFila(ByVal ws As Worksheet, ByVal fila As Long) As Double
    Dim valorFecha As Variant
    Dim valorHora As Variant
    Dim clave As Double
    
    valorFecha = ValorCampoConFallback(ws, "Fecha_de_presentacion", fila, 9)
    valorHora = ValorCampoConFallback(ws, "Hora_limite", fila, 10)
    
    If IsDate(valorFecha) Then
        clave = CDbl(DateValue(CDate(valorFecha)))
    Else
        clave = 2958465#
    End If
    
    If IsDate(valorHora) Then
        clave = clave + CDbl(TimeValue(CDate(valorHora)))
    End If
    
    ClaveOrdenFila = clave + (fila / 100000000#)
End Function

Private Function ObtenerOutlook() As Object
    On Error Resume Next
    Set ObtenerOutlook = GetObject(, "Outlook.Application")
    
    If ObtenerOutlook Is Nothing Then
        Set ObtenerOutlook = CreateObject("Outlook.Application")
    End If
    
    On Error GoTo 0
End Function

Private Function ObtenerEmailRemitente(ByVal olApp As Object) As String
    On Error Resume Next
    
    If olApp.Session.Accounts.Count > 0 Then
        ObtenerEmailRemitente = olApp.Session.Accounts.Item(1).SmtpAddress
    End If
    
    If ObtenerEmailRemitente = "" Then
        ObtenerEmailRemitente = olApp.Session.CurrentUser.Address
    End If
    
    On Error GoTo 0
End Function

Private Function AdjuntarLogo(ByVal olMail As Object) As String
    Dim logoPath As String
    logoPath = ThisWorkbook.Path & "\Logo.png"
    
    If Dir(logoPath) = "" Then
        AdjuntarLogo = ""
        Exit Function
    End If
    
    On Error Resume Next
    
    Dim oAttachment As Object
    Set oAttachment = olMail.Attachments.Add(logoPath)
    oAttachment.PropertyAccessor.SetProperty "http://schemas.microsoft.com/mapi/proptag/0x3712001F", "LogoLlangon"
    
    If Err.Number = 0 Then
        AdjuntarLogo = "<img src='cid:LogoLlangon' style='height:58px;display:block;' alt='Logo'>"
    Else
        AdjuntarLogo = ""
        Err.Clear
    End If
    
    On Error GoTo 0
End Function

Private Function ObtenerSaludo() As String
    Dim horaActual As Integer
    horaActual = Hour(Time)
    
    If horaActual >= 6 And horaActual < 12 Then
        ObtenerSaludo = Txt("Buenos d{i}as,")
    ElseIf horaActual >= 12 And horaActual < 20 Then
        ObtenerSaludo = "Buenas tardes,"
    Else
        ObtenerSaludo = "Buenas noches,"
    End If
End Function

Private Sub AgregarFechaInfonalia(ByVal fechas As Object, ByVal valor As Variant)
    Dim fecha As Date
    fecha = ExtraerFechaInfonalia(valor)
    
    If fecha = 0 Then Exit Sub
    
    Dim clave As String
    clave = CStr(CLng(DateValue(fecha)))
    
    If Not fechas.Exists(clave) Then fechas.Add clave, DateValue(fecha)
End Sub

Private Function ExtraerFechaInfonalia(ByVal valor As Variant) As Date
    If IsDate(valor) Then
        ExtraerFechaInfonalia = DateValue(CDate(valor))
        Exit Function
    End If
    
    Dim texto As String
    texto = Trim$(CStr(valor))
    If texto = "" Then Exit Function
    
    Dim partes As Variant
    Dim i As Long
    partes = Split(texto, " - ")
    
    For i = UBound(partes) To LBound(partes) Step -1
        If IsDate(Trim$(CStr(partes(i)))) Then
            ExtraerFechaInfonalia = DateValue(CDate(Trim$(CStr(partes(i)))))
            Exit Function
        End If
    Next i
End Function

Private Sub ConstruirTextosFechas(ByVal fechas As Object, ByRef asunto As String, ByRef cuerpo As String)
    If fechas.Count = 0 Then
        asunto = "Infonalia"
        cuerpo = "sin fecha especificada"
        Exit Sub
    End If
    
    Dim arr() As Long
    ReDim arr(1 To fechas.Count)
    
    Dim clave As Variant
    Dim i As Long
    i = 1
    
    For Each clave In fechas.Keys
        arr(i) = CLng(clave)
        i = i + 1
    Next clave
    
    OrdenarNumeros arr
    
    Dim mismaMensualidad As Boolean
    mismaMensualidad = True
    
    For i = 2 To UBound(arr)
        If Month(CDate(arr(i))) <> Month(CDate(arr(1))) Or Year(CDate(arr(i))) <> Year(CDate(arr(1))) Then
            mismaMensualidad = False
            Exit For
        End If
    Next i
    
    Dim textos() As String
    ReDim textos(1 To UBound(arr))
    
    If mismaMensualidad Then
        For i = 1 To UBound(arr)
            textos(i) = CStr(Day(CDate(arr(i))))
        Next i
        
        If UBound(arr) = 1 Then
            asunto = Txt("Infonalia del d{i}a ") & textos(1) & " de " & Format$(CDate(arr(1)), "mmmm") & " de " & Year(CDate(arr(1)))
            cuerpo = Txt("del d{i}a ") & textos(1) & " de " & Format$(CDate(arr(1)), "mmmm") & " de " & Year(CDate(arr(1)))
        Else
            asunto = Txt("Infonalia de los d{i}as ") & UnirLista(textos, UBound(textos)) & " de " & Format$(CDate(arr(1)), "mmmm") & " de " & Year(CDate(arr(1)))
            cuerpo = Txt("de los d{i}as ") & UnirLista(textos, UBound(textos)) & " de " & Format$(CDate(arr(1)), "mmmm") & " de " & Year(CDate(arr(1)))
        End If
    Else
        For i = 1 To UBound(arr)
            textos(i) = Format$(CDate(arr(i)), "dd/mm/yyyy")
        Next i
        
        If UBound(arr) = 1 Then
            asunto = Txt("Infonalia del d{i}a ") & textos(1)
            cuerpo = Txt("del d{i}a ") & textos(1)
        Else
            asunto = Txt("Infonalia de los d{i}as ") & UnirLista(textos, UBound(textos))
            cuerpo = Txt("de los d{i}as ") & UnirLista(textos, UBound(textos))
        End If
    End If
End Sub

Private Sub OrdenarNumeros(ByRef arr() As Long)
    Dim i As Long
    Dim j As Long
    Dim tmp As Long
    
    For i = LBound(arr) To UBound(arr) - 1
        For j = i + 1 To UBound(arr)
            If arr(j) < arr(i) Then
                tmp = arr(i)
                arr(i) = arr(j)
                arr(j) = tmp
            End If
        Next j
    Next i
End Sub

Private Function UnirLista(ByRef valores() As String, ByVal total As Long) As String
    Dim i As Long
    Dim resultado As String
    
    For i = 1 To total
        If i = 1 Then
            resultado = valores(i)
        ElseIf i = total Then
            resultado = resultado & " y " & valores(i)
        Else
            resultado = resultado & ", " & valores(i)
        End If
    Next i
    
    UnirLista = resultado
End Function

Private Sub AgregarHtml(ByRef html As String, ByVal fragmento As String)
    html = html & fragmento
End Sub

Private Function Txt(ByVal texto As String) As String
    texto = Replace(texto, "{a}", ChrW$(&HE1))
    texto = Replace(texto, "{e}", ChrW$(&HE9))
    texto = Replace(texto, "{i}", ChrW$(&HED))
    texto = Replace(texto, "{o}", ChrW$(&HF3))
    texto = Replace(texto, "{u}", ChrW$(&HFA))
    texto = Replace(texto, "{n}", ChrW$(&HF1))
    texto = Replace(texto, "{A}", ChrW$(&HC1))
    texto = Replace(texto, "{E}", ChrW$(&HC9))
    texto = Replace(texto, "{I}", ChrW$(&HCD))
    texto = Replace(texto, "{O}", ChrW$(&HD3))
    texto = Replace(texto, "{U}", ChrW$(&HDA))
    texto = Replace(texto, "{N}", ChrW$(&HD1))
    
    Txt = texto
End Function

Private Function ConstruirCabecera(ByVal logoHtml As String) As String
    Dim html As String
    
    AgregarHtml html, "<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#f4f6f8;padding:24px 0 0 0;'>"
    AgregarHtml html, "<tr><td align='center'>"
    AgregarHtml html, "<table width='720' cellpadding='0' cellspacing='0' style='width:720px;max-width:720px;background-color:#ffffff;border:1px solid #d9e1e8;'>"
    AgregarHtml html, "<tr>"
    AgregarHtml html, "<td style='padding:22px 26px;font-family:Segoe UI,Arial,sans-serif;'>"
    AgregarHtml html, "<div style='font-size:20px;font-weight:700;color:#1f2933;'>" & HtmlEncode(Txt("Asesores Llang{o}n S.L.")) & "</div>"
    AgregarHtml html, "<div style='font-size:13px;color:#6b7280;margin-top:4px;'>Resumen de licitaciones Infonalia</div>"
    AgregarHtml html, "</td>"
    AgregarHtml html, "<td align='right' style='padding:18px 26px 18px 10px;width:120px;'>"
    AgregarHtml html, logoHtml
    AgregarHtml html, "</td>"
    AgregarHtml html, "</tr></table></td></tr></table>"
    
    ConstruirCabecera = html
End Function

Private Function ConstruirIntroduccion(ByVal saludo As String, ByVal textoFechas As String, ByVal totalExpedientes As Long) As String
    Dim html As String
    
    AgregarHtml html, "<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#f4f6f8;padding:0;'>"
    AgregarHtml html, "<tr><td align='center'>"
    AgregarHtml html, "<table width='720' cellpadding='0' cellspacing='0' style='width:720px;max-width:720px;background-color:#ffffff;border-left:1px solid #d9e1e8;border-right:1px solid #d9e1e8;border-bottom:1px solid #d9e1e8;'>"
    AgregarHtml html, "<tr><td style='padding:22px 26px 12px 26px;font-family:Segoe UI,Arial,sans-serif;font-size:14px;line-height:1.55;color:#273444;'>"
    AgregarHtml html, "<p style='margin:0 0 12px 0;'>" & HtmlEncode(saludo) & "</p>"
    AgregarHtml html, "<p style='margin:0 0 12px 0;'>Te adjunto las licitaciones de Infonalia correspondientes a " & HtmlEncode(textoFechas) & ".</p>"
    AgregarHtml html, "<p style='margin:0 0 14px 0;'>" & HtmlEncode(Txt("He incluido ")) & totalExpedientes & HtmlEncode(Txt(" expediente(s), ordenados por fecha l{i}mite de presentaci{o}n.")) & "</p>"
    AgregarHtml html, "<table cellpadding='0' cellspacing='0' style='margin:0 0 4px 0;'><tr>"
    AgregarHtml html, "<td style='padding:6px 10px;background-color:#e8f2ff;border:1px solid #b7d8ff;color:#005a9e;font-size:12px;font-weight:700;'>Hacer concurso</td>"
    AgregarHtml html, "<td style='width:8px;'></td>"
    AgregarHtml html, "<td style='padding:6px 10px;background-color:#eaf7ed;border:1px solid #b9dfc2;color:#207245;font-size:12px;font-weight:700;'>Solo descargar</td>"
    AgregarHtml html, "</tr></table>"
    AgregarHtml html, "</td></tr></table></td></tr></table>"
    
    ConstruirIntroduccion = html
End Function

Private Function ConstruirTarjetaExpediente(ByVal ws As Worksheet, ByVal fila As Long, ByVal remitenteEmail As String) As String
    Dim expediente As String
    Dim objetoContrato As String
    Dim organismo As String
    Dim provinciaEjecucion As String
    Dim presupuesto As String
    Dim fechaPresentacion As String
    Dim horaLimite As String
    Dim enlacePerfilContratante As String
    Dim enlaceInfonalia As String
    Dim tipoContrato As String
    Dim fechaInfonalia As String
    Dim valorFechaLimite As Variant
    
    expediente = Trim$(CStr(ValorCampo(ws, "Expediente", fila)))
    objetoContrato = Trim$(CStr(ValorCampo(ws, "Objeto_del_contrato", fila)))
    organismo = Trim$(CStr(ValorCampo(ws, "Organismo", fila)))
    provinciaEjecucion = Trim$(CStr(ValorCampo(ws, "Provincia_de_ejecucion", fila)))
    presupuesto = TextoPresupuesto(ValorCampo(ws, "Presupuesto", fila))
    valorFechaLimite = ValorCampoConFallback(ws, "Fecha_de_presentacion", fila, 9)
    fechaPresentacion = TextoFecha(valorFechaLimite)
    horaLimite = TextoHora(ValorCampoConFallback(ws, "Hora_limite", fila, 10))
    enlacePerfilContratante = Trim$(CStr(ValorCampo(ws, "Enlace_Perfil_del_contratante", fila)))
    enlaceInfonalia = Trim$(CStr(ValorCampo(ws, "EnlaceInfonalia", fila)))
    tipoContrato = Trim$(CStr(ValorCampo(ws, "Tipo_de_Contrato", fila)))
    fechaInfonalia = TextoFecha(ValorCampo(ws, "Fecha_Infonalia", fila))
    
    If tipoContrato = "" Then tipoContrato = "No indicado"
    If presupuesto = "" Then presupuesto = "No indicado"
    If fechaPresentacion = "" Then fechaPresentacion = "Sin fecha"
    If horaLimite = "" Then horaLimite = "Sin hora"
    If fechaInfonalia = "" Then fechaInfonalia = "Sin fecha"
    
    Dim urgencia As String
    urgencia = EstadoUrgencia(valorFechaLimite)
    
    Dim urgBg As String, urgFg As String, urgBorder As String
    Dim tipoBg As String, tipoFg As String, tipoBorder As String
    
    ColoresUrgencia valorFechaLimite, urgBg, urgFg, urgBorder
    ColoresTipo tipoContrato, tipoBg, tipoFg, tipoBorder
    
    Dim cuerpoMensaje As String
    cuerpoMensaje = "Expediente: " & expediente & vbCrLf
    cuerpoMensaje = cuerpoMensaje & "Tipo: " & tipoContrato & vbCrLf
    cuerpoMensaje = cuerpoMensaje & Txt("Fecha l{i}mite: ") & fechaPresentacion & " " & horaLimite & vbCrLf
    cuerpoMensaje = cuerpoMensaje & "Organismo: " & organismo & vbCrLf
    cuerpoMensaje = cuerpoMensaje & "Infonalia: " & fechaInfonalia & vbCrLf
    cuerpoMensaje = cuerpoMensaje & "Objeto: " & RecortarTexto(objetoContrato, 360) & vbCrLf
    cuerpoMensaje = cuerpoMensaje & "Perfil: " & enlacePerfilContratante
    
    Dim mailtoHacer As String
    Dim mailtoDescargar As String
    Dim sufijoInfonalia As String
    
    sufijoInfonalia = " (Infonalia " & fechaInfonalia & ")"
    mailtoHacer = CrearMailTo(remitenteEmail, "Hacer concurso - Exp. " & expediente & sufijoInfonalia, cuerpoMensaje)
    mailtoDescargar = CrearMailTo(remitenteEmail, "Solo descargar - Exp. " & expediente & sufijoInfonalia, cuerpoMensaje)
    
    Dim html As String
    
    AgregarHtml html, "<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#f4f6f8;padding:14px 0 0 0;'><tr><td align='center'>"
    AgregarHtml html, "<table width='720' cellpadding='0' cellspacing='0' style='width:720px;max-width:720px;background-color:#ffffff;border:1px solid #d9e1e8;border-left:6px solid " & urgBorder & ";'>"
    AgregarHtml html, "<tr><td style='padding:18px 22px 12px 22px;font-family:Segoe UI,Arial,sans-serif;'>"
    AgregarHtml html, "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
    AgregarHtml html, "<td style='vertical-align:top;'>"
    AgregarHtml html, "<div style='font-size:11px;line-height:1.2;color:#6b7280;text-transform:uppercase;font-weight:700;'>Expediente</div>"
    AgregarHtml html, "<div style='font-size:18px;line-height:1.3;color:#111827;font-weight:700;margin-top:3px;'>" & HtmlEncode(expediente) & "</div>"
    AgregarHtml html, "</td>"
    AgregarHtml html, "<td align='right' style='vertical-align:top;width:230px;'>"
    AgregarHtml html, BadgeHtml(urgencia, urgBg, urgFg, urgBorder)
    AgregarHtml html, "<br><span style='display:block;height:5px;line-height:5px;'>&nbsp;</span>"
    AgregarHtml html, BadgeHtml(tipoContrato, tipoBg, tipoFg, tipoBorder)
    AgregarHtml html, "</td></tr></table>"
    AgregarHtml html, "<div style='font-size:14px;line-height:1.45;color:#1f2933;font-weight:600;margin-top:14px;'>" & HtmlEncode(objetoContrato) & "</div>"
    AgregarHtml html, "<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:14px;border-top:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;'>"
    AgregarHtml html, FilaInfoHtml("Organismo", organismo, "Provincia", provinciaEjecucion)
    AgregarHtml html, FilaInfoHtml("Presupuesto", presupuesto, Txt("Fecha l{i}mite"), fechaPresentacion & " - " & horaLimite)
    AgregarHtml html, "</table>"
    AgregarHtml html, ConstruirBloqueEnlaces(enlacePerfilContratante, enlaceInfonalia)
    AgregarHtml html, "<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:16px;'><tr>"
    AgregarHtml html, "<td align='left'>" & BotonHtml(mailtoHacer, "Hacer concurso", "#005a9e") & "</td>"
    AgregarHtml html, "<td align='right'>" & BotonHtml(mailtoDescargar, "Solo descargar", "#207245") & "</td>"
    AgregarHtml html, "</tr></table>"
    AgregarHtml html, "</td></tr></table></td></tr></table>"
    
    ConstruirTarjetaExpediente = html
End Function

Private Function FilaInfoHtml(ByVal etiqueta1 As String, ByVal valor1 As String, ByVal etiqueta2 As String, ByVal valor2 As String) As String
    Dim html As String
    
    AgregarHtml html, "<tr>"
    AgregarHtml html, "<td style='width:50%;padding:10px 12px 10px 0;border-top:1px solid #eef1f4;vertical-align:top;'>"
    AgregarHtml html, "<div style='font-size:11px;color:#6b7280;text-transform:uppercase;font-weight:700;'>" & HtmlEncode(etiqueta1) & "</div>"
    AgregarHtml html, "<div style='font-size:13px;color:#1f2933;margin-top:3px;'>" & HtmlEncode(valor1) & "</div>"
    AgregarHtml html, "</td>"
    AgregarHtml html, "<td style='width:50%;padding:10px 0 10px 12px;border-top:1px solid #eef1f4;vertical-align:top;'>"
    AgregarHtml html, "<div style='font-size:11px;color:#6b7280;text-transform:uppercase;font-weight:700;'>" & HtmlEncode(etiqueta2) & "</div>"
    AgregarHtml html, "<div style='font-size:13px;color:#1f2933;margin-top:3px;'>" & HtmlEncode(valor2) & "</div>"
    AgregarHtml html, "</td>"
    AgregarHtml html, "</tr>"
    
    FilaInfoHtml = html
End Function

Private Function ConstruirBloqueEnlaces(ByVal enlacePerfil As String, ByVal enlaceInfonalia As String) As String
    Dim html As String
    html = "<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:14px;'><tr>"
    
    html = html & "<td style='width:50%;padding-right:6px;'>" & LinkHtml(enlacePerfil, "Perfil del contratante") & "</td>"
    html = html & "<td style='width:50%;padding-left:6px;'>" & LinkHtml(enlaceInfonalia, "Anuncio Infonalia") & "</td>"
    
    html = html & "</tr></table>"
    ConstruirBloqueEnlaces = html
End Function

Private Function LinkHtml(ByVal url As String, ByVal texto As String) As String
    If Trim$(url) = "" Then
        LinkHtml = "<span style='font-size:12px;color:#9ca3af;'>Sin enlace</span>"
    Else
        LinkHtml = "<a href='" & HtmlAttr(url) & "' style='display:block;padding:8px 10px;background-color:#f8fafc;border:1px solid #d9e1e8;color:#005a9e;text-decoration:none;font-size:12px;font-weight:700;text-align:center;'>" & HtmlEncode(texto) & "</a>"
    End If
End Function

Private Function BotonHtml(ByVal url As String, ByVal texto As String, ByVal color As String) As String
    BotonHtml = "<a href='" & HtmlAttr(url) & "' style='display:inline-block;background-color:" & color & ";color:#ffffff;text-decoration:none;padding:10px 16px;font-weight:700;font-size:13px;'>" & HtmlEncode(texto) & "</a>"
End Function

Private Function BadgeHtml(ByVal texto As String, ByVal bg As String, ByVal fg As String, ByVal border As String) As String
    BadgeHtml = "<span style='display:inline-block;background-color:" & bg & ";border:1px solid " & border & ";color:" & fg & ";padding:4px 8px;font-size:11px;font-weight:700;'>" & HtmlEncode(texto) & "</span>"
End Function

Private Function EstadoUrgencia(ByVal valorFecha As Variant) As String
    If Not IsDate(valorFecha) Then
        EstadoUrgencia = "Sin fecha"
        Exit Function
    End If
    
    Dim dias As Long
    dias = DateDiff("d", Date, DateValue(CDate(valorFecha)))
    
    If dias < 0 Then
        EstadoUrgencia = "Vencida"
    ElseIf dias = 0 Then
        EstadoUrgencia = "Vence hoy"
    ElseIf dias = 1 Then
        EstadoUrgencia = Txt("Vence en 1 d{i}a")
    Else
        EstadoUrgencia = Txt("Vence en ") & CStr(dias) & Txt(" d{i}as")
    End If
End Function

Private Sub ColoresUrgencia(ByVal valorFecha As Variant, ByRef bg As String, ByRef fg As String, ByRef border As String)
    If Not IsDate(valorFecha) Then
        bg = "#f3f4f6": fg = "#4b5563": border = "#9ca3af"
        Exit Sub
    End If
    
    Dim dias As Long
    dias = DateDiff("d", Date, DateValue(CDate(valorFecha)))
    
    If dias < 0 Then
        bg = "#fef2f2": fg = "#991b1b": border = "#dc2626"
    ElseIf dias <= 3 Then
        bg = "#fff4e5": fg = "#9a4d00": border = "#f59e0b"
    ElseIf dias <= 7 Then
        bg = "#fffbe6": fg = "#7a5d00": border = "#d6b300"
    Else
        bg = "#e8f2ff": fg = "#005a9e": border = "#4f9be8"
    End If
End Sub

Private Sub ColoresTipo(ByVal tipoContrato As String, ByRef bg As String, ByRef fg As String, ByRef border As String)
    Dim t As String
    t = LCase$(tipoContrato)
    
    If InStr(1, t, "sumin", vbTextCompare) > 0 Then
        bg = "#eaf7ed": fg = "#207245": border = "#7fc58b"
    ElseIf InStr(1, t, "serv", vbTextCompare) > 0 Then
        bg = "#e8f2ff": fg = "#005a9e": border = "#8bbff2"
    ElseIf InStr(1, t, "obra", vbTextCompare) > 0 Then
        bg = "#fff4e5": fg = "#9a4d00": border = "#f2b866"
    ElseIf InStr(1, t, "conces", vbTextCompare) > 0 Then
        bg = "#f1ecff": fg = "#5b3ba8": border = "#b9a7f0"
    Else
        bg = "#f3f4f6": fg = "#4b5563": border = "#d1d5db"
    End If
End Sub

Private Function TextoFecha(ByVal valor As Variant) As String
    Dim fecha As Date
    
    If IsDate(valor) Then
        TextoFecha = Format$(CDate(valor), "dd/mm/yyyy")
    Else
        fecha = ExtraerFechaInfonalia(valor)
        If fecha <> 0 Then
            TextoFecha = Format$(fecha, "dd/mm/yyyy")
        Else
            TextoFecha = ""
        End If
    End If
End Function

Private Function TextoHora(ByVal valor As Variant) As String
    Dim texto As String
    
    texto = Trim$(CStr(valor))
    
    If texto = "" Then
        TextoHora = ""
    ElseIf IsNumeric(valor) And CDbl(valor) >= 0 And CDbl(valor) < 1 Then
        TextoHora = Format$(CDbl(valor), "hh:mm")
    ElseIf IsDate(valor) Then
        TextoHora = Format$(CDate(valor), "hh:mm")
    Else
        TextoHora = ExtraerHoraDesdeTexto(texto)
    End If
End Function

Private Function TextoPresupuesto(ByVal valor As Variant) As String
    If IsNumeric(valor) And Trim$(CStr(valor)) <> "" Then
        TextoPresupuesto = Format$(CDbl(valor), "#,##0.00") & " &euro;"
    Else
        TextoPresupuesto = ""
    End If
End Function

Private Function ExtraerHoraDesdeTexto(ByVal texto As String) As String
    On Error GoTo fallo
    
    Dim RE As Object
    Set RE = CreateObject("VBScript.RegExp")
    
    RE.Pattern = "([01]?\d|2[0-3])[:\.]([0-5]\d)"
    RE.Global = False
    RE.IgnoreCase = True
    
    If RE.Test(texto) Then
        Dim matches As Object
        Set matches = RE.Execute(texto)
        
        ExtraerHoraDesdeTexto = Right$("0" & matches(0).SubMatches(0), 2) & ":" & matches(0).SubMatches(1)
        Exit Function
    End If
    
fallo:
    ExtraerHoraDesdeTexto = ""
End Function

Private Function CrearMailTo(ByVal destinatario As String, ByVal asunto As String, ByVal cuerpo As String) As String
    cuerpo = RecortarTexto(cuerpo, 1400)
    CrearMailTo = "mailto:" & destinatario & "?subject=" & UrlEncode(asunto) & "&body=" & UrlEncode(cuerpo)
End Function

Private Function RecortarTexto(ByVal texto As String, ByVal maxLen As Long) As String
    texto = Trim$(texto)
    
    If Len(texto) > maxLen Then
        RecortarTexto = Left$(texto, maxLen - 3) & "..."
    Else
        RecortarTexto = texto
    End If
End Function

Private Function HtmlEncode(ByVal valor As Variant) As String
    Dim texto As String
    
    On Error GoTo fallo
    
    If IsError(valor) Then
        texto = ""
    ElseIf IsNull(valor) Then
        texto = ""
    Else
        texto = CStr(valor)
    End If
    
    texto = Replace(texto, "&", "&amp;")
    texto = Replace(texto, "<", "&lt;")
    texto = Replace(texto, ">", "&gt;")
    texto = Replace(texto, """", "&quot;")
    texto = Replace(texto, "'", "&#39;")
    texto = Replace(texto, vbCrLf, "<br>")
    texto = Replace(texto, vbCr, "<br>")
    texto = Replace(texto, vbLf, "<br>")
    texto = Replace(texto, "&amp;euro;", "&euro;")
    texto = Replace(texto, ChrW$(&HE1), "&aacute;")
    texto = Replace(texto, ChrW$(&HE9), "&eacute;")
    texto = Replace(texto, ChrW$(&HED), "&iacute;")
    texto = Replace(texto, ChrW$(&HF3), "&oacute;")
    texto = Replace(texto, ChrW$(&HFA), "&uacute;")
    texto = Replace(texto, ChrW$(&HF1), "&ntilde;")
    texto = Replace(texto, ChrW$(&HC1), "&Aacute;")
    texto = Replace(texto, ChrW$(&HC9), "&Eacute;")
    texto = Replace(texto, ChrW$(&HCD), "&Iacute;")
    texto = Replace(texto, ChrW$(&HD3), "&Oacute;")
    texto = Replace(texto, ChrW$(&HDA), "&Uacute;")
    texto = Replace(texto, ChrW$(&HD1), "&Ntilde;")
    
    HtmlEncode = texto
    Exit Function
    
fallo:
    HtmlEncode = ""
End Function

Private Function HtmlAttr(ByVal valor As String) As String
    HtmlAttr = HtmlEncode(valor)
End Function

Private Function UrlEncode(ByVal cuerpo As String) As String
    On Error GoTo fallback
    
    UrlEncode = Application.WorksheetFunction.EncodeURL(cuerpo)
    Exit Function
    
fallback:
    UrlEncode = UrlEncodeUtf8(cuerpo)
End Function

Private Function UrlEncodeUtf8(ByVal texto As String) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.WriteText texto
    stream.Position = 0
    stream.Type = 1
    
    Dim bytes() As Byte
    bytes = stream.Read
    stream.Close
    
    Dim i As Long
    Dim inicio As Long
    Dim b As Integer
    Dim resultado As String
    Dim esSeguro As Boolean
    
    inicio = LBound(bytes)
    If UBound(bytes) >= inicio + 2 Then
        If bytes(inicio) = &HEF And bytes(inicio + 1) = &HBB And bytes(inicio + 2) = &HBF Then
            inicio = inicio + 3
        End If
    End If
    
    For i = inicio To UBound(bytes)
        b = bytes(i)
        
        esSeguro = False
        
        If b >= 48 And b <= 57 Then esSeguro = True
        If b >= 65 And b <= 90 Then esSeguro = True
        If b >= 97 And b <= 122 Then esSeguro = True
        If b = 45 Or b = 46 Or b = 95 Or b = 126 Then esSeguro = True
        
        If esSeguro Then
            resultado = resultado & Chr$(b)
        ElseIf b = 32 Then
            resultado = resultado & "%20"
        Else
            resultado = resultado & "%" & Right$("0" & Hex$(b), 2)
        End If
    Next i
    
    UrlEncodeUtf8 = resultado
End Function
