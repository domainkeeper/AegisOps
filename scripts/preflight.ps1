# AegisOps Windows wrapper: preflight readiness report.
# Runs the same scripts/preflight.py used on other platforms (via Git Bash).
#
# Usage (PowerShell):
#   .\scripts\preflight.ps1 [-LocalOnly]
param(
    [switch]$LocalOnly
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

$args = @()
if ($LocalOnly) { $args += "--local-only" }

& $bash "scripts/preflight.sh" @args
exit $LASTEXITCODE