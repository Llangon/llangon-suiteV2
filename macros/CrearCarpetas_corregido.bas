Option Explicit

#If VBA7 Then
    Private Declare PtrSafe Function URLDownloadToFile Lib "urlmon" Alias "URLDownloadToFileA" ( _
        ByVal pCaller As LongPtr, ByVal szURL As String, ByVal szFileName As String, _
        ByVal dwReserved As Long, ByVal lpfnCB As LongPtr) As Long
#Else
    Private Declare Function URLDownloadToFile Lib "urlmon" Alias "URLDownloadToFileA" ( _
        ByVal pCaller As Long, ByVal szURL As String, ByVal szFileName As String, _
        ByVal dwReserved As Long, ByVal lpfnCB As Long) As Long
#End If

Sub CrearCarpetas()
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    
    Dim ws As Worksheet
    Set ws = ActiveSheet
    
    ' Trabajamos sobre la fila de la celda activa
    Dim fila As Long
    fila = ActiveCell.Row
    
    ' --- Control inicial: Verificar que "No_tocar._Nombre_carpeta" este relleno ---
    If Trim(ws.Range("No_tocar._Nombre_carpeta").Cells(fila, 1).Value) = "" Then
        MsgBox "Error: Falta asignar un nombre a la carpeta en 'No_tocar._Nombre_carpeta'.", vbCritical, "Error"
        Exit Sub
    End If
    ' ---------------------------------------------------------------------------
    
    '-------------------------------------------
    ' Obtener la fecha desde "Fecha_de_presentacion"
    Dim fecha As Date
    On Error GoTo FechaError
    fecha = ws.Range("Fecha_de_presentacion").Cells(fila, 1).Value
    On Error GoTo 0
    
    ' Extraer anio, mes y dia de la fecha
    Dim anio As String, mesNumero As String, dia As String, mesNombre As String
    anio = Format(fecha, "yyyy")
    mesNumero = Format(fecha, "mm")
    dia = Format(fecha, "dd")
    mesNombre = GetNombreMes(Month(fecha))
    
    ' Obtener la hora desde "Hora_limite" y formatearla sin los dos puntos
    Dim hora As String
    hora = Format(ws.Range("Hora_limite").Cells(fila, 1).Value, "hhmm")
    
    ' Nombre de la carpeta para el mes
    Dim nombreCarpetaMes As String
    nombreCarpetaMes = LimpiarTexto(mesNumero & " " & mesNombre)
    
    ' Obtener la informacion adicional de "No_tocar._Nombre_carpeta"
    Dim infoAdicional As String
    infoAdicional = ws.Range("No_tocar._Nombre_carpeta").Cells(fila, 1).Value
    infoAdicional = LimpiarTexto(infoAdicional)
    
    ' Obtener la informacion adicional de "Expediente"
    Dim infoAdicionalC As String
    infoAdicionalC = ws.Range("Expediente").Cells(fila, 1).Value
    infoAdicionalC = LimpiarTexto(infoAdicionalC)
    
    ' Construir el nombre de la carpeta final
    Dim nombreCarpetaFinal As String
    nombreCarpetaFinal = LimpiarTexto(dia & " " & mesNombre & " " & hora & " " & infoAdicional & " " & infoAdicionalC)
    
    '-------------------------------------------
    ' Obtener la ruta del archivo Excel y su carpeta superior
    Dim rutaExcel As String, rutaPadre As String
    rutaExcel = ThisWorkbook.Path
    rutaPadre = fso.GetParentFolderName(rutaExcel)
    
    ' Construir las rutas completas para las carpetas
    Dim rutaAnio As String, rutaMes As String, rutaFinal As String
    rutaAnio = rutaPadre & "\" & anio
    rutaMes = rutaAnio & "\" & nombreCarpetaMes
    rutaFinal = rutaMes & "\" & nombreCarpetaFinal
    
    On Error GoTo ErrorCreacion
    
    ' Crear carpeta del anio, si no existe
    If Not fso.FolderExists(rutaAnio) Then
        fso.CreateFolder rutaAnio
    End If
    
    ' Crear carpeta del mes, si no existe
    If Not fso.FolderExists(rutaMes) Then
        fso.CreateFolder rutaMes
    End If
    
    ' Si la carpeta final ya existe, avisar, abrirla y salir sin descargar nada
    If fso.FolderExists(rutaFinal) Then
        MsgBox "La carpeta ya existe." & vbCrLf & vbCrLf & _
               "Se abrira la carpeta, pero no se descargara ningun fichero ni se ejecutara ningun script.", _
               vbInformation, "Carpeta existente"
        Shell "explorer.exe """ & rutaFinal & """", vbNormalFocus
        Exit Sub
    End If
    
    ' Si la carpeta final no existe, pedir confirmacion para crearla
    Dim respuesta As String
    respuesta = InputBox("La carpeta final no existe. Escribe 'CREAR' para confirmar su creacion:", "Confirmar Creacion")
    If StrComp(Trim(respuesta), "CREAR", vbTextCompare) = 0 Then
        fso.CreateFolder rutaFinal
    Else
        MsgBox "No se confirmo la creacion de la carpeta. Operacion cancelada.", vbExclamation
        Exit Sub
    End If
    
    ' Guardar la ruta relativa desde la carpeta superior en "No_tocar._Ruta_carpeta"
    Dim rutaRelativa As String
    rutaRelativa = Replace(rutaFinal, rutaPadre, "")
    ws.Range("No_tocar._Ruta_carpeta").Cells(fila, 1).Value = rutaRelativa
    
    '-------------------------------------------
    ' Descargar el PDF usando la URL de "EnlaceInfonalia"
    Dim urlPDF As String
    urlPDF = Trim(ws.Range("EnlaceInfonalia").Cells(fila, 1).Value)
    
    ' Ajustar la URL si comienza con "//" o no tiene prefijo
    If Left(urlPDF, 2) = "//" Then
        urlPDF = "http:" & urlPDF
    ElseIf InStr(1, urlPDF, "http://", vbTextCompare) = 0 And InStr(1, urlPDF, "https://", vbTextCompare) = 0 Then
        urlPDF = "http://" & urlPDF
    End If
    
    ' Extraer el nombre original del fichero
    Dim pos As Long, originalFileName As String
    pos = InStrRev(urlPDF, "/")
    If pos > 0 Then
        originalFileName = Mid(urlPDF, pos + 1)
    Else
        originalFileName = urlPDF
    End If
    
    ' Nuevo nombre: "Infonalia " + nombre original del fichero
    Dim newFileName As String
    newFileName = "Infonalia " & originalFileName
    
    ' Ruta completa para guardar el PDF
    Dim savePath As String
    savePath = rutaFinal & "\" & newFileName
    
    Dim ret As Long
    ret = URLDownloadToFile(0, urlPDF, savePath, 0, 0)
    If ret <> 0 Then
        MsgBox "Error al descargar el PDF.", vbCritical
    End If
    
    '-------------------------------------------
    ' Crear un archivo de hipervinculo "HTTP.url" usando la URL de "Enlace_Perfil_del_contratante"
    Dim urlHTTP As String
    urlHTTP = Trim(ws.Range("Enlace_Perfil_del_contratante").Cells(fila, 1).Value)
    
    ' Ajustar la URL si comienza con "//" o le falta el prefijo
    If Left(urlHTTP, 2) = "//" Then
        urlHTTP = "http:" & urlHTTP
    ElseIf InStr(1, urlHTTP, "http://", vbTextCompare) = 0 And InStr(1, urlHTTP, "https://", vbTextCompare) = 0 Then
        urlHTTP = "http://" & urlHTTP
    End If
    
    ' Ruta para el archivo de hipervinculo
    Dim hyperlinkFile As String
    hyperlinkFile = rutaFinal & "\HTTP.url"
    
    ' Contenido del archivo .url
    Dim fileContent As String
    fileContent = "[InternetShortcut]" & vbCrLf & "URL=" & urlHTTP
    
    Dim textStream As Object
    Set textStream = fso.CreateTextFile(hyperlinkFile, True, False)
    textStream.Write fileContent
    textStream.Close
    
    '-------------------------------------------
    ' El BAT estandar llama al mismo lanzador central y Python que usa Llangon Suite.
    Dim scriptLanzador As String
    Dim pythonExe As String
    Dim suiteRoot As String
    
    suiteRoot = Environ$("LLANGON_SUITE_ROOT")
    If suiteRoot = "" Then
        suiteRoot = Environ$("USERPROFILE") & "\Documents\Codex\Llangon-SuiteV2"
    End If
    scriptLanzador = suiteRoot & "\herramientas_python\Descargar_Licitacion.py"
    pythonExe = suiteRoot & "\.venv\Scripts\python.exe"
    
    If Dir(scriptLanzador) = "" Then
        MsgBox "No se encontro el descargador central de Llangon Suite: " & scriptLanzador, vbCritical
        Exit Sub
    End If
    If Dir(pythonExe) = "" Then
        MsgBox "No se encontro el Python de Llangon Suite: " & pythonExe, vbCritical
        Exit Sub
    End If
    
    ' Finalmente, crear un .bat ejecutable, abrir la carpeta final y ejecutar el lanzador central
    ' Guardar el comando en un BAT ejecutable para poder relanzarlo manualmente
    Dim fsoLog As Object
    Dim logFile As Object
    Dim logPath As String
    
    logPath = rutaFinal & "\Descargar ficheros de la plataforma.bat"
    
    Set fsoLog = CreateObject("Scripting.FileSystemObject")
    Set logFile = fsoLog.CreateTextFile(logPath, True, False)
    
    logFile.WriteLine "@echo off"
    logFile.WriteLine "setlocal"
    logFile.WriteLine "cd /d ""%~dp0"""
    logFile.WriteLine "set ""PYTHON=" & pythonExe & """"
    logFile.WriteLine "set ""SCRIPT=" & scriptLanzador & """"
    logFile.WriteLine """%PYTHON%"" ""%SCRIPT%"""
    logFile.WriteLine "set ""EXIT_CODE=%ERRORLEVEL%"""
    logFile.WriteLine "if not ""%EXIT_CODE%""==""0"" pause"
    logFile.WriteLine "exit /b %EXIT_CODE%"
    logFile.Close
    
    Shell """" & logPath & """", vbNormalFocus
    Shell "explorer.exe """ & rutaFinal & """", vbNormalFocus
    Exit Sub
    
FechaError:
    MsgBox "Error: La celda definida como 'Fecha_de_presentacion' no contiene una fecha valida.", vbCritical
    Exit Sub

ErrorCreacion:
    MsgBox "Error al crear las carpetas. Verifica permisos o la validez de la ruta.", vbCritical
End Sub

' Funcion que devuelve el nombre del mes en espanol
Function GetNombreMes(mesNumero As Integer) As String
    Select Case mesNumero
        Case 1: GetNombreMes = "ENERO"
        Case 2: GetNombreMes = "FEBRERO"
        Case 3: GetNombreMes = "MARZO"
        Case 4: GetNombreMes = "ABRIL"
        Case 5: GetNombreMes = "MAYO"
        Case 6: GetNombreMes = "JUNIO"
        Case 7: GetNombreMes = "JULIO"
        Case 8: GetNombreMes = "AGOSTO"
        Case 9: GetNombreMes = "SEPTIEMBRE"
        Case 10: GetNombreMes = "OCTUBRE"
        Case 11: GetNombreMes = "NOVIEMBRE"
        Case 12: GetNombreMes = "DICIEMBRE"
        Case Else: GetNombreMes = ""
    End Select
End Function

' Funcion para limpiar el nombre de caracteres no permitidos en Windows
Function LimpiarTexto(Txt As String) As String
    Dim caracteresInvalidos As Variant, i As Integer
    caracteresInvalidos = Array("\", "/", ":", "*", "?", """", "<", ">", "|")
    For i = LBound(caracteresInvalidos) To UBound(caracteresInvalidos)
        Txt = Replace(Txt, caracteresInvalidos(i), "")
    Next i
    LimpiarTexto = Txt
End Function
