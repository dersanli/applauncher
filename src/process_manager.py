from __future__ import annotations

import os
import signal
import subprocess
import threading
from typing import Callable, Optional

from gi.repository import GLib


def _user_path() -> str:
    """Build a PATH that includes user-local tools (nvm, pnpm, pyenv etc.)
    by sourcing ~/.zshrc, which is where these tools register themselves."""
    home = os.path.expanduser("~")

    # Try sourcing .zshrc in a non-interactive zsh to pick up nvm/pnpm/pyenv
    zshrc = os.path.join(home, ".zshrc")
    for shell in ("/bin/zsh", "/usr/bin/zsh"):
        if not os.path.exists(shell) or not os.path.exists(zshrc):
            continue
        try:
            result = subprocess.run(
                [shell, "-c", f"source {zshrc} 2>/dev/null; echo $PATH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            continue

    # Hard fallback: stitch known user-local paths together
    extra = [f"{home}/.local/share/pnpm", f"{home}/.local/bin"]

    # nvm: read the default alias to find the active node version
    nvm_alias = os.path.join(home, ".nvm", "alias", "default")
    if os.path.isfile(nvm_alias):
        with open(nvm_alias) as f:
            version = f.read().strip().lstrip("v")
        node_bin = os.path.join(home, ".nvm", "versions", "node", f"v{version}", "bin")
        if os.path.isdir(node_bin):
            extra.append(node_bin)

    return ":".join(extra) + ":" + os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")


class ProcessStatus:
    STOPPED = "stopped"
    RUNNING = "running"
    CRASHED = "crashed"


class ManagedProcess:
    def __init__(self, name: str, command: str, cwd: str) -> None:
        self.name = name
        self.command = command
        self.cwd = cwd
        self.status = ProcessStatus.STOPPED
        self.log_lines: list[str] = []

        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

        # Callbacks — always invoked on the main GLib thread
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        if self.is_running:
            return
        self.log_lines.clear()
        cwd = os.path.expanduser(self.cwd)
        try:
            self._process = subprocess.Popen(
                self.command,
                shell=True,
                executable="/bin/bash",
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
                env={**os.environ, "PATH": _user_path()},
            )
            self._set_status(ProcessStatus.RUNNING)
            threading.Thread(target=self._reader, daemon=True).start()
        except Exception as exc:
            self._append_log(f"[error] Failed to start: {exc}\n")
            self._set_status(ProcessStatus.CRASHED)

    def stop(self) -> None:
        if self._process and self.is_running:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except ProcessLookupError:
                self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    self._process.kill()
                self._process.wait()
        self._set_status(ProcessStatus.STOPPED)

    # ── private ──────────────────────────────────────────────────────────────

    def _reader(self) -> None:
        try:
            assert self._process and self._process.stdout
            for line in iter(self._process.stdout.readline, ""):
                if line:
                    self._append_log(line)
            exit_code = self._process.wait()
            # SIGTERM is -15; treat as intentional stop
            if exit_code in (0, -15):
                self._set_status(ProcessStatus.STOPPED)
            else:
                self._set_status(ProcessStatus.CRASHED)
        except Exception as exc:
            self._append_log(f"[error] {exc}\n")
            self._set_status(ProcessStatus.CRASHED)

    def _append_log(self, line: str) -> None:
        with self._lock:
            self.log_lines.append(line)
        if self.on_output:
            GLib.idle_add(self.on_output, line)

    def _set_status(self, status: str) -> None:
        self.status = status
        if self.on_status_change:
            GLib.idle_add(self.on_status_change, status)
