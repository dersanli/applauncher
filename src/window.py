from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk

from .config import ProjectConfig, load_config, save_config
from .docker_manager import DockerManager
from .docker_view import DockerView
from .project_view import ProjectView
from .settings_window import SettingsWindow
from .sidebar import Sidebar


class DevLauncherWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("DevLauncher")
        self.set_default_size(1280, 760)

        self._projects: list[ProjectConfig] = []
        self._quitting = False

        # ── Docker ───────────────────────────────────────────────────────────
        self._docker = DockerManager()

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
            on_docker_selected=self._on_docker_selected,
        )
        self._split.set_sidebar(self._sidebar)

        # Content stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._project_view = ProjectView()
        self._docker_view = DockerView(
            self._docker, on_connected=self._on_docker_reconnected
        )

        self._stack.add_named(self._project_view, "project")
        self._stack.add_named(self._docker_view, "docker")
        self._split.set_content(self._stack)

        self._title = title
        self._title.set_subtitle("Connecting to Docker…")

        # Connect to Docker in background to avoid blocking the UI
        import threading
        threading.Thread(target=self._connect_docker, daemon=True).start()

        self._load_projects()

    # ── private ──────────────────────────────────────────────────────────────

    def _load_projects(self) -> None:
        self._projects = load_config()
        self._sidebar.load_projects(self._projects)

    def _on_project_selected(self, project: ProjectConfig) -> None:
        self._stack.set_visible_child_name("project")
        self._project_view.load_project(project)

    def _on_docker_selected(self) -> None:
        self._stack.set_visible_child_name("docker")

    def _on_add_project(self) -> None:
        self._on_settings(None)

    def _on_settings(self, _btn) -> None:
        win = SettingsWindow(
            projects=self._projects,
            on_saved=self._on_settings_saved,
            transient_for=self,
        )
        win.present()

    def do_close_request(self) -> bool:
        if self._quitting:
            return False  # allow normal destroy → app quits
        self.hide()
        return True  # prevent destroy; keep app alive in tray

    def _connect_docker(self) -> None:
        ok = self._docker.connect()
        GLib.idle_add(self._on_docker_connected, ok)

    def _on_docker_connected(self, ok: bool) -> bool:
        if ok:
            self._title.set_subtitle("Docker connected")
            self._docker.start_polling(3000)
            self._docker_view.notify_docker_connected()
        elif self._docker.is_desktop_context:
            self._title.set_subtitle("Docker Desktop not running")
            self._docker_view.notify_docker_unavailable()
        else:
            self._title.set_subtitle("Docker unavailable")
        return False

    def _on_docker_reconnected(self) -> None:
        self._title.set_subtitle("Docker connected")
        self._docker.start_polling(3000)

    def _on_settings_saved(self, projects: list[ProjectConfig]) -> None:
        self._projects = projects
        self._sidebar.load_projects(self._projects)
