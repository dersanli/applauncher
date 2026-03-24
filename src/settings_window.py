from __future__ import annotations

import os
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gio, Gtk

from .config import AppSettings, CommandConfig, ProcessConfig, ProjectConfig, save_app_settings


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(
        self,
        app_settings: AppSettings,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.set_title("Settings")
        self.set_default_size(600, 400)
        self.set_search_enabled(False)

        self._app_settings = app_settings

        self._page = Adw.PreferencesPage()
        self.add(self._page)

        # ── general group ────────────────────────────────────────────────────
        general_group = Adw.PreferencesGroup()
        general_group.set_title("General")
        self._page.add(general_group)

        tray_row = Adw.SwitchRow()
        tray_row.set_title("Minimize to tray")
        tray_row.set_subtitle("Closing the window hides it to the system tray")
        tray_row.set_active(app_settings.minimize_to_tray)
        tray_row.connect(
            "notify::active",
            lambda r, _: setattr(self._app_settings, "minimize_to_tray", r.get_active()),
        )
        general_group.add(tray_row)

        self.connect("close-request", self._on_close)

    def _on_close(self, _win) -> bool:
        save_app_settings(self._app_settings)
        return False


# ── Project editor window ─────────────────────────────────────────────────────

class ProjectEditor(Adw.Window):
    def __init__(
        self,
        project: ProjectConfig,
        title: str = "Edit Project",
        on_confirm: Optional[Callable[[ProjectConfig], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._project = project
        self._on_confirm = on_confirm
        self._confirmed = False
        self.set_title(title)
        self.set_default_size(600, 650)
        self.set_modal(True)

        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Done")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_done)
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

        browse_btn = Gtk.Button(icon_name="folder-open-symbolic")
        browse_btn.add_css_class("flat")
        browse_btn.set_tooltip_text("Choose directory")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.connect("clicked", self._on_browse_directory)
        self._dir_row.add_suffix(browse_btn)

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

    def _on_browse_directory(self, _btn) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Project Directory")
        initial = os.path.expanduser(self._project.directory)
        if os.path.isdir(initial):
            dialog.set_initial_folder(Gio.File.new_for_path(initial))
        dialog.select_folder(self, None, self._on_directory_chosen)

    def _on_directory_chosen(self, dialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if folder:
            path = folder.get_path()
            self._project.directory = path
            self._dir_row.set_text(path)

    def _on_done(self, _btn) -> None:
        self._confirmed = True
        if self._on_confirm:
            self._on_confirm(self._project)
        self.close()

    # ── process rows ─────────────────────────────────────────────────────────

    def _on_add_process(self, _btn) -> None:
        pc = ProcessConfig(name="New Process", command="")
        self._project.processes.append(pc)
        self._add_process_row(pc)

    def _add_process_row(self, pc: ProcessConfig) -> None:
        expander = Adw.ExpanderRow()
        expander.set_title(pc.name)
        expander.set_subtitle(GLib.markup_escape_text(pc.command))

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
            expander.set_subtitle(GLib.markup_escape_text(pc.command))

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
        expander.set_subtitle(GLib.markup_escape_text(cc.command))

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
            expander.set_subtitle(GLib.markup_escape_text(cc.command))

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
