from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GObject, Gtk

from .config import ProjectConfig, load_config, save_config
from .docker_manager import DockerManager
from .project_view import ProjectView
from .settings_window import SettingsWindow
from .sidebar import Sidebar


class DevLauncherWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("DevLauncher")
        self.set_default_size(1280, 760)

        self._projects: list[ProjectConfig] = []

        # ── Docker ───────────────────────────────────────────────────────────
        self._docker = DockerManager()
        docker_ok = self._docker.connect()

        # ── Main layout ──────────────────────────────────────────────────────
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # Header bar
        header = Adw.HeaderBar()

        self._toggle_btn = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self._toggle_btn.set_tooltip_text("Toggle sidebar")
        self._toggle_btn.set_active(True)
        header.pack_start(self._toggle_btn)

        title = Adw.WindowTitle(title="DevLauncher", subtitle="")
        header.set_title_widget(title)

        settings_btn = Gtk.Button(icon_name="preferences-system-symbolic")
        settings_btn.set_tooltip_text("Settings")
        settings_btn.connect("clicked", self._on_settings)
        header.pack_end(settings_btn)

        toolbar_view.add_top_bar(header)

        # Split view
        self._split = Adw.OverlaySplitView()
        self._split.set_min_sidebar_width(200)
        self._split.set_max_sidebar_width(280)
        toolbar_view.set_content(self._split)

        # Bind sidebar toggle button
        self._toggle_btn.bind_property(
            "active",
            self._split,
            "show-sidebar",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        # Sidebar
        self._sidebar = Sidebar(
            on_project_selected=self._on_project_selected,
            on_add_project=self._on_add_project,
        )
        self._split.set_sidebar(self._sidebar)

        # Project view
        self._project_view = ProjectView(self._docker)
        self._split.set_content(self._project_view)

        # Docker subtitle
        if docker_ok:
            title.set_subtitle("Docker connected")
            self._docker.start_polling(3000)
        else:
            title.set_subtitle("Docker unavailable")

        # Load projects
        self._load_projects()

    # ── private ──────────────────────────────────────────────────────────────

    def _load_projects(self) -> None:
        self._projects = load_config()
        self._sidebar.load_projects(self._projects)

    def _on_project_selected(self, project: ProjectConfig) -> None:
        self._project_view.load_project(project)

    def _on_add_project(self) -> None:
        self._on_settings(None)

    def _on_settings(self, _btn) -> None:
        win = SettingsWindow(
            projects=self._projects,
            on_saved=self._on_settings_saved,
            transient_for=self,
        )
        win.present()

    def _on_settings_saved(self, projects: list[ProjectConfig]) -> None:
        self._projects = projects
        self._sidebar.load_projects(self._projects)
