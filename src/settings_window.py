from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from .config import CommandConfig, ProcessConfig, ProjectConfig, save_config


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(
        self,
        projects: list[ProjectConfig],
        on_saved: Optional[Callable[[list[ProjectConfig]], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.set_title("Settings")
        self.set_default_size(700, 600)
        self.set_search_enabled(False)

        self._projects = [self._copy_project(p) for p in projects]
        self._on_saved = on_saved

        self._page = Adw.PreferencesPage()
        self.add(self._page)

        # ── projects group ───────────────────────────────────────────────────
        self._group = Adw.PreferencesGroup()
        self._group.set_title("Projects")

        add_btn = Gtk.Button(label="Add Project")
        add_btn.add_css_class("flat")
        add_btn.connect("clicked", self._on_add_project)
        self._group.set_header_suffix(add_btn)

        self._page.add(self._group)
        self._project_rows: list[Adw.ActionRow] = []
        self._rebuild_project_list()

        self.connect("close-request", self._on_close)

    # ── project list ─────────────────────────────────────────────────────────

    def _rebuild_project_list(self) -> None:
        for row in self._project_rows:
            self._group.remove(row)
        self._project_rows.clear()

        for project in self._projects:
            row = Adw.ActionRow()
            row.set_title(project.name)
            row.set_subtitle(project.directory)
            row.set_activatable(True)

            edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
            edit_btn.add_css_class("flat")
            edit_btn.set_valign(Gtk.Align.CENTER)
            edit_btn.set_tooltip_text("Edit project")
            edit_btn.connect("clicked", lambda _, p=project: self._open_editor(p))
            row.add_suffix(edit_btn)

            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("destructive-action")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text("Delete project")
            del_btn.connect("clicked", lambda _, p=project: self._delete_project(p))
            row.add_suffix(del_btn)

            self._group.add(row)
            self._project_rows.append(row)

    def _on_add_project(self, _btn) -> None:
        new_project = ProjectConfig(name="New Project", directory="~")
        self._projects.append(new_project)
        self._rebuild_project_list()
        self._open_editor(new_project)

    def _delete_project(self, project: ProjectConfig) -> None:
        self._projects.remove(project)
        self._rebuild_project_list()

    def _open_editor(self, project: ProjectConfig) -> None:
        editor = ProjectEditor(project, transient_for=self)
        editor.present()

    def _on_close(self, _win) -> bool:
        save_config(self._projects)
        if self._on_saved:
            self._on_saved(self._projects)
        return False

    @staticmethod
    def _copy_project(p: ProjectConfig) -> ProjectConfig:
        return ProjectConfig(
            name=p.name,
            directory=p.directory,
            processes=[ProcessConfig(pc.name, pc.command, pc.auto_start) for pc in p.processes],
            commands=[CommandConfig(cc.name, cc.command) for cc in p.commands],
        )


# ── Project editor window ─────────────────────────────────────────────────────

class ProjectEditor(Adw.Window):
    def __init__(self, project: ProjectConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self._project = project
        self.set_title("Edit Project")
        self.set_default_size(600, 650)
        self.set_modal(True)

        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()
        save_btn = Gtk.Button(label="Done")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self.close())
        header.pack_end(save_btn)
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar.set_content(scroll)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(560)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )
        clamp.set_child(box)
        scroll.set_child(clamp)

        # ── General ──────────────────────────────────────────────────────────
        general = Adw.PreferencesGroup()
        general.set_title("General")
        box.append(general)

        self._name_row = Adw.EntryRow()
        self._name_row.set_title("Project name")
        self._name_row.set_text(project.name)
        self._name_row.connect("changed", lambda r: setattr(project, "name", r.get_text()))
        general.add(self._name_row)

        self._dir_row = Adw.EntryRow()
        self._dir_row.set_title("Directory")
        self._dir_row.set_text(project.directory)
        self._dir_row.connect("changed", lambda r: setattr(project, "directory", r.get_text()))
        general.add(self._dir_row)

        # ── Processes ────────────────────────────────────────────────────────
        self._proc_group = Adw.PreferencesGroup()
        self._proc_group.set_title("Processes")
        add_proc = Gtk.Button(label="Add")
        add_proc.add_css_class("flat")
        add_proc.connect("clicked", self._on_add_process)
        self._proc_group.set_header_suffix(add_proc)
        box.append(self._proc_group)

        self._proc_rows: list[Adw.ExpanderRow] = []
        for pc in project.processes:
            self._add_process_row(pc)

        # ── Commands ─────────────────────────────────────────────────────────
        self._cmd_group = Adw.PreferencesGroup()
        self._cmd_group.set_title("Commands")
        add_cmd = Gtk.Button(label="Add")
        add_cmd.add_css_class("flat")
        add_cmd.connect("clicked", self._on_add_command)
        self._cmd_group.set_header_suffix(add_cmd)
        box.append(self._cmd_group)

        self._cmd_rows: list[Adw.ExpanderRow] = []
        for cc in project.commands:
            self._add_command_row(cc)

    # ── process rows ─────────────────────────────────────────────────────────

    def _on_add_process(self, _btn) -> None:
        pc = ProcessConfig(name="New Process", command="")
        self._project.processes.append(pc)
        self._add_process_row(pc)

    def _add_process_row(self, pc: ProcessConfig) -> None:
        expander = Adw.ExpanderRow()
        expander.set_title(pc.name)
        expander.set_subtitle(pc.command)

        name_row = Adw.EntryRow()
        name_row.set_title("Name")
        name_row.set_text(pc.name)

        def on_name_changed(r):
            pc.name = r.get_text()
            expander.set_title(pc.name)

        name_row.connect("changed", on_name_changed)
        expander.add_row(name_row)

        cmd_row = Adw.EntryRow()
        cmd_row.set_title("Command")
        cmd_row.set_text(pc.command)

        def on_cmd_changed(r):
            pc.command = r.get_text()
            expander.set_subtitle(pc.command)

        cmd_row.connect("changed", on_cmd_changed)
        expander.add_row(cmd_row)

        auto_row = Adw.SwitchRow()
        auto_row.set_title("Auto-start")
        auto_row.set_active(pc.auto_start)
        auto_row.connect("notify::active", lambda r, _: setattr(pc, "auto_start", r.get_active()))
        expander.add_row(auto_row)

        del_row = Adw.ActionRow()
        del_row.set_title("Delete this process")
        del_btn = Gtk.Button(label="Delete")
        del_btn.add_css_class("destructive-action")
        del_btn.set_valign(Gtk.Align.CENTER)

        def on_delete(_btn):
            self._project.processes.remove(pc)
            self._proc_group.remove(expander)
            self._proc_rows.remove(expander)

        del_btn.connect("clicked", on_delete)
        del_row.add_suffix(del_btn)
        expander.add_row(del_row)

        self._proc_group.add(expander)
        self._proc_rows.append(expander)

    # ── command rows ─────────────────────────────────────────────────────────

    def _on_add_command(self, _btn) -> None:
        cc = CommandConfig(name="New Command", command="")
        self._project.commands.append(cc)
        self._add_command_row(cc)

    def _add_command_row(self, cc: CommandConfig) -> None:
        expander = Adw.ExpanderRow()
        expander.set_title(cc.name)
        expander.set_subtitle(cc.command)

        name_row = Adw.EntryRow()
        name_row.set_title("Name")
        name_row.set_text(cc.name)

        def on_name_changed(r):
            cc.name = r.get_text()
            expander.set_title(cc.name)

        name_row.connect("changed", on_name_changed)
        expander.add_row(name_row)

        cmd_row = Adw.EntryRow()
        cmd_row.set_title("Command")
        cmd_row.set_text(cc.command)

        def on_cmd_changed(r):
            cc.command = r.get_text()
            expander.set_subtitle(cc.command)

        cmd_row.connect("changed", on_cmd_changed)
        expander.add_row(cmd_row)

        del_row = Adw.ActionRow()
        del_row.set_title("Delete this command")
        del_btn = Gtk.Button(label="Delete")
        del_btn.add_css_class("destructive-action")
        del_btn.set_valign(Gtk.Align.CENTER)

        def on_delete(_btn):
            self._project.commands.remove(cc)
            self._cmd_group.remove(expander)
            self._cmd_rows.remove(expander)

        del_btn.connect("clicked", on_delete)
        del_row.add_suffix(del_btn)
        expander.add_row(del_row)

        self._cmd_group.add(expander)
        self._cmd_rows.append(expander)
