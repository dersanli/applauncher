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
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_size_request(220, -1)
        self._on_project_selected = on_project_selected
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

        # ── project list ─────────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.connect("row-selected", self._on_row_selected)
        scroll.set_child(self._list)

        self.append(header)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.append(scroll)

    # ── public API ───────────────────────────────────────────────────────────

    def load_projects(self, projects: list[ProjectConfig]) -> None:
        self._projects = projects
        # Clear existing rows
        while (row := self._list.get_row_at_index(0)) is not None:
            self._list.remove(row)
        for project in projects:
            self._list.append(self._make_row(project))
        # Auto-select first project — call directly since select_row() doesn't
        # reliably emit row-selected before the window is realized
        if projects:
            first = self._list.get_row_at_index(0)
            self._list.select_row(first)
            if self._on_project_selected:
                self._on_project_selected(projects[0])

    def select_project(self, project: ProjectConfig) -> None:
        for i, p in enumerate(self._projects):
            if p is project:
                row = self._list.get_row_at_index(i)
                if row:
                    self._list.select_row(row)
                break

    # ── private ──────────────────────────────────────────────────────────────

    def _make_row(self, project: ProjectConfig) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=project.name)
        label.set_halign(Gtk.Align.START)
        label.set_margin_start(12)
        label.set_margin_end(12)
        label.set_margin_top(10)
        label.set_margin_bottom(10)
        row.set_child(label)
        return row

    def _on_row_selected(self, _list, row: Optional[Gtk.ListBoxRow]) -> None:
        if row is None or not self._on_project_selected:
            return
        index = row.get_index()
        if 0 <= index < len(self._projects):
            self._on_project_selected(self._projects[index])
