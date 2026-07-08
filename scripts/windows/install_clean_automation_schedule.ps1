param(
    [switch]$NoSelfElevate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$BackupRoot = Join-Path $RuntimeRoot ("task_backups\" + (Get-Date -Format "yyyy-MM-dd_HHmmss"))
$HiddenRunner = Join-Path $ScriptRoot "run_powershell_hidden.vbs"
$Wscript = (Get-Command wscript.exe).Source

$Principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if (-not $NoSelfElevate) {
        $Arguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", "`"$PSCommandPath`"",
            "-NoSelfElevate"
        )
        Write-Host "Se necesitan permisos de Administrador para modificar tareas programadas."
        Write-Host "Solicitando elevacion UAC..."
        Start-Process -FilePath "powershell.exe" -ArgumentList $Arguments -Verb RunAs -WorkingDirectory $ProjectRoot
        Write-Host "Se ha lanzado una ventana elevada. Acepta el aviso de Windows y revisa su resultado."
        exit 0
    }
    Write-Host "Este instalador debe ejecutarse en una ventana de PowerShell abierta como Administrador."
    Write-Host "No se ha modificado ninguna tarea programada."
    exit 5
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$OldTasks = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup",
    "LlangonSuite-AgendaWake",
    "LlangonSuiteV2-MonitorScheduler",
    "LlangonSuite-KeeperTick",
    "LlangonSuite-WakeTick"
)
$LegacyTasks = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup",
    "LlangonSuite-AgendaWake",
    "LlangonSuiteV2-MonitorScheduler"
)

function Safe-FileName {
    param([string]$Text)
    return ($Text -replace '[\\/:*?"<>|]', '_')
}

function Get-ObjectProperty {
    param(
        [object]$Object,
        [string]$Name
    )
    if ($null -eq $Object) {
        return $null
    }
    $Property = $Object.PSObject.Properties[$Name]
    if ($null -eq $Property) {
        return $null
    }
    return $Property.Value
}

function Export-LlangonTask {
    param([string]$Name)
    $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        return $null
    }
    $Info = Get-ScheduledTaskInfo -TaskName $Name
    $Safe = Safe-FileName $Name
    Export-ScheduledTask -TaskName $Name | Out-File -LiteralPath (Join-Path $BackupRoot "$Safe.xml") -Encoding utf8
    return [pscustomobject]@{
        name = $Name
        state = $Task.State.ToString()
        enabled = $Task.Settings.Enabled
        wake_to_run = $Task.Settings.WakeToRun
        last_run = $Info.LastRunTime
        next_run = $Info.NextRunTime
        last_result = $Info.LastTaskResult
        actions = @($Task.Actions | ForEach-Object {
            [pscustomobject]@{
                execute = $_.Execute
                arguments = $_.Arguments
                working_directory = $_.WorkingDirectory
            }
        })
        triggers = @($Task.Triggers | ForEach-Object {
            $Repetition = Get-ObjectProperty $_ "Repetition"
            [pscustomobject]@{
                type = $_.CimClass.CimClassName
                enabled = Get-ObjectProperty $_ "Enabled"
                start = Get-ObjectProperty $_ "StartBoundary"
                days_of_week = Get-ObjectProperty $_ "DaysOfWeek"
                days_interval = Get-ObjectProperty $_ "DaysInterval"
                weeks_interval = Get-ObjectProperty $_ "WeeksInterval"
                repetition_interval = Get-ObjectProperty $Repetition "Interval"
                repetition_duration = Get-ObjectProperty $Repetition "Duration"
            }
        })
    }
}

$Summary = @()
foreach ($Name in $OldTasks) {
    $Item = Export-LlangonTask -Name $Name
    if ($null -ne $Item) {
        $Summary += $Item
    }
}
$Summary | ConvertTo-Json -Depth 8 | Out-File -LiteralPath (Join-Path $BackupRoot "summary.json") -Encoding utf8

