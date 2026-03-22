from __future__ import annotations

import subprocess
import threading
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .config import CommandConfig


class CommandRow(Gtk.ListBoxRow):
    def __init__(
        self,
        config: CommandConfig,
        cwd: str,
        on_output: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._cwd = cwd
        self._on_output = on_output
        self.set_activatable(False)

        outer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label=config.name)
        title.set_halign(Gtk.Align.START)
        title.add_css_class("body")

        subtitle = Gtk.Label(label=config.command)
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("caption")
        subtitle.add_css_class("dim-label")
        subtitle.set_ellipsize(3)
        subtitle.set_max_width_chars(60)

        text_box.append(title)
        text_box.append(subtitle)
        outer.append(text_box)

        self._run_btn = Gtk.Button(label="Run")
        self._run_btn.set_valign(Gtk.Align.CENTER)
        self._run_btn.connect("clicked", self._on_run)
        outer.append(self._run_btn)

        self.set_child(outer)

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
