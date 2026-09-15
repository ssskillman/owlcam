#Requires -Version 5.1
#Requires -RunAsAdministrator
# Makes the animal identifier survive sleep, reboot, and a closed terminal.
#
# Before this existed the identifier was a command typed into a PowerShell
# window. When this desktop slept, /identify went down for every visitor on the
# public site and the only symptom was "the photo-processing server is offline".
# Wake on LAN is not configured here, so nobody could bring it back remotely.
$ErrorActionPreference = "Stop"

$taskName = "OwlCam animal identifier"
$runner = Join-Path $PSScriptRoot "run-identifier.ps1"
if (-not (Test-Path $runner)) {
    throw "missing runner script at $runner"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`""

$trigger = New-ScheduledTaskTrigger -AtStartup

# S4U runs the task whether or not anyone is logged in and stores no password,
# while still running as this user so the venv and the Hugging Face and
# Ultralytics model caches in the profile are the ones that get used.
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

# Uvicorn is meant to run forever, so no execution time limit, and a crash
# should come back by itself.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

# Sleeping drops this node off the tailnet entirely, which no amount of
# service supervision can recover from. The display may still sleep.
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

# Re-asserting the publish is idempotent and removes the question of whether
# the serve config survived the last reboot.
$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty Source
if (-not $tailscale) {
    $tailscale = "C:\Program Files\Tailscale\tailscale.exe"
}
if (Test-Path $tailscale) {
    & $tailscale funnel --bg --yes --https=8443 http://127.0.0.1:8767
} else {
    Write-Warning "tailscale CLI not found; publish 8443 yourself"
}

# A uvicorn started by hand still owns the port, and the task would otherwise
# crash-loop against "address already in use" once a minute while the old
# process kept serving and hid the problem.
$listeners = Get-NetTCPConnection -LocalPort 8767 -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
    $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if ($owner) {
        Write-Host "Stopping existing listener on 8767: $($owner.ProcessName) (PID $($owner.Id))"
        Stop-Process -Id $owner.Id -Force
    }
}
if ($listeners) {
    Start-Sleep -Seconds 3
}

Start-ScheduledTask -TaskName $taskName

Write-Host ""
Write-Host "Installed '$taskName'. Verify with:"
Write-Host "  Get-ScheduledTask -TaskName '$taskName'"
Write-Host "  Get-Content `"$env:LOCALAPPDATA\owlcam\identifier.log`" -Tail 20"
Write-Host "  curl.exe http://127.0.0.1:8767/api/health"
Write-Host ""
Write-Host "If inference fails only under the task, CUDA is unhappy in a"
Write-Host "non-interactive session. Re-register with -LogonType Interactive"
Write-Host "and an -AtLogOn trigger, and enable automatic sign-in."
