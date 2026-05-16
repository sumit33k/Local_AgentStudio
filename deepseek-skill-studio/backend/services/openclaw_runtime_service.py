"""
OpenClaw Runtime Service — manages the OpenClaw gateway subprocess.

The vendor path resolves three levels above the backend directory:
  backend/ -> deepseek-skill-studio/ -> Local_AgentStudio/ -> vendor/openclaw/
"""

import asyncio
import logging
import os
import signal
import subprocess
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Optional

import httpx

logger = logging.getLogger("agentstudio.openclaw_runtime")

OPENCLAW_DEFAULT_PORT = 18789
LOG_BUFFER_SIZE = 500


@dataclass
class OpenClawRuntimeStatus:
    installed: bool
    vendor_path: str
    dependency_status: str  # "ok" | "missing" | "unknown"
    running: bool
    pid: Optional[int]
    gateway_url: str
    port: int
    last_started_at: Optional[str]
    last_error: Optional[str]
    log_tail: list


def _mask_env(env: dict) -> dict:
    """Return a copy of env with secret values redacted for logging."""
    masked: dict = {}
    secret_keys = {"token", "key", "password", "secret", "api_key", "auth"}
    for k, v in env.items():
        if any(s in k.lower() for s in secret_keys):
            masked[k] = "***"
        else:
            masked[k] = v
    return masked


