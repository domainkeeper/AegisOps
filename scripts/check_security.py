#!/usr/bin/env python
"""AegisOps static security checks - final-pass guard.

Scans the repository (excluding .venv, .git, .keys, logs, database, caches)
and fails on:
  - competition/hackathon framing terms (docs + scripts)
  - shell-execution patterns in the agent layer (agents must talk to Docker
    ONLY through the MCP layer)
  - secret material leaked into tracked files (real-looking ArmorIQ keys,
    private keys outside .keys/, real Gemini keys)
  - missing gitignore coverage for secret/runtime paths

Exit codes:
  0  clean
  1  findings (each printed as [FAIL])
  2  internal error (e.g. git not available)

Usage:
    python scripts/check_security.py
    scripts/check_security.sh
    scripts/check_security.ps1
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Competition/hackathon framing that must never appear in the project.
# "event" is intentionally NOT in the list: TimelineEvent/audit_events are core
# data-model terms, not competition framing - we match event only in a
# competition context (e.g. "hackathon event", "event day").
BANNED_TERMS = (
    r"\bhackathon\b",
    r"\bcompetition\b",
    r"\bjudges?\b",
    r"\bjudging\b",
    r"\bsubmission\b",
    r"\bscoring\b",
    r"\btrack\b",
    r"\bProblem 2\b",
    r"\bWho authorized that\??",
    r"hackathon event",
    r"competition event",
)
BANNED_TERMS_RE = [re.compile(p, re.IGNORECASE) for p in BANNED_TERMS]

# Shell-execution patterns banned in the agent layer (and everywhere).
SHELL_EXEC_PATTERNS = (
    re.compile(r"import\s+subprocess"),
    re.compile(r"from\s+subprocess"),
    re.compile(r"subprocess\.(run|Popen)\s*\("),
    re.compile(r"\bPopen\s*\("),
    re.compile(r"os\.system\s*\("),
    re.compile(r"shell\s*=\s*True"),
)

# Secret patterns that must only ever appear in tests/ or .env.example
# (placeholders) - never in tracked source or docs.
SECRET_PATTERNS = (
    re.compile(r"ak_live_[A-Za-z0-9_-]{8,}"),
    re.compile(r"ak_test_[A-Za-z0-9_-]{8,}(?<!_1234\b)"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),  # Gemini key shape
    re.compile(r"-----BEGIN (?:RSA |EC |)PRIVATE KEY-----"),
)

EXCLUDE_DIRS = {
    ".venv", ".git", ".keys", "logs", ".pytest_cache", "__pycache__",
    "node_modules", "database", "infrastructure",
}
# Files where placeholders / test keys are legitimate.
SECRET_ALLOWED_PREFIXES = (".env.example", "tests/", "docs/")
# The only legitimate ak_test_ value (hermetic test placeholder).
TEST_PLACEHOLDER = "ak_test_1234"

GITIGNORE_REQUIRED = (".env", ".keys/", "*.db", "logs/", ".pytest_cache/")


def _tracked_files() -> list[Path]:
    """Files git actually tracks (excludes untracked secrets by construction)."""
    out = subprocess.run(
        ["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [PROJECT_ROOT / line for line in out.splitlines() if line.strip()]


def _scan_eligible(path: Path) -> bool:
    """Skip directories and the checker's own file (it legitimately names the
    banned terms in its patterns)."""
    if path.name == "check_security.py":
        return False
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return False
    return True


def main() -> int:
    print("== AegisOps static security checks ==")
    findings = 0

    try:
        files = _tracked_files()
    except subprocess.CalledProcessError as exc:  # pragma: no cover
        print(f"[ERROR] git ls-files failed: {exc}")
        return 2

    # 1. Banned framing terms -------------------------------------------------
    print("[1/4] competition/hackathon framing")
    for path in files:
        if not _scan_eligible(path):
            continue
        if path.suffix not in (".py", ".md", ".sh", ".txt", ".yml", ".yaml", ".ps1", ".example"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover
            continue
        for regex in BANNED_TERMS_RE:
            for match in regex.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                snippet = text.splitlines()[line_no - 1].strip()[:100]
                print(f"  [FAIL] {path.relative_to(PROJECT_ROOT)}:{line_no} "
                      f"matches {regex.pattern!r}: {snippet}")
                findings += 1

    # 2. Shell-execution in the agent layer -----------------------------------
    print("[2/4] agent layer never shells out")
    for path in sorted((PROJECT_ROOT / "agents").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for regex in SHELL_EXEC_PATTERNS:
            match = regex.search(text)
            if match:
                print(f"  [FAIL] {path.relative_to(PROJECT_ROOT)} matches {regex.pattern!r}")
                findings += 1

    # Scripts are operator tooling and may use subprocess, but NEVER os.system /
    # shell=True (command injection and shell metacharacter hazards apply there too).
    for path in (PROJECT_ROOT / "scripts").glob("*.py"):
        if path.name == "check_security.py":
            continue
        text = path.read_text(encoding="utf-8")
        for regex in (re.compile(r"os\.system\s*\("), re.compile(r"shell\s*=\s*True")):
            match = regex.search(text)
            if match:
                print(f"  [FAIL] {path.relative_to(PROJECT_ROOT)} matches {regex.pattern!r}")
                findings += 1

    # 3. Secret material in tracked files -------------------------------------
    print("[3/4] secret material")
    for path in files:
        if not _scan_eligible(path):
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if path.suffix not in (".py", ".md", ".sh", ".txt", ".yml", ".yaml", ".json", ".example"):
            continue
        if path.suffix == ".md":
            continue  # docs only ever mention key PREFIXES, verified separately below
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover
            continue
        for regex in SECRET_PATTERNS:
            for match in regex.finditer(text):
                if rel == ".env.example" and match.group(0) in (
                    "ak_test_replace_with_your_real_key",
                ):
                    continue
                if rel.startswith("tests/") and match.group(0) == TEST_PLACEHOLDER:
                    continue
                print(f"  [FAIL] {rel} contains {regex.pattern!r} match: "
                      f"{match.group(0)[:20]}...")
                findings += 1

    # docs/ mention key prefixes only - ensure no full values slipped in
    for path in (PROJECT_ROOT / "docs").glob("*.md") if (PROJECT_ROOT / "docs").exists() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        for regex in SECRET_PATTERNS:
            match = regex.search(text)
            if match and "prefix" not in text[max(0, match.start() - 120):match.start() + 20]:
                print(f"  [FAIL] {path.relative_to(PROJECT_ROOT)} contains {regex.pattern!r}")
                findings += 1

    # 4. Gitignore coverage ----------------------------------------------------
    print("[4/4] gitignore coverage")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    for required in GITIGNORE_REQUIRED:
        if required not in gitignore:
            print(f"  [FAIL] .gitignore does not cover {required!r}")
            findings += 1
        else:
            print(f"  [PASS] .gitignore covers {required!r}")

    print()
    if findings == 0:
        print("RESULT: CLEAN - no findings")
        return 0
    print(f"RESULT: {findings} finding(s) - fix before demo day")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())