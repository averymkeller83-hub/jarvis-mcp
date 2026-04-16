"""Safe osascript/Shortcuts execution wrapper for Jarvis MCP.

All CONTROL handlers route through this module to execute AppleScript,
macOS Shortcuts, and URL schemes.  Every function returns an ``OSAResult``
and **never raises** — errors are captured in the result object.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass


@dataclass
class OSAResult:
    """Outcome of an osascript / subprocess execution."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    script: str


async def run_osascript(script: str, timeout: float = 10.0) -> OSAResult:
    """Execute an AppleScript string via ``/usr/bin/osascript -e``.

    Parameters
    ----------
    script:
        The AppleScript source to execute.
    timeout:
        Maximum seconds to wait before killing the process.

    Returns
    -------
    OSAResult
        Always returned — never raises.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return OSAResult(
                success=False,
                stdout="",
                stderr=f"Timed out after {timeout}s",
                return_code=-1,
                script=script,
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        rc = proc.returncode or 0

        return OSAResult(
            success=rc == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=rc,
            script=script,
        )
    except Exception as exc:  # noqa: BLE001
        return OSAResult(
            success=False,
            stdout="",
            stderr=str(exc),
            return_code=-1,
            script=script,
        )


async def run_shortcut(name: str, input_text: str | None = None) -> OSAResult:
    """Run a macOS Shortcut by name.

    Uses create_subprocess_exec with explicit argument list (no shell
    interpolation) to prevent injection.

    Parameters
    ----------
    name:
        The Shortcut name exactly as it appears in Shortcuts.app.
    input_text:
        Optional text input to pass via ``--input-text``.
    """
    cmd: list[str] = ["/usr/bin/shortcuts", "run", name]
    if input_text is not None:
        cmd += ["--input-text", input_text]
    script_repr = " ".join(shlex.quote(c) for c in cmd)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=30.0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return OSAResult(
                success=False,
                stdout="",
                stderr="Shortcut timed out after 30s",
                return_code=-1,
                script=script_repr,
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        rc = proc.returncode or 0

        return OSAResult(
            success=rc == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=rc,
            script=script_repr,
        )
    except Exception as exc:  # noqa: BLE001
        return OSAResult(
            success=False,
            stdout="",
            stderr=str(exc),
            return_code=-1,
            script=script_repr,
        )


async def open_url(url: str) -> OSAResult:
    """Open a URL via ``/usr/bin/open``.

    Supports ``tel:``, ``facetime:``, ``https:`` and other URL schemes.
    Uses create_subprocess_exec with an explicit argument list (no shell).
    """
    cmd = ["/usr/bin/open", url]
    script_repr = f"open {shlex.quote(url)}"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=10.0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return OSAResult(
                success=False,
                stdout="",
                stderr="open timed out after 10s",
                return_code=-1,
                script=script_repr,
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        rc = proc.returncode or 0

        return OSAResult(
            success=rc == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=rc,
            script=script_repr,
        )
    except Exception as exc:  # noqa: BLE001
        return OSAResult(
            success=False,
            stdout="",
            stderr=str(exc),
            return_code=-1,
            script=script_repr,
        )


def _osa_escape(s: str) -> str:
    """Escape a string for safe embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


async def check_app_running(app_name: str) -> bool:
    """Return ``True`` if *app_name* is currently running."""
    safe = _osa_escape(app_name)
    script = (
        f'tell application "System Events" to '
        f'(name of processes) contains "{safe}"'
    )
    result = await run_osascript(script)
    return result.success and result.stdout.strip().lower() == "true"


async def launch_app(app_name: str) -> OSAResult:
    """Launch *app_name* if it is not already running (diagnostic auto-fix)."""
    safe = _osa_escape(app_name)
    script = f'tell application "{safe}" to activate'
    return await run_osascript(script, timeout=15.0)
