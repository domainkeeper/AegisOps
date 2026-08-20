# AegisOps Windows wrapper: static security checks.
# Runs the same scripts/check_security.py used on other platforms (via Git Bash).
#
# Usage (PowerShell):
#   .\scripts\check_security.ps1
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

& $bash "scripts/check_security.sh"
exit $LASTEXITCODE