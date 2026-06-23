Option Explicit

Dim shell, fso, scriptDir, projectRoot, runner, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
If WScript.Arguments.Count > 0 Then
  projectRoot = WScript.Arguments(0)
Else
  projectRoot = fso.GetParentFolderName(scriptDir)
End If

runner = fso.BuildPath(projectRoot, "scripts\run_monitor_scheduler_once.ps1")
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & _
  Chr(34) & runner & Chr(34) & " -ProjectRoot " & Chr(34) & projectRoot & Chr(34)

shell.CurrentDirectory = projectRoot
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
