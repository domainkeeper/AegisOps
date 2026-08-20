# AegisOps Windows wrapper: stop all background agents and MCP servers.
# Usage (PowerShell):
#   .\scripts\stop_all.ps1
param()

$ErrorActionPreference = "Stop"
$bash = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path -LiteralPath $bash)) {
    $candidate = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
    if (-not $candidate) {
        throw "Git Bash not found. Install Git for Windows or set GIT_BASH."
    }
    $bash = $candidate
}

& $bash "scripts/stop_agents.sh"
& $bash "scripts/stop_mcps.sh"
exit $LASTEXITCODE