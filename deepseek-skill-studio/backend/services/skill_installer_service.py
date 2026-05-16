"""
Skill Installer Service — installs skills from various sources.

Sources supported:
  - Raw content (string)
  - ZIP archive (bytes)
  - GitHub URL (git clone via subprocess, no shell=True)
  - OpenClaw vendor directory

All skills are scanned before installation. Critical/high-risk skills are
quarantined rather than installed. The registry.json file records every
install decision.
"""

import json
import logging
import subprocess
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .skill_scanner_service import ScanResult, SkillScannerService

logger = logging.getLogger("agentstudio.skill_installer")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class InstallResult:
    name: str
    status: str  # "installed" | "quarantined" | "failed"
    source: str
    scan_result: ScanResult
    path: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_name(name: str) -> str:
    """Sanitise a skill name to a filesystem-safe slug."""
    import re
    slug = re.sub(r"[^\w\-]", "_", name.strip())
    return slug[:128] or "unnamed_skill"


def _atomic_write(path: Path, data: str) -> None:
    """Write *data* to *path* atomically via a .tmp sibling file."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _load_registry(registry_path: Path) -> dict:
    if registry_path.is_file():
        try:
            return json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"skills": {}}


def _save_registry(registry_path: Path, registry: dict) -> None:
    _atomic_write(registry_path, json.dumps(registry, indent=2))


def _record(
    registry: dict,
    name: str,
    status: str,
    source: str,
    risk_level: str,
    path: Optional[str],
) -> None:
    registry.setdefault("skills", {})[name] = {
        "status": status,
        "source": source,
        "risk_level": risk_level,
        "path": path,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SkillInstallerService:
    """
    Manages installation, quarantine, and registry tracking of skills.

    Directory layout under *skills_dir*::

        installed/      Active skills
        bundled/        Shipped-with-app skills (read-only by convention)
        openclaw/       Skills imported from OpenClaw vendor
        quarantined/    Rejected skills (kept for audit)
        registry.json   Installation records
    """

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.installed_dir = skills_dir / "installed"
        self.bundled_dir = skills_dir / "bundled"
        self.openclaw_dir = skills_dir / "openclaw"
        self.quarantine_dir = skills_dir / "quarantined"
        self.registry_path = skills_dir / "registry.json"

        for d in (
            self.installed_dir,
            self.bundled_dir,
            self.openclaw_dir,
            self.quarantine_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    # ── Core install ───────────────────────────────────────────────────────

    def install_from_content(
        self,
        name: str,
        content: str,
        source: str,
        scanner: SkillScannerService,
    ) -> InstallResult:
        """
        Scan *content* and install or quarantine accordingly.

        - critical / high → quarantine
        - medium / low    → install to installed/{name}/SKILL.md
        """
        safe_n = _safe_name(name)
        scan = scanner.scan(content, filename=f"{safe_n}/SKILL.md")

        registry = _load_registry(self.registry_path)

        if scan.risk_level in ("critical", "high"):
            dest = self.quarantine_dir / safe_n / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                _atomic_write(dest, content)
            except OSError as exc:
                logger.error("Failed to quarantine %s: %s", safe_n, exc)
                _record(registry, safe_n, "failed", source, scan.risk_level, None)
                _save_registry(self.registry_path, registry)
                return InstallResult(
                    name=safe_n,
                    status="failed",
                    source=source,
                    scan_result=scan,
                    path=None,
                )
            logger.warning(
                "Quarantined skill '%s' (risk=%s, source=%s)",
                safe_n,
                scan.risk_level,
                source,
            )
            _record(registry, safe_n, "quarantined", source, scan.risk_level, str(dest))
            _save_registry(self.registry_path, registry)
            return InstallResult(
                name=safe_n,
                status="quarantined",
                source=source,
                scan_result=scan,
                path=str(dest),
            )

        # Install
        dest = self.installed_dir / safe_n / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            _atomic_write(dest, content)
        except OSError as exc:
            logger.error("Failed to install %s: %s", safe_n, exc)
            _record(registry, safe_n, "failed", source, scan.risk_level, None)
            _save_registry(self.registry_path, registry)
            return InstallResult(
                name=safe_n,
                status="failed",
                source=source,
                scan_result=scan,
                path=None,
            )

        logger.info(
            "Installed skill '%s' (risk=%s, source=%s)",
            safe_n,
            scan.risk_level,
            source,
        )
        _record(registry, safe_n, "installed", source, scan.risk_level, str(dest))
        _save_registry(self.registry_path, registry)
        return InstallResult(
            name=safe_n,
            status="installed",
            source=source,
            scan_result=scan,
            path=str(dest),
        )

    # ── ZIP install ────────────────────────────────────────────────────────

    def install_from_zip(
        self,
        zip_bytes: bytes,
        scanner: SkillScannerService,
    ) -> List[InstallResult]:
        """
        Extract *zip_bytes*, find SKILL.md files, install each.

        Rejects any zip entry whose path contains ".." to prevent traversal.
        """
        results: List[InstallResult] = []

        try:
            with zipfile.ZipFile(
                __import__("io").BytesIO(zip_bytes), "r"
            ) as zf:
                entries = zf.namelist()
        except zipfile.BadZipFile as exc:
            logger.error("Invalid zip archive: %s", exc)
            return results

        skill_entries = [e for e in entries if e.endswith("SKILL.md")]

        if not skill_entries:
            logger.warning("No SKILL.md files found in zip archive")
            return results

        with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes), "r") as zf:
            for entry in skill_entries:
                # Security: reject path traversal inside zip
                if ".." in entry or entry.startswith("/"):
                    logger.warning("Rejected zip entry with traversal: %s", entry)
                    continue

                parts = Path(entry).parts
                # Derive skill name from directory component
                if len(parts) >= 2:
                    name = parts[-2]
                else:
                    name = Path(entry).stem or f"skill_{uuid.uuid4().hex[:8]}"

                try:
                    content = zf.read(entry).decode("utf-8", errors="replace")
                except (KeyError, OSError) as exc:
                    logger.warning("Could not read zip entry %s: %s", entry, exc)
                    continue

                result = self.install_from_content(
                    name=name,
                    content=content,
                    source="zip",
                    scanner=scanner,
                )
                results.append(result)

        return results

    # ── GitHub install ─────────────────────────────────────────────────────

    def install_from_github_url(
        self,
        github_url: str,
        branch: str,
        scanner: SkillScannerService,
    ) -> List[InstallResult]:
        """
        Clone a GitHub repository to a temp directory (no shell=True) and
        install all SKILL.md files found within it.
        """
        results: List[InstallResult] = []

        with tempfile.TemporaryDirectory(prefix="agentstudio_skill_clone_") as tmpdir:
            clone_cmd = [
                "git",
                "clone",
                "--depth", "1",
                "--branch", branch,
                "--single-branch",
                github_url,
                tmpdir,
            ]

            logger.info("Cloning %s (branch=%s) into temp dir", github_url, branch)
            try:
                proc = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    shell=False,  # NEVER shell=True
                )
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
                logger.error("git clone failed: %s", exc)
                return results

            if proc.returncode != 0:
                logger.error(
                    "git clone returned non-zero (%d): %s",
                    proc.returncode,
                    proc.stderr[:500],
                )
                return results

            tmp_path = Path(tmpdir)
            skill_files = list(tmp_path.rglob("SKILL.md"))
            logger.info("Found %d SKILL.md files in cloned repo", len(skill_files))

            for skill_md in skill_files:
                name = skill_md.parent.name or f"skill_{uuid.uuid4().hex[:8]}"
                try:
                    content = skill_md.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.warning("Could not read %s: %s", skill_md, exc)
                    continue

                result = self.install_from_content(
                    name=name,
                    content=content,
                    source=f"github:{github_url}@{branch}",
                    scanner=scanner,
                )
                results.append(result)

        return results

    # ── OpenClaw vendor import ─────────────────────────────────────────────

    def import_openclaw_skills(
        self,
        vendor_path: Path,
        scanner: SkillScannerService,
    ) -> List[InstallResult]:
        """
        Scan vendor_path/skills/ for skill directories with SKILL.md and
        install each into skills_dir/openclaw/{name}/SKILL.md.
        """
        results: List[InstallResult] = []
        skills_dir = vendor_path / "skills"

        if not skills_dir.is_dir():
            logger.info("OpenClaw vendor skills directory not found: %s", skills_dir)
            return results

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("Could not read %s: %s", skill_md, exc)
                continue

            name = skill_dir.name
            safe_n = _safe_name(name)
            scan = scanner.scan(content, filename=f"openclaw/{safe_n}/SKILL.md")

            registry = _load_registry(self.registry_path)

            if scan.risk_level in ("critical", "high"):
                dest = self.quarantine_dir / safe_n / "SKILL.md"
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    _atomic_write(dest, content)
                except OSError as exc:
                    logger.error("Quarantine write failed for %s: %s", safe_n, exc)
                    results.append(
                        InstallResult(
                            name=safe_n,
                            status="failed",
                            source="openclaw",
                            scan_result=scan,
                            path=None,
                        )
                    )
                    continue
                logger.warning("Quarantined openclaw skill '%s' (risk=%s)", safe_n, scan.risk_level)
                _record(registry, safe_n, "quarantined", "openclaw", scan.risk_level, str(dest))
                _save_registry(self.registry_path, registry)
                results.append(
                    InstallResult(
                        name=safe_n,
                        status="quarantined",
                        source="openclaw",
                        scan_result=scan,
                        path=str(dest),
                    )
                )
                continue

            dest = self.openclaw_dir / safe_n / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                _atomic_write(dest, content)
            except OSError as exc:
                logger.error("Install failed for openclaw skill %s: %s", safe_n, exc)
                results.append(
                    InstallResult(
                        name=safe_n,
                        status="failed",
                        source="openclaw",
                        scan_result=scan,
                        path=None,
                    )
                )
                continue

            logger.info("Imported openclaw skill '%s' (risk=%s)", safe_n, scan.risk_level)
            _record(registry, safe_n, "installed", "openclaw", scan.risk_level, str(dest))
            _save_registry(self.registry_path, registry)
            results.append(
                InstallResult(
                    name=safe_n,
                    status="installed",
                    source="openclaw",
                    scan_result=scan,
                    path=str(dest),
                )
            )

        return results
