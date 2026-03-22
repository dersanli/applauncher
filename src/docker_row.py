from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .docker_manager import DockerManager

_STATUS_COLORS = {
    "running": "#33d17a",
    "exited": "#e01b24",
    "dead": "#e01b24",
    "paused": "#e5a50a",
    "restarting": "#e5a50a",
    "created": "#9a9996",
}


class DockerRow(Gtk.ListBoxRow):
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
        self.set_activatable(False)

        outer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        self._dot = Gtk.Label()
        self._dot.set_valign(Gtk.Align.CENTER)
        outer.append(self._dot)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label=container["name"])
        title.set_halign(Gtk.Align.START)
        title.add_css_class("body")

        subtitle = Gtk.Label(label=container["image"])
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("caption")
        subtitle.add_css_class("dim-label")

        text_box.append(title)
        text_box.append(subtitle)
        outer.append(text_box)

        self._start_btn = Gtk.Button(label="Start")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.set_valign(Gtk.Align.CENTER)
        self._start_btn.connect("clicked", lambda _: self._docker.start_container(self._name, callback=self._on_refresh))
        outer.append(self._start_btn)

        self._stop_btn = Gtk.Button(label="Stop")
        self._stop_btn.add_css_class("destructive-action")
        self._stop_btn.set_valign(Gtk.Align.CENTER)
        self._stop_btn.connect("clicked", lambda _: self._docker.stop_container(self._name, callback=self._on_refresh))
        outer.append(self._stop_btn)

        restart_btn = Gtk.Button(label="Restart")
        restart_btn.set_valign(Gtk.Align.CENTER)
        restart_btn.connect("clicked", lambda _: self._docker.restart_container(self._name, callback=self._on_refresh))
        outer.append(restart_btn)

        self.set_child(outer)
        self.update(container)

    def update(self, container: dict) -> None:
        status = container["status"]
        color = _STATUS_COLORS.get(status, "#9a9996")
        self._dot.set_markup(f'<span color="{color}">●</span>')
        self._dot.set_tooltip_text(status)
        running = status == "running"
        self._start_btn.set_visible(not running)
        self._stop_btn.set_visible(running)
