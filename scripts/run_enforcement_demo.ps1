# AegisOps Windows wrapper: authorization enforcement demonstration
# (Scene 1 BLOCKED / Scene 2 ALLOWED). Runs the same
# scripts/run_enforcement_demo.sh used on other platforms (via Git Bash).
#
# Requires a real ARMORIQ_API_KEY (and registered MCPs for the full proof).
#
# Usage (PowerShell):
#   .\scripts\run_enforcement_demo.ps1 [-IncidentId <id>]
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
    & $bash "scripts/run_enforcement_demo.sh" $IncidentId
} else {
    & $bash "scripts/run_enforcement_demo.sh"
}
exit $LASTEXITCODE