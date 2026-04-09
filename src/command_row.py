from __future__ import annotations

import os
import subprocess
import threading
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .config import CommandConfig


def _user_path() -> str:
    """Build a PATH that includes user-local tools (nvm, pnpm, pyenv etc.)
    by sourcing ~/.zshrc, which is where these tools register themselves."""
    home = os.path.expanduser("~")

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

    nvm_alias = os.path.join(home, ".nvm", "alias", "default")
    if os.path.isfile(nvm_alias):
        with open(nvm_alias) as f:
            version = f.read().strip().lstrip("v")
        node_bin = os.path.join(home, ".nvm", "versions", "node", f"v{version}", "bin")
        if os.path.isdir(node_bin):
            extra.append(node_bin)

    return ":".join(extra) + ":" + os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")


class CommandRow(Gtk.ListBoxRow):
    def __init__(
        self,
        config: CommandConfig,
        cwd: str,
        on_output: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._cwd = os.path.expanduser(cwd)
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
                env = {**os.environ, "PATH": _user_path()}
                proc = subprocess.Popen(
                    self._config.command,
                    shell=True,
                    cwd=self._cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
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
