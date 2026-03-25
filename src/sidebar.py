from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from .config import ProjectConfig


class Sidebar(Gtk.Box):
    def __init__(
        self,
        on_project_selected: Optional[Callable[[ProjectConfig], None]] = None,
        on_add_project: Optional[Callable] = None,
        on_docker_selected: Optional[Callable] = None,
        on_edit_project: Optional[Callable[[ProjectConfig], None]] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_size_request(220, -1)
        self._on_project_selected = on_project_selected
        self._on_docker_selected = on_docker_selected
        self._on_edit_project = on_edit_project
        self._projects: list[ProjectConfig] = []

        # ── header ───────────────────────────────────────────────────────────
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_title_widget(Gtk.Label(label="Projects"))
        header.add_css_class("flat")

        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.add_css_class("flat")
        add_btn.set_tooltip_text("Add project")
        if on_add_project:
            add_btn.connect("clicked", lambda _: on_add_project())
        header.pack_end(add_btn)

        # ── scrollable project list ───────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.connect("row-selected", self._on_project_row_selected)
        scroll.set_child(self._list)

        # ── pinned Docker entry at the bottom ─────────────────────────────────
        self._bottom_list = Gtk.ListBox()
        self._bottom_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._bottom_list.add_css_class("navigation-sidebar")
        self._bottom_list.connect("row-selected", self._on_docker_row_selected)

        docker_row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.append(Gtk.Image.new_from_icon_name("application-x-executable-symbolic"))
        lbl = Gtk.Label(label="Docker")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        box.append(lbl)
        self._docker_status_dot = Gtk.Label(label="●")
        self._docker_status_dot.set_valign(Gtk.Align.CENTER)
        self._docker_status_dot.add_css_class("dim-label")
        box.append(self._docker_status_dot)
        docker_row.set_child(box)
        self._bottom_list.append(docker_row)

        self.append(header)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.append(scroll)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.append(self._bottom_list)

    # ── public API ───────────────────────────────────────────────────────────

    def set_docker_status(self, connected: bool | None) -> None:
        """Update the Docker status dot. True=connected, False=unavailable, None=connecting."""
        dot = self._docker_status_dot
        dot.remove_css_class("success")
        dot.remove_css_class("error")
        dot.remove_css_class("dim-label")
        if connected is True:
            dot.add_css_class("success")
            dot.set_tooltip_text("Docker connected")
        elif connected is False:
            dot.add_css_class("error")
            dot.set_tooltip_text("Docker is not running")
        else:
            dot.add_css_class("dim-label")
            dot.set_tooltip_text("Connecting to Docker…")

    def load_projects(self, projects: list[ProjectConfig]) -> None:
        self._projects = projects
        while (row := self._list.get_row_at_index(0)) is not None:
            self._list.remove(row)
        for project in projects:
            self._list.append(self._make_project_row(project))

    def select_project(self, project: ProjectConfig) -> None:
        for i, p in enumerate(self._projects):
            if p is project:
                row = self._list.get_row_at_index(i)
                if row:
                    self._list.select_row(row)
                break

    # ── private ──────────────────────────────────────────────────────────────

    def _make_project_row(self, project: ProjectConfig) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._project = project

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_margin_start(12)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        label = Gtk.Label(label=project.name)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_margin_end(4)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        box.append(label)

        if self._on_edit_project:
            edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
            edit_btn.add_css_class("flat")
            edit_btn.set_tooltip_text("Edit project")
            edit_btn.set_valign(Gtk.Align.CENTER)
            edit_btn.connect("clicked", lambda _, p=project: self._on_edit_project(p))
            box.append(edit_btn)

        row.set_child(box)
        return row

    def _on_project_row_selected(self, _list, row: Optional[Gtk.ListBoxRow]) -> None:
        if row is None:
            return
        # Deselect the Docker list
        self._bottom_list.select_row(None)
        project = getattr(row, "_project", None)
        if project and self._on_project_selected:
            self._on_project_selected(project)

    def _on_docker_row_selected(self, _list, row: Optional[Gtk.ListBoxRow]) -> None:
        if row is None:
            return
        # Deselect the project list
        self._list.select_row(None)
        if self._on_docker_selected:
            self._on_docker_selected()
