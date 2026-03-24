from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, GObject, Gtk

from .config import AppSettings, ProjectConfig, load_app_settings, load_config, save_config
from .settings_window import ProjectEditor
from .dashboard_view import DashboardView
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
        self._app_settings: AppSettings = load_app_settings()
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

        home_btn = Gtk.Button(icon_name="go-home-symbolic")
        home_btn.set_tooltip_text("Dashboard")
        home_btn.connect("clicked", self._on_home)
        header.pack_start(home_btn)

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
            on_edit_project=self._on_edit_project,
        )
        self._split.set_sidebar(self._sidebar)

        # Content stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._dashboard_view = DashboardView(on_project_selected=self._on_project_selected)
        self._project_view = ProjectView()
        self._docker_view = DockerView(
            self._docker, on_connected=self._on_docker_reconnected
        )

        self._stack.add_named(self._dashboard_view, "dashboard")
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
        self._dashboard_view.load_projects(self._projects)
        self._stack.set_visible_child_name("dashboard")

    def _on_project_selected(self, project: ProjectConfig) -> None:
        self._stack.set_visible_child_name("project")
        self._title.set_title(project.name)
        self._project_view.load_project(project)
        self._sidebar.select_project(project)

    def _on_home(self, _btn) -> None:
        self._stack.set_visible_child_name("dashboard")
        self._title.set_title("DevLauncher")

    def _on_docker_selected(self) -> None:
        self._stack.set_visible_child_name("docker")

    def _on_add_project(self) -> None:
        new_project = ProjectConfig(name="New Project", directory="~")

        def on_confirm(project: ProjectConfig) -> None:
            self._projects.append(project)
            self._reload_projects()

        editor = ProjectEditor(
            new_project,
            title="Add Project",
            on_confirm=on_confirm,
            transient_for=self,
        )
        editor.present()

    def _on_edit_project(self, project: ProjectConfig) -> None:
        editor = ProjectEditor(
            project,
            on_confirm=lambda p: self._reload_projects(edited_project=p),
            on_delete=self._do_delete_project,
            transient_for=self,
        )
        editor.present()

    def _reload_projects(self, edited_project: ProjectConfig | None = None) -> None:
        save_config(self._projects)
        self._sidebar.load_projects(self._projects)
        self._dashboard_view.load_projects(self._projects)
        if edited_project and self._stack.get_visible_child_name() == "project":
            self._title.set_title(edited_project.name)
            self._project_view.load_project(edited_project)

    def _do_delete_project(self, project: ProjectConfig) -> None:
        self._projects.remove(project)
        self._reload_projects()
        self._stack.set_visible_child_name("dashboard")
        self._title.set_title("DevLauncher")

    def _on_settings(self, _btn) -> None:
        win = SettingsWindow(
            app_settings=self._app_settings,
            transient_for=self,
        )
        win.present()

    def request_quit(self) -> None:
        running = self._project_view.get_running_count()
        if running == 0:
            self._do_quit()
            return

        noun = "process" if running == 1 else "processes"
        dialog = Adw.AlertDialog(
            heading="Quit DevLauncher?",
            body=f"{running} {noun} still running. They will be stopped.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("quit", "Quit")
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda d, r: self._do_quit() if r == "quit" else None)
        self.present()
        dialog.present(self)

    def _do_quit(self) -> None:
        self._project_view.stop_all()
        self._quitting = True
        self.get_application().quit()

    def do_close_request(self) -> bool:
        if self._quitting:
            return False  # allow normal destroy → app quits
        if self._app_settings.minimize_to_tray:
            self.hide()
            return True  # prevent destroy; keep app alive in tray
        self.request_quit()
        return True  # always intercept; request_quit handles the rest

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

