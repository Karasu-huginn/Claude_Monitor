# Security Report — 2026-04-16

## Summary
| Severity | Count |
|----------|-------|
| Critical | 0     |
| High     | 0     |
| Medium   | 1     |
| Low      | 58    |

## Scanners
- ✓ bandit (ran successfully)
- ✓ pip-audit (ran successfully)
- ✗ semgrep (skipped — not installed; `pip install semgrep`)
- ✗ trivy (skipped — not installed; see https://trivy.dev)
- ✗ gitleaks (skipped — not installed; see https://github.com/gitleaks/gitleaks)
- ✗ osv-scanner (skipped — not installed; see https://github.com/google/osv-scanner)

## Dependency Audit (pip-audit)

No known vulnerabilities found across all 13 audited packages (PyQt6, requests, pytest, and transitive dependencies).

## Findings

### Critical
None

### High
None

### Medium

#### [B108] Probable insecure usage of temp file/directory
- **Tool:** bandit
- **File:** tests/test_session_scanner.py:68
- **Details:** Test uses a hardcoded `/tmp` path. This is test-only code and poses no production risk — the test creates a temporary directory fixture for session scanning tests.

### Low

#### Production code (5 findings)

##### [B404] import subprocess
- **Tool:** bandit
- **Files:** install.py:5, ping_poller.py:6
- **Details:** Both files import `subprocess` for legitimate purposes — running PowerShell (installer) and the system `ping` command (network monitor). No user-controlled input reaches these calls. Acceptable risk.

##### [B603] subprocess call — check for execution of untrusted input
- **Tool:** bandit
- **Files:** install.py:40, ping_poller.py:37
- **Details:** Both subprocess calls use hardcoded command arguments (PowerShell shortcut creation, ping to 8.8.8.8). No dynamic or user-supplied input is passed. No injection vector exists.

##### [B607] Starting a process with a partial executable path
- **Tool:** bandit
- **File:** install.py:40
- **Details:** Calls `powershell` by name rather than absolute path. This is standard practice for a Windows installer utility and acceptable for the project's scope.

#### Test code (53 findings)

##### [B101] Use of assert detected (53 findings across all test files)
- **Tool:** bandit
- **Files:** tests/test_install.py, tests/test_ping_poller.py, tests/test_poller.py, tests/test_session_scanner.py
- **Details:** All instances are `assert` statements in pytest test functions. This is the standard and expected pattern for pytest — these files are never compiled with optimizations. No action needed.
