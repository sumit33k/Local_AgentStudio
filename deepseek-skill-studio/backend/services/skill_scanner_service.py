"""
Skill Scanner Service — security scanner for skills before installation.

Scans SKILL.md content for dangerous shell patterns, credential access,
network exfiltration, obfuscation, and other malicious constructs.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger("agentstudio.skill_scanner")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    pattern: str
    line: int
    description: str
    severity: str  # "low" | "medium" | "high" | "critical"


@dataclass
class ScanResult:
    risk_level: str  # "low" | "medium" | "high" | "critical"
    findings: List[Finding]
    safe: bool


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Each entry: (compiled_regex, description, severity)
_PATTERNS: List[tuple] = [
    # ── Critical ────────────────────────────────────────────────────────────
    (
        re.compile(r"rm\s+-[rf]{1,3}\s+/", re.IGNORECASE),
        "Destructive rm -rf targeting root path",
        "critical",
    ),
    (
        re.compile(r"rm\s+-rf", re.IGNORECASE),
        "Recursive force delete (rm -rf)",
        "critical",
    ),
    (
        re.compile(r"curl\s+.*\|\s*(ba)?sh", re.IGNORECASE),
        "Remote code execution: curl piped to shell",
        "critical",
    ),
    (
        re.compile(r"wget\s+.*\|\s*(ba)?sh", re.IGNORECASE),
        "Remote code execution: wget piped to shell",
        "critical",
    ),
    (
        re.compile(r"-EncodedCommand\b", re.IGNORECASE),
        "Encoded PowerShell command",
        "critical",
    ),
    (
        re.compile(r"powershell.*-enc\s+[A-Za-z0-9+/=]{20,}", re.IGNORECASE),
        "Base64-encoded PowerShell payload",
        "critical",
    ),
    (
        re.compile(r"eval\s*\(\s*atob\s*\(", re.IGNORECASE),
        "Obfuscated base64 eval (eval(atob(...)))",
        "critical",
    ),
    (
        re.compile(r"exec\s*\(\s*base64", re.IGNORECASE),
        "Obfuscated base64 exec",
        "critical",
    ),
    (
        re.compile(r"(?:~|/root|/home/[^/]+)/\.ssh/", re.IGNORECASE),
        "SSH key directory access",
        "critical",
    ),
    (
        re.compile(r"Login\s+Data|Chrome.*cookies|keychain", re.IGNORECASE),
        "Browser password/keychain file access",
        "critical",
    ),
    (
        re.compile(r"\.wallet\b|seed\s+phrase|mnemonic\s+phrase", re.IGNORECASE),
        "Cryptocurrency wallet or seed phrase access",
        "critical",
    ),
    (
        re.compile(
            r"curl\s+.*--data[- ]raw\s+\S+\s+https?://(?!127\.|localhost|0\.0\.0\.0)",
            re.IGNORECASE,
        ),
        "Network exfiltration: curl sending data to external host",
        "critical",
    ),
    (
        re.compile(
            r"wget\s+.*--post-data\s+\S+\s+https?://(?!127\.|localhost|0\.0\.0\.0)",
            re.IGNORECASE,
        ),
        "Network exfiltration: wget posting data to external host",
        "critical",
    ),
    # ── High ─────────────────────────────────────────────────────────────────
    (
        re.compile(r"\bsudo\b", re.IGNORECASE),
        "Privilege escalation via sudo",
        "high",
    ),
    (
        re.compile(r"chmod\s+777", re.IGNORECASE),
        "Dangerous file permission change (chmod 777)",
        "high",
    ),
    (
        re.compile(r"chown\s+root", re.IGNORECASE),
        "Ownership change to root (chown root)",
        "high",
    ),
    (
        re.compile(
            r"(?:password|passwd|secret|credential|api[_-]?key)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        "Hardcoded credential or secret access pattern",
        "high",
    ),
    (
        re.compile(r"printenv|env\s+\|\s*grep", re.IGNORECASE),
        "Environment variable dumping",
        "high",
    ),
    (
        re.compile(r"postinstall\b", re.IGNORECASE),
        "Package manager postinstall hook (potential supply chain risk)",
        "high",
    ),
    (
        re.compile(r"npm\s+install|pip\s+install|gem\s+install", re.IGNORECASE),
        "Package installation attempt inside skill content",
        "high",
    ),
    (
        re.compile(r"os\.symlink|ln\s+-s\b", re.IGNORECASE),
        "Symlink creation that may escape sandbox",
        "high",
    ),
    (
        re.compile(r"\\x[0-9a-f]{2}\\x[0-9a-f]{2}", re.IGNORECASE),
        "Binary/hex payload suspected",
        "high",
    ),
    (
        re.compile(r"\x00|\x01|\x02|\x03"),
        "Null/control bytes — possible hidden binary payload",
        "high",
    ),
    # ── Medium ────────────────────────────────────────────────────────────────
    (
        re.compile(r"\.\./\.\./", ),
        "Path traversal pattern (../../)",
        "medium",
    ),
    (
        re.compile(r"\.\.[\\/]", ),
        "Relative path traversal",
        "medium",
    ),
    (
        re.compile(
            r"(?:open|write|create)\s+.*(?:src/|app/|\.py\b|\.ts\b|\.js\b)",
            re.IGNORECASE,
        ),
        "Attempt to write to application source files",
        "medium",
    ),
    (
        re.compile(r"base64\s+-d|base64\s+--decode", re.IGNORECASE),
        "Base64 decoding (possible obfuscation)",
        "medium",
    ),
    (
        re.compile(r"\bssh\s+-[oO]\b|\bssh\s+root@", re.IGNORECASE),
        "SSH command with potentially dangerous options",
        "medium",
    ),
    # ── Low ───────────────────────────────────────────────────────────────────
    (
        re.compile(r"curl\s+", re.IGNORECASE),
        "curl usage (verify intent)",
        "low",
    ),
    (
        re.compile(r"wget\s+", re.IGNORECASE),
        "wget usage (verify intent)",
        "low",
    ),
]

# Risk scoring thresholds
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class SkillScannerService:
    """
    Scans SKILL.md content for malicious or dangerous patterns.

    Usage::

        scanner = SkillScannerService()
        result = scanner.scan(content, filename="my_skill/SKILL.md")
        if not result.safe:
            print(result.risk_level, result.findings)
    """

    def scan(self, content: str, filename: str = "") -> ScanResult:
        """
        Scan *content* and return a ScanResult.

        Lines are checked individually so line numbers are meaningful.
        """
        findings: List[Finding] = []
        lines = content.splitlines()

        for lineno, line in enumerate(lines, start=1):
            for regex, description, severity in _PATTERNS:
                if regex.search(line):
                    findings.append(
                        Finding(
                            pattern=regex.pattern,
                            line=lineno,
                            description=description,
                            severity=severity,
                        )
                    )

        risk_level = self._compute_risk(findings)
        safe = risk_level != "critical"

        if findings:
            logger.info(
                "Skill scan%s: risk=%s findings=%d",
                f" ({filename})" if filename else "",
                risk_level,
                len(findings),
            )

        return ScanResult(risk_level=risk_level, findings=findings, safe=safe)

    @staticmethod
    def _compute_risk(findings: List[Finding]) -> str:
        """
        Scoring rules:
        - Any critical finding  → "critical"
        - >= 2 high findings    → "high"
        - >= 1 high or >= 3 medium → "medium"
        - Otherwise             → "low"
        """
        critical_count = sum(1 for f in findings if f.severity == "critical")
        high_count = sum(1 for f in findings if f.severity == "high")
        medium_count = sum(1 for f in findings if f.severity == "medium")

        if critical_count >= 1:
            return "critical"
        if high_count >= 2:
            return "high"
        if high_count >= 1 or medium_count >= 3:
            return "medium"
        return "low"
