# AegisOps Windows wrapper: run one complete incident end to end.
# Runs the same scripts/run_incident.sh used on other platforms (via Git Bash).
#
# Usage (PowerShell):
#   .\scripts\run_incident.ps1 [-IncidentId <id>]
param(
    [string]$IncidentId = ""
)

$ErrorActionPreference = "Stop"
$bash = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path -LiteralPath $bash)) {
    $candidate = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
    if (-not $candidate) {
        throw "Git Bash not found. Install Git for Windows or set GIT_BASH."
    }
    $bash = $candidate
}

if ($IncidentId) {
    & $bash "scripts/run_incident.sh" $IncidentId
} else {
    & $bash "scripts/run_incident.sh"
}
exit $LASTEXITCODE