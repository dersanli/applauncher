from __future__ import annotations

import subprocess
import threading
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from .config import CommandConfig


class CommandRow(Adw.ActionRow):
    def __init__(
        self,
        config: CommandConfig,
        cwd: str,
        on_output: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._cwd = cwd
        self._on_output = on_output  # fn(text, label)

        self.set_title(config.name)
        self.set_subtitle(config.command)

        self._run_btn = Gtk.Button(label="Run")
        self._run_btn.add_css_class("flat")
        self._run_btn.set_valign(Gtk.Align.CENTER)
        self._run_btn.connect("clicked", self._on_run)
        self.add_suffix(self._run_btn)

    def _on_run(self, btn: Gtk.Button) -> None:
        btn.set_sensitive(False)
        btn.set_label("Running…")

        if self._on_output:
            self._on_output(f"\n$ {self._config.command}\n", self._config.name)

        def _run() -> None:
            try:
                proc = subprocess.Popen(
                    self._config.command,
                    shell=True,
                    cwd=self._cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert proc.stdout
                for line in iter(proc.stdout.readline, ""):
                    if line and self._on_output:
                        GLib.idle_add(self._on_output, line, self._config.name)
                proc.wait()
            except Exception as exc:
                if self._on_output:
                    GLib.idle_add(self._on_output, f"[error] {exc}\n", self._config.name)
            finally:
                GLib.idle_add(self._reset_button, btn)

        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _reset_button(btn: Gtk.Button) -> None:
        btn.set_sensitive(True)
        btn.set_label("Run")
