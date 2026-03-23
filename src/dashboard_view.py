from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Pango

from .config import ProjectConfig


class _ProjectCard(Gtk.Button):
    def __init__(
        self,
        project: ProjectConfig,
        on_click: Callable[[ProjectConfig], None],
    ) -> None:
        super().__init__()
        self.add_css_class("card")
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_start=18,
            margin_end=18,
            margin_top=18,
            margin_bottom=18,
        )

        # ── header row: icon + name ───────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.set_valign(Gtk.Align.CENTER)
        header.append(icon)

        name = Gtk.Label(label=project.name)
        name.add_css_class("title-3")
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_hexpand(True)
        header.append(name)

        box.append(header)

        # ── directory ─────────────────────────────────────────────────────────
        dir_label = Gtk.Label(label=project.directory)
        dir_label.add_css_class("caption")
        dir_label.add_css_class("dim-label")
        dir_label.set_halign(Gtk.Align.START)
        dir_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        dir_label.set_max_width_chars(48)
        box.append(dir_label)

        # ── stats ─────────────────────────────────────────────────────────────
        n_proc = len(project.processes)
        n_cmd = len(project.commands)
        parts = []
        if n_proc:
            parts.append(f"{n_proc} process{'es' if n_proc != 1 else ''}")
        if n_cmd:
            parts.append(f"{n_cmd} command{'s' if n_cmd != 1 else ''}")
        if not parts:
            parts.append("No processes or commands")

        stats = Gtk.Label(label=" · ".join(parts))
        stats.add_css_class("caption")
        stats.set_halign(Gtk.Align.START)
        box.append(stats)

        self.set_child(box)
        self.connect("clicked", lambda _: on_click(project))


class DashboardView(Gtk.Box):
    def __init__(
        self,
        on_project_selected: Callable[[ProjectConfig], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_project_selected = on_project_selected

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(960)

        inner = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=20,
            margin_start=24,
            margin_end=24,
            margin_top=32,
            margin_bottom=32,
        )

        title = Gtk.Label(label="Projects")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        inner.append(title)

        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_homogeneous(True)
        self._flow.set_column_spacing(12)
        self._flow.set_row_spacing(12)
        self._flow.set_min_children_per_line(1)
        self._flow.set_max_children_per_line(3)
        inner.append(self._flow)

        self._empty = Adw.StatusPage()
        self._empty.set_title("No Projects Yet")
        self._empty.set_description("Add a project from the sidebar to get started")
        self._empty.set_icon_name("folder-symbolic")
        self._empty.set_vexpand(True)
        self._empty.set_visible(False)
        inner.append(self._empty)

        clamp.set_child(inner)
        scroll.set_child(clamp)
        self.append(scroll)

    def load_projects(self, projects: list[ProjectConfig]) -> None:
        while (child := self._flow.get_child_at_index(0)) is not None:
            self._flow.remove(child)

        if projects:
            self._flow.set_visible(True)
            self._empty.set_visible(False)
            for project in projects:
                card = _ProjectCard(project, self._on_project_selected)
                self._flow.append(card)
        else:
            self._flow.set_visible(False)
            self._empty.set_visible(True)
