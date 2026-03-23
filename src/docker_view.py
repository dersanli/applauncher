from __future__ import annotations

import subprocess
import threading
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from .docker_manager import DockerManager
from .docker_row import DockerRow


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

        # ── stack: unavailable / container list ───────────────────────────────
        self._inner_stack = Gtk.Stack()
        self._inner_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._inner_stack.set_vexpand(True)
        self.append(self._inner_stack)

        # ── "not available" page ──────────────────────────────────────────────
        self._unavailable_page = Adw.StatusPage()
        self._unavailable_page.set_icon_name("application-x-executable-symbolic")
        self._unavailable_page.set_title("Docker Desktop is not running")
        self._unavailable_page.set_vexpand(True)

        self._start_btn = Gtk.Button(label="Start Docker Desktop")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.add_css_class("pill")
        self._start_btn.set_halign(Gtk.Align.CENTER)
        self._start_btn.connect("clicked", self._on_start_clicked)
        self._unavailable_page.set_child(self._start_btn)

        self._inner_stack.add_named(self._unavailable_page, "unavailable")

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
        self.connect("map", self._on_mapped)

    # ── public API ────────────────────────────────────────────────────────────

    def notify_docker_connected(self) -> None:
        self._inner_stack.set_visible_child_name("containers")
        self._refresh()

    def notify_docker_unavailable(self) -> None:
        self._inner_stack.set_visible_child_name("unavailable")

    # ── private ───────────────────────────────────────────────────────────────

    def _on_mapped(self, _widget) -> None:
        if self._docker.is_available:
            self._refresh()

    def _refresh(self) -> None:
        def fetch():
            containers = self._docker.get_containers()
            GLib.idle_add(self._on_containers_updated, containers)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_start_clicked(self, _btn) -> None:
        self._start_btn.set_sensitive(False)
        self._start_btn.set_label("Starting…")
        try:
            subprocess.Popen(
                ["systemctl", "--user", "start", "docker-desktop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            self._start_btn.set_label("Start Docker Desktop")
            self._start_btn.set_sensitive(True)
            return
        GLib.timeout_add(6000, self._retry_connect)

    def _retry_connect(self) -> bool:
        def attempt():
            ok = self._docker.connect()
            GLib.idle_add(self._on_retry_result, ok)

        threading.Thread(target=attempt, daemon=True).start()
        return False

    def _on_retry_result(self, ok: bool) -> bool:
        if ok:
            self._inner_stack.set_visible_child_name("containers")
            self._refresh()
            if self._on_connected:
                self._on_connected()
        else:
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