$Markdown = @(
    "# Backup de tareas Llangon Suite",
    "",
    "Fecha: $(Get-Date -Format s)",
    "",
    "| Nombre | Estado | Habilitada | WakeToRun | Ultima | Proxima | Resultado |",
    "|---|---|---:|---:|---|---|---:|"
)
foreach ($Item in $Summary) {
    $Markdown += "| $($Item.name) | $($Item.state) | $($Item.enabled) | $($Item.wake_to_run) | $($Item.last_run) | $($Item.next_run) | $($Item.last_result) |"
}
$Markdown | Out-File -LiteralPath (Join-Path $BackupRoot "summary.md") -Encoding utf8

function Register-HiddenPowerShellTask {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [Microsoft.Management.Infrastructure.CimInstance[]]$Triggers,
        [bool]$WakeToRun,
        [string]$Description
    )
    $ActionArgs = "`"$HiddenRunner`" `"$ScriptPath`""
    $Action = New-ScheduledTaskAction -Execute $Wscript -Argument $ActionArgs -WorkingDirectory $ProjectRoot
    $Settings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -WakeToRun:$WakeToRun `
        -ExecutionTimeLimit (New-TimeSpan -Hours 3)
    Register-ScheduledTask `
        -TaskName $Name `
        -Action $Action `
        -Trigger $Triggers `
        -Settings $Settings `
        -Description $Description `
        -Force | Out-Null
    Enable-ScheduledTask -TaskName $Name | Out-Null
}

$KeeperScript = Join-Path $ScriptRoot "run_keeper_tick.ps1"
$WakeScript = Join-Path $ScriptRoot "run_wake_tick.ps1"

$KeeperTriggers = @(
    $(New-ScheduledTaskTrigger -AtLogOn),
    $(New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(5)) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650))
)
$WakeTriggers = @(
    $(New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At (Get-Date -Date "08:00")),
    $(New-ScheduledTaskTrigger -Daily -At (Get-Date -Date "15:55"))
)

Register-HiddenPowerShellTask `
    -Name "LlangonSuite-KeeperTick" `
    -ScriptPath $KeeperScript `
    -Triggers $KeeperTriggers `
    -WakeToRun $false `
    -Description "Vigila la web local y ejecuta el tick interno de automatizaciones sin despertar el PC."

Register-HiddenPowerShellTask `
    -Name "LlangonSuite-WakeTick" `
    -ScriptPath $WakeScript `
    -Triggers $WakeTriggers `
    -WakeToRun $true `
    -Description "Despierta el PC a las 08:00 laborables y 15:55 diario para que la Suite decida tareas pendientes."

$RemovalFailures = @()
foreach ($Name in $LegacyTasks) {
    $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($Task) {
        try {
            Unregister-ScheduledTask -TaskName $Name -Confirm:$false
            Write-Host "Eliminada tarea legacy: $Name"
        }
        catch {
            $RemovalFailures += "${Name}: $($_.Exception.Message)"
            Write-Host "No se pudo eliminar tarea legacy: $Name"
            try {
                Disable-ScheduledTask -TaskName $Name | Out-Null
                Write-Host "Tarea legacy deshabilitada: $Name"
            }
            catch {
                $RemovalFailures += "${Name} disable: $($_.Exception.Message)"
            }
        }
    }
}

Write-Host ""
Write-Host "Backup de tareas exportado en: $BackupRoot"
Write-Host "Tareas finales creadas:"
Write-Host " - LlangonSuite-KeeperTick (WakeToRun=False)"
Write-Host " - LlangonSuite-WakeTick (WakeToRun=True)"
if ($RemovalFailures.Count -gt 0) {
    Write-Host ""
    Write-Host "Advertencia: quedaron tareas legacy sin eliminar/deshabilitar:"
    $RemovalFailures | ForEach-Object { Write-Host " - $_" }
    exit 6
}
