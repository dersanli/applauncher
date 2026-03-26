from __future__ import annotations

import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

# ── log level detection ───────────────────────────────────────────────────────

_LEVEL_RE = re.compile(
    r'\b(DEBUG|TRACE|VERBOSE|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b',
    re.IGNORECASE,
)

_LEVEL_MAP = {
    "debug": "debug", "trace": "debug", "verbose": "debug",
    "info": "info",
    "warn": "warning", "warning": "warning",
    "error": "error", "critical": "error", "fatal": "error",
}

_LEVELS = ["debug", "info", "warning", "error"]
_LEVEL_LABELS = {"debug": "Debug", "info": "Info", "warning": "Warning", "error": "Error"}


def _detect_level(line: str) -> str | None:
    m = _LEVEL_RE.search(line)
    return _LEVEL_MAP.get(m.group(1).lower()) if m else None


class LogPane(Gtk.Box):
    def __init__(self, show_line_numbers: bool = False, word_wrap: bool = True) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._current_process = None
        self._show_line_numbers = show_line_numbers
        self._word_wrap = word_wrap
        self._line_count = 0
        self._filters_per_process: dict[str, set[str]] = {}  # proc name → active levels

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

        # ── filter menu button ────────────────────────────────────────────────
        self._filter_btn = Gtk.MenuButton()
        self._filter_btn.set_icon_name("preferences-other-symbolic")
        self._filter_btn.add_css_class("flat")
        self._filter_btn.set_tooltip_text("Filter by log level")
        self._filter_btn.set_popover(self._build_filter_popover())
        header.append(self._filter_btn)

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
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if word_wrap else Gtk.WrapMode.NONE)
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
        self._line_count = 0

        if process is None:
            self._title.set_label("Logs")
            self._restore_filter_ui("")
            return

        self._title.set_label(f"Logs — {process.name}")
        self._restore_filter_ui(process.name)
        for line in process.log_lines:
            self._insert(line)
        process.on_output = self._on_line

    def set_show_line_numbers(self, show: bool) -> None:
        if self._show_line_numbers == show:
            return
        self._show_line_numbers = show
        if show:
            self._view.set_wrap_mode(Gtk.WrapMode.NONE)
        else:
            self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if self._word_wrap else Gtk.WrapMode.NONE)
        self._rerender()

    def set_word_wrap(self, wrap: bool) -> None:
        self._word_wrap = wrap
        if not self._show_line_numbers:
            self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if wrap else Gtk.WrapMode.NONE)

    def detach(self) -> None:
        """Disconnect from the current process without clearing the buffer."""
        self._detach_current()
        self._current_process = None

    def append_text(self, text: str, label: str = "Command output") -> None:
        """Append arbitrary text (used for one-off commands)."""
        if self._current_process:
            if self._current_process.on_output == self._on_line:
                self._current_process.on_output = None
            self._current_process = None
        self._title.set_label(label)
        self._insert(text)

    # ── private ──────────────────────────────────────────────────────────────

    def _build_filter_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_start=8,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        self._filter_checks: dict[str, Gtk.CheckButton] = {}
        for level in _LEVELS:
            check = Gtk.CheckButton(label=_LEVEL_LABELS[level])
            check.connect("toggled", self._on_filter_toggled, level)
            box.append(check)
            self._filter_checks[level] = check

        popover.set_child(box)
        return popover

    def _active_filters(self) -> set[str]:
        if self._current_process is None:
            return set()
        return self._filters_per_process.get(self._current_process.name, set())

    def _on_filter_toggled(self, check: Gtk.CheckButton, level: str) -> None:
        if self._current_process is None:
            return
        filters = self._filters_per_process.setdefault(self._current_process.name, set())
        if check.get_active():
            filters.add(level)
        else:
            filters.discard(level)
        self._update_filter_btn_style()
        self._rerender()

    def _restore_filter_ui(self, proc_name: str) -> None:
        filters = self._filters_per_process.get(proc_name, set())
        for level, check in self._filter_checks.items():
            check.handler_block_by_func(self._on_filter_toggled)
            check.set_active(level in filters)
            check.handler_unblock_by_func(self._on_filter_toggled)
        self._update_filter_btn_style()

    def _update_filter_btn_style(self) -> None:
        if self._active_filters():
            self._filter_btn.add_css_class("suggested-action")
        else:
            self._filter_btn.remove_css_class("suggested-action")

    def _passes_filter(self, line: str) -> bool:
        filters = self._active_filters()
        if not filters:
            return True
        level = _detect_level(line)
        if level is None:
            return True  # unclassified lines (stack traces etc.) always show
        return level in filters

    def _rerender(self) -> None:
        self._buffer.set_text("")
        self._line_count = 0
        if self._current_process:
            for line in self._current_process.log_lines:
                self._insert(line)

    def _detach_current(self) -> None:
        if self._current_process and self._current_process.on_output == self._on_line:
            self._current_process.on_output = None

    def _on_line(self, line: str) -> None:
        self._insert(line)

    def _insert(self, text: str) -> None:
        if not self._passes_filter(text):
            return
        if self._show_line_numbers:
            self._line_count += 1
            text = f"{self._line_count:>4} │ {text}"
        end = self._buffer.get_end_iter()
        self._buffer.insert(end, text)
        GLib.idle_add(self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> bool:
        adj = self._scrolled.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return GLib.SOURCE_REMOVE

    def _on_clear(self, _btn) -> None:
        self._buffer.set_text("")
        self._line_count = 0
        if self._current_process:
            self._current_process.log_lines.clear()
