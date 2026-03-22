from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk

from .process_manager import ManagedProcess, ProcessStatus

_STATUS_COLORS = {
    ProcessStatus.RUNNING: "#33d17a",
    ProcessStatus.CRASHED: "#e01b24",
    ProcessStatus.STOPPED: "#9a9996",
}


class ProcessRow(Gtk.ListBoxRow):
    def __init__(
        self,
        process: ManagedProcess,
        on_select: Optional[Callable[[ManagedProcess], None]] = None,
    ) -> None:
        super().__init__()
        self.process = process
        self._on_select = on_select

        self.set_activatable(False)

        outer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        # ── status dot ───────────────────────────────────────────────────────
        self._dot = Gtk.Label()
        self._dot.set_valign(Gtk.Align.CENTER)
        self._refresh_dot()
        outer.append(self._dot)

        # ── text ─────────────────────────────────────────────────────────────
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label=process.name)
        title.set_halign(Gtk.Align.START)
        title.add_css_class("body")

        subtitle = Gtk.Label(label=process.command)
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("caption")
        subtitle.add_css_class("dim-label")
        subtitle.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        subtitle.set_max_width_chars(60)

        text_box.append(title)
        text_box.append(subtitle)
        outer.append(text_box)

        # ── log button ────────────────────────────────────────────────────────
        log_btn = Gtk.Button(label="Logs")
        log_btn.add_css_class("flat")
        log_btn.set_valign(Gtk.Align.CENTER)
        log_btn.connect("clicked", lambda _: on_select and on_select(process))
        outer.append(log_btn)

        # ── start / stop ─────────────────────────────────────────────────────
        self._start_btn = Gtk.Button(label="Start")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.set_valign(Gtk.Align.CENTER)
        self._start_btn.connect("clicked", self._on_start_clicked)
        outer.append(self._start_btn)

        self._stop_btn = Gtk.Button(label="Stop")
        self._stop_btn.add_css_class("destructive-action")
        self._stop_btn.set_valign(Gtk.Align.CENTER)
        self._stop_btn.connect("clicked", lambda _: process.stop())
        outer.append(self._stop_btn)

        self.set_child(outer)
        self._refresh_buttons()

        # Chain status callbacks
        _prev = process.on_status_change

        def _chained(status: str) -> None:
            self._on_status_change(status)
            if _prev:
                _prev(status)

        process.on_status_change = _chained

    # ── private ──────────────────────────────────────────────────────────────

    def _on_start_clicked(self, _btn) -> None:
        if self._on_select:
            self._on_select(self.process)
        self.process.start()

    def _on_status_change(self, _status: str) -> None:
        self._refresh_dot()
        self._refresh_buttons()

    def _refresh_dot(self) -> None:
        color = _STATUS_COLORS.get(self.process.status, "#9a9996")
        self._dot.set_markup(f'<span color="{color}">●</span>')
        self._dot.set_tooltip_text(self.process.status)

    def _refresh_buttons(self) -> None:
        running = self.process.is_running
        self._start_btn.set_visible(not running)
        self._stop_btn.set_visible(running)
