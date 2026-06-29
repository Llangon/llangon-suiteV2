Option Explicit

Dim shell, scriptPath, command, i

If WScript.Arguments.Count < 1 Then
    WScript.Quit 2
End If

scriptPath = WScript.Arguments(0)
command = "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Quote(scriptPath)

For i = 1 To WScript.Arguments.Count - 1
    command = command & " " & Quote(WScript.Arguments(i))
Next

Set shell = CreateObject("WScript.Shell")
WScript.Quit shell.Run(command, 0, True)

Function Quote(value)
    Quote = """" & Replace(CStr(value), """", "\""") & """"
End Function

