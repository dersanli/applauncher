from __future__ import annotations

import threading
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from . import notifications
from .command_row import CommandRow
from .config import ProjectConfig
from .docker_manager import DockerManager
from .docker_row import DockerRow
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
    def __init__(self, docker: DockerManager) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._docker = docker
        self._project: Optional[ProjectConfig] = None
        self._processes: dict[str, ManagedProcess] = {}
        self._docker_rows: dict[str, DockerRow] = {}
        self._process_rows: list[ProcessRow] = []
        self._docker_row_list: list[DockerRow] = []
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
        docker_section, self._docker_list = _make_section("Docker Containers")
        cmd_section, self._cmd_list = _make_section("Commands")

        inner.append(proc_section)
        inner.append(docker_section)
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

        self._docker.on_containers_updated = self._on_containers_updated

    # ── public API ───────────────────────────────────────────────────────────

    def load_project(self, project: ProjectConfig) -> None:
        self._project = project
        self._empty.set_visible(False)
        self._content.set_visible(True)

        self._clear_all()

        for pc in project.processes:
            proc = ManagedProcess(pc.name, pc.command, project.directory)
            proc.on_status_change = self._make_crash_handler(proc, project.name)
            self._processes[pc.name] = proc
            row = ProcessRow(proc, on_select=self._log_pane.set_process)
            self._proc_list.append(row)
            self._process_rows.append(row)
            if pc.auto_start:
                GLib.idle_add(proc.start)

        for cc in project.commands:
            row = CommandRow(cc, project.directory, on_output=self._on_command_output)
            self._cmd_list.append(row)
            self._command_rows.append(row)

        self._refresh_docker()

    def stop_all(self) -> None:
        for proc in self._processes.values():
            if proc.is_running:
                proc.stop()

    # ── private ──────────────────────────────────────────────────────────────

    def _clear_all(self) -> None:
        self.stop_all()
        for row in self._process_rows:
            self._proc_list.remove(row)
        for row in self._docker_row_list:
            self._docker_list.remove(row)
        for row in self._command_rows:
            self._cmd_list.remove(row)
        self._process_rows.clear()
        self._docker_row_list.clear()
        self._command_rows.clear()
        self._processes.clear()
        self._docker_rows.clear()
        self._log_pane.set_process(None)

    def _make_crash_handler(self, proc: ManagedProcess, project_name: str):
        def handler(status: str) -> None:
            if status == ProcessStatus.CRASHED:
                notifications.process_crashed(proc.name, project_name)
        return handler

    def _on_command_output(self, text: str, label: str) -> None:
        self._log_pane.append_text(text, f"Command — {label}")

    def _refresh_docker(self) -> None:
        if not self._docker.is_available:
            return

        def fetch() -> None:
            containers = self._docker.get_containers()
            GLib.idle_add(self._on_containers_updated, containers)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_containers_updated(self, containers: list[dict]) -> None:
        seen: set[str] = set()
        for c in containers:
            name = c["name"]
            seen.add(name)
            if name in self._docker_rows:
                self._docker_rows[name].update(c)
            else:
                row = DockerRow(c, self._docker, on_refresh=self._refresh_docker)
                self._docker_rows[name] = row
                self._docker_list.append(row)
                self._docker_row_list.append(row)
        gone = [n for n in self._docker_rows if n not in seen]
        for name in gone:
            row = self._docker_rows.pop(name)
            self._docker_list.remove(row)
            if row in self._docker_row_list:
                self._docker_row_list.remove(row)
