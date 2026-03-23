from __future__ import annotations

import sys
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk, Gio

from .tray import TrayIcon
from .window import DevLauncherWindow

# Register bundled icons so the app icon works without installation
_ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "icons")

def _register_icons() -> None:
    display = Gdk.Display.get_default()
    if display:
        Gtk.IconTheme.get_for_display(display).add_search_path(
            os.path.abspath(_ICONS_DIR)
        )


class DevLauncherApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="io.github.dersanli.DevLauncher",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._tray: TrayIcon | None = None
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app) -> None:
        _register_icons()
        win = self.get_active_window()
        if not win:
            win = DevLauncherWindow(application=self)
            win.set_icon_name("io.github.dersanli.DevLauncher")
            self.hold()  # keep app alive when window is hidden
            self._tray = TrayIcon(app=self, window=win)
        win.present()


def main() -> int:
    app = DevLauncherApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
