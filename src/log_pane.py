from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk


class LogPane(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._current_process = None

        # ── header bar ───────────────────────────────────────────────────────
        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=6,
            margin_top=6,
            margin_bottom=6,
        )

        self._title = Gtk.Label(label="Logs")
        self._title.add_css_class("heading")
        self._title.set_halign(Gtk.Align.START)
        self._title.set_hexpand(True)
        header.append(self._title)

        clear_btn = Gtk.Button(icon_name="edit-clear-symbolic")
        clear_btn.add_css_class("flat")
        clear_btn.set_tooltip_text("Clear logs")
        clear_btn.connect("clicked", self._on_clear)
        header.append(clear_btn)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        # ── text view ────────────────────────────────────────────────────────
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_vexpand(True)
        self._scrolled.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )

        self._view = Gtk.TextView()
        self._view.set_editable(False)
        self._view.set_cursor_visible(False)
        self._view.set_monospace(True)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._view.set_margin_start(12)
        self._view.set_margin_end(12)
        self._view.set_margin_top(8)
        self._view.set_margin_bottom(8)
        self._buffer = self._view.get_buffer()
        self._scrolled.set_child(self._view)

        self.append(header)
        self.append(sep)
        self.append(self._scrolled)

    # ── public API ───────────────────────────────────────────────────────────

    def set_process(self, process) -> None:
        """Show logs for a running/stopped ManagedProcess."""
        self._detach_current()
        self._current_process = process
        self._buffer.set_text("")

        if process is None:
            self._title.set_label("Logs")
            return

        self._title.set_label(f"Logs — {process.name}")
        for line in process.log_lines:
            self._insert(line)
        process.on_output = self._on_line

    def detach(self) -> None:
        """Disconnect from the current process without clearing the buffer."""
        self._detach_current()
        self._current_process = None

    def append_text(self, text: str, label: str = "Command output") -> None:
        """Append arbitrary text (used for one-off commands)."""
        if self._current_process:
            # Detach from current process
            if self._current_process.on_output == self._on_line:
                self._current_process.on_output = None
            self._current_process = None
        self._title.set_label(label)
        self._insert(text)

    # ── private ──────────────────────────────────────────────────────────────

    def _detach_current(self) -> None:
        if self._current_process and self._current_process.on_output == self._on_line:
            self._current_process.on_output = None

    def _on_line(self, line: str) -> None:
        self._insert(line)

    def _insert(self, text: str) -> None:
        end = self._buffer.get_end_iter()
        self._buffer.insert(end, text)
        GLib.idle_add(self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> bool:
        adj = self._scrolled.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return GLib.SOURCE_REMOVE

    def _on_clear(self, _btn) -> None:
        self._buffer.set_text("")
        if self._current_process:
            self._current_process.log_lines.clear()
