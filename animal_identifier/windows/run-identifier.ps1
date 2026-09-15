#Requires -Version 5.1
# Starts the animal identifier and keeps its output where it can be read after
# an unattended restart. Task Scheduler cannot redirect a task's output, so the
# redirect lives here instead of in the registered action.
$ErrorActionPreference = "Stop"

$identifierRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$logDirectory = Join-Path $env:LOCALAPPDATA "owlcam"
$logFile = Join-Path $logDirectory "identifier.log"

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

# A scheduled task does not inherit the interactive shell's PATH, so uv is
# resolved rather than assumed.
$uv = Get-Command uv -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty Source
if (-not $uv) {
    $candidate = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $candidate) {
        $uv = $candidate
    } else {
        throw "uv was not found on PATH or in $candidate"
    }
}

Set-Location $identifierRoot

"$(Get-Date -Format o) starting identifier from $identifierRoot" |
    Add-Content -Path $logFile

# 127.0.0.1 on purpose: Tailscale Serve or Funnel is the only route in, so the
# API stays unreachable from the LAN no matter what the firewall allows.
& $uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767 *>> $logFile