class OpenClawRuntimeService:
    """
    Manages the lifecycle of the OpenClaw gateway subprocess.

    The vendor path is resolved as: APP_DIR/../../../vendor/openclaw
    where APP_DIR is the backend directory (parent of this file's services/).
    """

    def __init__(self, port: int = OPENCLAW_DEFAULT_PORT):
        self.port = port
        self.gateway_url = f"http://127.0.0.1:{port}"

        # backend/services/openclaw_runtime_service.py -> backend -> deepseek-skill-studio -> Local_AgentStudio
        _services_dir = Path(__file__).parent
        _backend_dir = _services_dir.parent          # backend/
        _app_dir = _backend_dir.parent               # deepseek-skill-studio/
        _root_dir = _app_dir.parent                  # Local_AgentStudio/
        self.vendor_path: Path = (_root_dir / "vendor" / "openclaw").resolve()

        self._process: Optional[subprocess.Popen] = None
        self._log_buffer: Deque[str] = deque(maxlen=LOG_BUFFER_SIZE)
        self._last_started_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._log_reader_task: Optional[asyncio.Task] = None

    # ── Introspection ──────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        """Return True if package.json exists in the vendor directory."""
        return (self.vendor_path / "package.json").is_file()

    def _check_node_modules(self) -> bool:
        return (self.vendor_path / "node_modules").is_dir()

    def _check_built(self) -> bool:
        """Return True if the dist/entry.mjs build output exists."""
        return (self.vendor_path / "dist" / "entry.mjs").is_file()

    @staticmethod
    def _node_available() -> bool:
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def dependency_status(self) -> str:
        if not self.is_installed():
            return "missing"
        if self._check_node_modules() and self._check_built():
            return "ok"
        return "missing"

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    # ── Process management ─────────────────────────────────────────────────

    async def start(self) -> bool:
        """
        Start the OpenClaw gateway subprocess.

        Automatically runs npm/pnpm install + build if the vendor directory is
        an unbuilt source tree (missing node_modules or dist/entry.mjs).
        Returns True on successful start.
        """
        if self.is_running():
            logger.info("OpenClaw gateway already running (pid=%s)", self._process.pid)
            return True

        if not self.is_installed():
            msg = f"OpenClaw not found at {self.vendor_path}"
            logger.error(msg)
            self._last_error = msg
            return False

        if not self._node_available():
            msg = "node binary not found on PATH; cannot start OpenClaw gateway"
            logger.error(msg)
            self._last_error = msg
            return False

        # Auto-install dependencies if node_modules is missing
        if not self._check_node_modules():
            logger.info("node_modules missing — running npm install in %s", self.vendor_path)
            self._log_buffer.append("[setup] Running npm install...")
            ok = await asyncio.to_thread(self._run_npm_install)
            if not ok:
                self._last_error = "npm install failed — check logs for details"
                return False
            self._log_buffer.append("[setup] npm install complete.")

        # Auto-build if dist/entry.mjs is missing (source-tree install)
        if not self._check_built():
            logger.info("dist/entry.mjs missing — building OpenClaw in %s", self.vendor_path)
            self._log_buffer.append("[setup] Building OpenClaw (pnpm build / npm run build)...")
            ok = await asyncio.to_thread(self._run_build)
            if not ok:
                self._last_error = "build failed — run `pnpm install && pnpm build` in vendor/openclaw"
                return False
            self._log_buffer.append("[setup] Build complete.")

        if not self._check_built():
            self._last_error = "dist/entry.mjs not found after build — build may have failed silently"
            logger.error(self._last_error)
            return False

        mjs_path = self.vendor_path / "openclaw.mjs"
        started = False

        if mjs_path.is_file():
            started = await self._launch(
                ["node", str(mjs_path), "gateway", "--port", str(self.port)],
                cwd=self.vendor_path,
            )

        if not started:
            logger.info("Falling back to npx openclaw gateway")
            started = await self._launch(
                ["npx", "openclaw", "gateway", "--port", str(self.port)],
                cwd=self.vendor_path,
            )

        if started:
            self._last_started_at = datetime.now(timezone.utc).isoformat()
            self._last_error = None
            logger.info(
                "OpenClaw gateway started (pid=%s, url=%s)",
                self._process.pid,
                self.gateway_url,
            )
        return started

    def _run_npm_install(self) -> bool:
        """Synchronous: run npm install in vendor_path. Never shell=True."""
        try:
            result = subprocess.run(
                ["npm", "install", "--prefer-offline"],
                cwd=str(self.vendor_path),
                capture_output=True,
                text=True,
                timeout=300,
                shell=False,
            )
            for line in result.stdout.splitlines():
                self._log_buffer.append(f"[npm install] {line}")
            for line in result.stderr.splitlines():
                self._log_buffer.append(f"[npm install] {line}")
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            self._log_buffer.append(f"[npm install] error: {exc}")
            logger.warning("npm install error: %s", exc)
            return False

    def _run_build(self) -> bool:
        """
        Synchronous: build OpenClaw in vendor_path.
        Prefers pnpm (project standard); falls back to npm run build.
        Never shell=True.
        """
        for pkg_manager, build_cmd in [
            ("pnpm", ["pnpm", "install", "--frozen-lockfile=false"]),
            ("npm", ["npm", "install"]),
        ]:
            try:
                subprocess.run(
                    ["node", "--version"],  # confirm node still available
                    capture_output=True, shell=False, timeout=5,
                )
                subprocess.run(
                    [pkg_manager, "--version"],
                    capture_output=True, shell=False, timeout=5,
                    check=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue  # try next

            # Install
            try:
                r = subprocess.run(
                    [pkg_manager, "install"],
                    cwd=str(self.vendor_path),
                    capture_output=True, text=True, timeout=300, shell=False,
                )
                for line in r.stdout.splitlines():
                    self._log_buffer.append(f"[{pkg_manager} install] {line}")
                if r.returncode != 0:
                    continue
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue

            # Build
            try:
                build_args = [pkg_manager, "run", "build"] if pkg_manager == "npm" else [pkg_manager, "build"]
                r = subprocess.run(
                    build_args,
                    cwd=str(self.vendor_path),
                    capture_output=True, text=True, timeout=300, shell=False,
                )
                for line in r.stdout.splitlines():
                    self._log_buffer.append(f"[{pkg_manager} build] {line}")
                for line in r.stderr.splitlines():
                    self._log_buffer.append(f"[{pkg_manager} build] {line}")
                if r.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue

        return False

    async def _launch(self, cmd: list, cwd: Path) -> bool:
        """
        Launch subprocess with the given command. Never uses shell=True.
        Captures stdout/stderr into the log buffer.
        """
        env = {**os.environ}  # inherit env; do not strip secrets from process env

        logger.debug("Launching OpenClaw: %s (cwd=%s)", cmd, cwd)
        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=False,  # NEVER shell=True
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            msg = f"Failed to launch {cmd[0]}: {exc}"
            logger.warning(msg)
            self._last_error = msg
            self._process = None
            return False

        # Kick off async log reading
        loop = asyncio.get_event_loop()
        self._log_reader_task = loop.run_in_executor(None, self._drain_logs)
        return True

    def _drain_logs(self) -> None:
        """Read stdout/stderr from the subprocess and store in the deque."""
        if self._process is None or self._process.stdout is None:
            return
        try:
            for line in self._process.stdout:
                clean = line.rstrip("\n")
                # Mask secrets from log lines before storing
                clean = self._mask_line(clean)
                self._log_buffer.append(clean)
                logger.debug("[openclaw] %s", clean)
        except (OSError, ValueError):
            pass

    @staticmethod
    def _mask_line(line: str) -> str:
        """Rudimentary masking of tokens/keys in log output."""
        import re
        # Mask Bearer tokens
        line = re.sub(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer ***", line)
        # Mask key=<value> style pairs
        line = re.sub(
            r"(api[_-]?key|token|password|secret)\s*[:=]\s*\S+",
            r"\1=***",
            line,
            flags=re.IGNORECASE,
        )
        return line

    async def stop(self) -> bool:
        """Send SIGTERM; escalate to SIGKILL after 5 seconds."""
        if not self.is_running():
            return True

        pid = self._process.pid
        logger.info("Stopping OpenClaw gateway (pid=%s)", pid)

        try:
            self._process.send_signal(signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._process.wait),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("SIGTERM timed out; sending SIGKILL to pid=%s", pid)
            try:
                self._process.send_signal(signal.SIGKILL)
                await asyncio.to_thread(self._process.wait)
            except (ProcessLookupError, OSError):
                pass

        logger.info("OpenClaw gateway stopped (pid=%s)", pid)
        self._process = None
        return True

    async def restart(self) -> bool:
        """Stop then start the gateway."""
        await self.stop()
        return await self.start()

    # ── Health check ───────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if the gateway responds to GET /status."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.gateway_url}/status")
                return resp.status_code < 500
        except (httpx.HTTPError, httpx.TransportError, OSError):
            return False

    # ── Status export ──────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return a serialisable status dict suitable for API responses."""
        status = OpenClawRuntimeStatus(
            installed=self.is_installed(),
            vendor_path=str(self.vendor_path),
            dependency_status=self.dependency_status(),
            running=self.is_running(),
            pid=self._process.pid if self.is_running() else None,
            gateway_url=self.gateway_url,
            port=self.port,
            last_started_at=self._last_started_at,
            last_error=self._last_error,
            log_tail=list(self._log_buffer)[-50:],
        )
        return {
            "installed": status.installed,
            "vendor_path": status.vendor_path,
            "dependency_status": status.dependency_status,
            "running": status.running,
            "pid": status.pid,
            "gateway_url": status.gateway_url,
            "port": status.port,
            "last_started_at": status.last_started_at,
            "last_error": status.last_error,
            "log_tail": status.log_tail,
        }
