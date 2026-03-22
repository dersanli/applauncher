from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from .docker_manager import DockerManager

_STATUS_COLORS = {
    "running": "#33d17a",
    "exited": "#e01b24",
    "dead": "#e01b24",
    "paused": "#e5a50a",
    "restarting": "#e5a50a",
    "created": "#9a9996",
}


class DockerRow(Adw.ActionRow):
    def __init__(
        self,
        container: dict,
        docker: DockerManager,
        on_refresh: Optional[Callable] = None,
    ) -> None:
        super().__init__()
        self._name = container["name"]
        self._docker = docker
        self._on_refresh = on_refresh

        self.set_title(container["name"])
        self.set_subtitle(container["image"])

        # ── status dot ───────────────────────────────────────────────────────
        self._dot = Gtk.Label()
        self._dot.set_valign(Gtk.Align.CENTER)
        self.add_prefix(self._dot)

        # ── buttons ──────────────────────────────────────────────────────────
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_valign(Gtk.Align.CENTER)

        self._start_btn = Gtk.Button(label="Start")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.add_css_class("flat")
        self._start_btn.connect("clicked", self._on_start)
        box.append(self._start_btn)

        self._stop_btn = Gtk.Button(label="Stop")
        self._stop_btn.add_css_class("destructive-action")
        self._stop_btn.add_css_class("flat")
        self._stop_btn.connect("clicked", self._on_stop)
        box.append(self._stop_btn)

        restart_btn = Gtk.Button(label="Restart")
        restart_btn.add_css_class("flat")
        restart_btn.connect("clicked", self._on_restart)
        box.append(restart_btn)

        self.add_suffix(box)
        self.update(container)

    def update(self, container: dict) -> None:
        status = container["status"]
        color = _STATUS_COLORS.get(status, "#9a9996")
        self._dot.set_markup(f'<span color="{color}">●</span>')
        self._dot.set_tooltip_text(status)
        running = status == "running"
        self._start_btn.set_visible(not running)
        self._stop_btn.set_visible(running)

    # ── private ──────────────────────────────────────────────────────────────

    def _on_start(self, _btn) -> None:
        self._docker.start_container(self._name, callback=self._on_refresh)

    def _on_stop(self, _btn) -> None:
        self._docker.stop_container(self._name, callback=self._on_refresh)

    def _on_restart(self, _btn) -> None:
        self._docker.restart_container(self._name, callback=self._on_refresh)
