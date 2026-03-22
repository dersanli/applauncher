from __future__ import annotations

import os
import subprocess
import threading
from typing import Callable, Optional

from gi.repository import GLib


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
            )
            self._set_status(ProcessStatus.RUNNING)
            threading.Thread(target=self._reader, daemon=True).start()
        except Exception as exc:
            self._append_log(f"[error] Failed to start: {exc}\n")
            self._set_status(ProcessStatus.CRASHED)

    def stop(self) -> None:
        if self._process and self.is_running:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
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
