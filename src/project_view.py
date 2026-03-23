from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from . import notifications
from .command_row import CommandRow
from .config import ProjectConfig
from .log_pane import LogPane
from .process_manager import ManagedProcess, ProcessStatus
from .process_row import ProcessRow


def _make_section(title: str) -> tuple[Gtk.Box, Gtk.ListBox]:
    """Returns (outer_box, list_box). Append rows to list_box."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

    label = Gtk.Label(label=title)
    label.add_css_class("heading")
    label.set_halign(Gtk.Align.START)
    label.set_margin_bottom(4)
    outer.append(label)

    list_box = Gtk.ListBox()
    list_box.set_selection_mode(Gtk.SelectionMode.NONE)
    list_box.add_css_class("boxed-list")
    outer.append(list_box)

    return outer, list_box


class ProjectView(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._project: Optional[ProjectConfig] = None
        self._all_processes: dict[str, dict[str, ManagedProcess]] = {}  # project_name -> {proc_name -> proc}
        self._last_proc_name: dict[str, str] = {}  # project_name -> last selected proc name
        self._process_rows: list[ProcessRow] = []
        self._command_rows: list[CommandRow] = []

        # ── empty state ──────────────────────────────────────────────────────
        self._empty = Adw.StatusPage()
        self._empty.set_title("No Project Selected")
        self._empty.set_description("Select a project from the sidebar")
        self._empty.set_icon_name("folder-symbolic")
        self._empty.set_vexpand(True)

        # ── content ──────────────────────────────────────────────────────────
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content.set_vexpand(True)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)

        inner = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=20,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        proc_section, self._proc_list = _make_section("Processes")
        cmd_section, self._cmd_list = _make_section("Commands")

        inner.append(proc_section)
        inner.append(cmd_section)
        clamp.set_child(inner)
        scroll.set_child(clamp)
        self._content.append(scroll)

        # Log pane
        self._content.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self._log_pane = LogPane()
        self._log_pane.set_size_request(-1, 220)
        self._content.append(self._log_pane)

        self.append(self._empty)
        self.append(self._content)
        self._content.set_visible(False)

    # ── public API ───────────────────────────────────────────────────────────

    def load_project(self, project: ProjectConfig) -> None:
        self._project = project
        self._empty.set_visible(False)
        self._content.set_visible(True)

        self._unload_ui()

        project_procs = self._all_processes.setdefault(project.name, {})

        for pc in project.processes:
            if pc.name not in project_procs:
                proc = ManagedProcess(pc.name, pc.command, project.directory)
                proc.on_status_change = self._make_crash_handler(proc, project.name)
                project_procs[pc.name] = proc
                if pc.auto_start:
                    GLib.idle_add(proc.start)
            proc = project_procs[pc.name]
            row = ProcessRow(proc, on_select=self._make_select_handler(project.name))
            self._proc_list.append(row)
            self._process_rows.append(row)

        # Restore last viewed process logs for this project, or clear
        last_name = self._last_proc_name.get(project.name)
        if last_name and last_name in project_procs:
            self._log_pane.set_process(project_procs[last_name])
        else:
            self._log_pane.set_process(None)

        for cc in project.commands:
            row = CommandRow(cc, project.directory, on_output=self._on_command_output)
            self._cmd_list.append(row)
            self._command_rows.append(row)

    def get_running_count(self) -> int:
        return sum(
            1
            for procs in self._all_processes.values()
            for proc in procs.values()
            if proc.is_running
        )

    def stop_all(self) -> None:
        """Stop all processes across all projects."""
        for project_procs in self._all_processes.values():
            for proc in project_procs.values():
                if proc.is_running:
                    proc.stop()

    # ── private ──────────────────────────────────────────────────────────────

    def _unload_ui(self) -> None:
        """Remove UI rows without stopping processes or clearing logs."""
        for row in self._process_rows:
            self._proc_list.remove(row)
        for row in self._command_rows:
            self._cmd_list.remove(row)
        self._process_rows.clear()
        self._command_rows.clear()
        self._log_pane.detach()

    def _make_select_handler(self, project_name: str):
        def on_select(proc) -> None:
            self._last_proc_name[project_name] = proc.name
            self._log_pane.set_process(proc)
        return on_select

    def _make_crash_handler(self, proc: ManagedProcess, project_name: str):
        def handler(status: str) -> None:
            if status == ProcessStatus.CRASHED:
                notifications.process_crashed(proc.name, project_name)
        return handler

    def _on_command_output(self, text: str, label: str) -> None:
        self._log_pane.append_text(text, f"Command — {label}")
