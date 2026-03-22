from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from .process_manager import ManagedProcess, ProcessStatus

_STATUS_COLORS = {
    ProcessStatus.RUNNING: "#33d17a",
    ProcessStatus.CRASHED: "#e01b24",
    ProcessStatus.STOPPED: "#9a9996",
}
_STATUS_TIPS = {
    ProcessStatus.RUNNING: "Running",
    ProcessStatus.CRASHED: "Crashed",
    ProcessStatus.STOPPED: "Stopped",
}


class ProcessRow(Adw.ActionRow):
    def __init__(
        self,
        process: ManagedProcess,
        on_select: Optional[Callable[[ManagedProcess], None]] = None,
    ) -> None:
        super().__init__()
        self.process = process
        self._on_select = on_select

        self.set_title(process.name)
        self.set_subtitle(GLib.markup_escape_text(process.command))
        self.set_activatable(True)

        # ── status dot ───────────────────────────────────────────────────────
        self._dot = Gtk.Label()
        self._dot.set_valign(Gtk.Align.CENTER)
        self._refresh_dot()
        self.add_prefix(self._dot)

        # ── action buttons ───────────────────────────────────────────────────
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_valign(Gtk.Align.CENTER)

        self._start_btn = Gtk.Button(label="Start")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.add_css_class("flat")
        self._start_btn.connect("clicked", self._on_start_clicked)
        box.append(self._start_btn)

        self._stop_btn = Gtk.Button(label="Stop")
        self._stop_btn.add_css_class("destructive-action")
        self._stop_btn.add_css_class("flat")
        self._stop_btn.connect("clicked", lambda _: process.stop())
        box.append(self._stop_btn)

        self.add_suffix(box)
        self._refresh_buttons()

        # Chain onto any existing on_status_change (e.g. crash notifier from project_view)
        _prev_status_cb = process.on_status_change

        def _chained_status(status: str) -> None:
            self._on_status_change(status)
            if _prev_status_cb:
                _prev_status_cb(status)

        process.on_status_change = _chained_status
        self.connect("activated", lambda _: self._on_select and self._on_select(process))

    # ── private ──────────────────────────────────────────────────────────────

    def _on_start_clicked(self, _btn) -> None:
        # Show logs immediately when Start is pressed
        if self._on_select:
            self._on_select(self.process)
        self.process.start()

    def _on_status_change(self, status: str) -> None:
        self._refresh_dot()
        self._refresh_buttons()

    def _refresh_dot(self) -> None:
        color = _STATUS_COLORS.get(self.process.status, "#9a9996")
        tip = _STATUS_TIPS.get(self.process.status, self.process.status)
        self._dot.set_markup(f'<span color="{color}">●</span>')
        self._dot.set_tooltip_text(tip)

    def _refresh_buttons(self) -> None:
        running = self.process.is_running
        self._start_btn.set_visible(not running)
        self._stop_btn.set_visible(running)
