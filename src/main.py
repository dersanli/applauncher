from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from .tray import TrayIcon
from .window import DevLauncherWindow


class DevLauncherApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="io.github.dersanli.DevLauncher",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._tray: TrayIcon | None = None
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app) -> None:
        win = self.get_active_window()
        if not win:
            win = DevLauncherWindow(application=self)
            self.hold()  # keep app alive when window is hidden
            self._tray = TrayIcon(app=self, window=win)
        win.present()


def main() -> int:
    app = DevLauncherApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
