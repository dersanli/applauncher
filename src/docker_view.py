from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from .docker_manager import DockerManager
from .docker_row import DockerRow

_DESKTOP_BINARY = "/opt/docker-desktop/bin/docker-desktop"


def _is_docker_desktop_installed() -> bool:
    """Check via systemctl service file — more reliable than checking a binary path."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "list-unit-files", "docker-desktop.service"],
            capture_output=True,
            text=True,
        )
        return "docker-desktop.service" in result.stdout
    except Exception:
        return os.path.exists(_DESKTOP_BINARY)


def _is_docker_desktop_running() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "docker-desktop"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def _find_desktop_binary() -> str | None:
    """Try to locate the Docker Desktop binary."""
    if os.path.exists(_DESKTOP_BINARY):
        return _DESKTOP_BINARY
    # Parse the systemd service file for the ExecStart binary
    service_paths = [
        os.path.expanduser("~/.config/systemd/user/docker-desktop.service"),
        "/usr/lib/systemd/user/docker-desktop.service",
        os.path.expanduser("~/.local/share/systemd/user/docker-desktop.service"),
    ]
    for path in service_paths:
        try:
            with open(path) as f:
                for line in f:
                    if line.startswith("ExecStart="):
                        binary = line.split("=", 1)[1].strip().split()[0]
                        if os.path.exists(binary):
                            return binary
        except Exception:
            pass
    try:
        result = subprocess.run(
            ["which", "docker-desktop"], capture_output=True, text=True
        )
        path = result.stdout.strip()
        if path:
            return path
    except Exception:
        pass
    return None


class DockerView(Gtk.Box):
    def __init__(
        self,
        docker: DockerManager,
        on_connected: Optional[Callable] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._docker = docker
        self._on_connected = on_connected
        self._rows: dict[str, DockerRow] = {}
        self._row_list: list[DockerRow] = []

        # ── Docker Desktop banner (shown when DD is installed but not running) ─
        self._desktop_revealer = Gtk.Revealer()
        self._desktop_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._desktop_revealer.set_reveal_child(False)

        banner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        banner_box.set_margin_start(16)
        banner_box.set_margin_end(16)
        banner_box.set_margin_top(10)
        banner_box.set_margin_bottom(10)
        banner_box.add_css_class("toolbar")

        banner_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        banner_icon.add_css_class("warning")
        banner_box.append(banner_icon)

        banner_label = Gtk.Label(label="Docker Desktop is not running")
        banner_label.set_hexpand(True)
        banner_label.set_halign(Gtk.Align.START)
        banner_box.append(banner_label)

        self._minimized_check = Gtk.CheckButton(label="Start minimized")
        self._minimized_check.set_valign(Gtk.Align.CENTER)
        self._minimized_check.set_active(True)
        banner_box.append(self._minimized_check)

        self._start_btn = Gtk.Button(label="Start")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.set_valign(Gtk.Align.CENTER)
        self._start_btn.connect("clicked", self._on_start_clicked)
        banner_box.append(self._start_btn)

        self._desktop_revealer.set_child(banner_box)
        self.append(self._desktop_revealer)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── stack: unavailable / container list ───────────────────────────────
        self._inner_stack = Gtk.Stack()
        self._inner_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._inner_stack.set_vexpand(True)
        self.append(self._inner_stack)

        # ── "no daemon" page ──────────────────────────────────────────────────
        unavailable_page = Adw.StatusPage()
        unavailable_page.set_icon_name("application-x-executable-symbolic")
        unavailable_page.set_title("Docker is not available")
        unavailable_page.set_description("Make sure Docker is installed and running.")
        unavailable_page.set_vexpand(True)
        self._inner_stack.add_named(unavailable_page, "unavailable")

        # ── container list page ───────────────────────────────────────────────
        list_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

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

        label = Gtk.Label(label="Docker Containers")
        label.add_css_class("heading")
        label.set_halign(Gtk.Align.START)
        label.set_margin_bottom(4)
        inner.append(label)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        inner.append(self._list)

        clamp.set_child(inner)
        scroll.set_child(clamp)
        list_page.append(scroll)

        self._inner_stack.add_named(list_page, "containers")
        self._inner_stack.set_visible_child_name("containers")

        self._docker.on_containers_updated = self._on_containers_updated
        self._desktop_installed: bool = False
        self._desktop_poll_id: int | None = None
        self.connect("map", self._on_mapped)
        self.connect("unmap", self._on_unmapped)

        # Check Docker Desktop state on startup
        self._check_desktop_state()

    # ── public API ────────────────────────────────────────────────────────────

    def notify_docker_connected(self) -> None:
        self._inner_stack.set_visible_child_name("containers")
        self._refresh()

    def notify_docker_unavailable(self) -> None:
        self._inner_stack.set_visible_child_name("unavailable")

    def notify_docker_disconnected(self) -> None:
        for name in list(self._rows):
            row = self._rows.pop(name)
            self._list.remove(row)
        self._row_list.clear()

    # ── private ───────────────────────────────────────────────────────────────

    def _check_desktop_state(self) -> None:
        def check():
            installed = _is_docker_desktop_installed()
            running = _is_docker_desktop_running() if installed else False
            GLib.idle_add(self._apply_desktop_state, installed, running)

        threading.Thread(target=check, daemon=True).start()

    def _apply_desktop_state(self, installed: bool, running: bool) -> bool:
        self._desktop_installed = installed
        self._desktop_revealer.set_reveal_child(installed and not running)
        if not running:
            self._start_btn.set_label("Start")
            self._start_btn.set_sensitive(True)
        return False

    def _poll_desktop_state(self) -> bool:
        self._check_desktop_state()
        return GLib.SOURCE_CONTINUE

    def _on_mapped(self, _widget) -> None:
        self._check_desktop_state()
        if self._docker.is_available:
            self._refresh()
        if self._desktop_poll_id is None:
            self._desktop_poll_id = GLib.timeout_add(5000, self._poll_desktop_state)

    def _on_unmapped(self, _widget) -> None:
        if self._desktop_poll_id is not None:
            GLib.source_remove(self._desktop_poll_id)
            self._desktop_poll_id = None

    def _refresh(self) -> None:
        def fetch():
            containers = self._docker.get_containers()
            GLib.idle_add(self._on_containers_updated, containers)

        threading.Thread(target=fetch, daemon=True).start()

    def _set_open_ui_on_startup(self, enabled: bool) -> None:
        path = os.path.expanduser("~/.docker/desktop/settings-store.json")
        try:
            with open(path) as f:
                data = json.load(f)
            data["OpenUIOnStartupDisabled"] = not enabled
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _on_start_clicked(self, _btn) -> None:
        self._start_btn.set_sensitive(False)
        self._start_btn.set_label("Starting…")
        minimized = self._minimized_check.get_active()
        try:
            if minimized:
                self._set_open_ui_on_startup(False)
            subprocess.Popen(
                ["systemctl", "--user", "start", "docker-desktop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            self._start_btn.set_label("Start")
            self._start_btn.set_sensitive(True)
            return
        GLib.timeout_add(6000, self._retry_connect)

    def _retry_connect(self) -> bool:
        def attempt():
            ok = self._docker.connect()
            running = _is_docker_desktop_running()
            GLib.idle_add(self._on_retry_result, ok, running)

        threading.Thread(target=attempt, daemon=True).start()
        return False

    def _on_retry_result(self, ok: bool, running: bool) -> bool:
        self._apply_desktop_state(_is_docker_desktop_installed(), running)
        if running:
            self._set_open_ui_on_startup(True)  # restore default
            self._start_btn.set_label("Start")
            self._start_btn.set_sensitive(True)
        if ok:
            self._inner_stack.set_visible_child_name("containers")
            self._refresh()
            if self._on_connected:
                self._on_connected()
        elif not running:
            GLib.timeout_add(4000, self._retry_connect)
        return False

    def _on_containers_updated(self, containers: list[dict]) -> None:
        seen: set[str] = set()
        for c in containers:
            name = c["name"]
            seen.add(name)
            if name in self._rows:
                self._rows[name].update(c)
            else:
                row = DockerRow(c, self._docker, on_refresh=self._refresh)
                self._rows[name] = row
                self._row_list.append(row)
                self._list.append(row)

        gone = [n for n in self._rows if n not in seen]
        for name in gone:
            row = self._rows.pop(name)
            self._list.remove(row)
            self._row_list.remove(row)
