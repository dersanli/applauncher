from __future__ import annotations

import gi

try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify

    Notify.init("DevLauncher")
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def _notify(title: str, body: str, icon: str = "dialog-information-symbolic") -> None:
    if not _AVAILABLE:
        return
    try:
        n = Notify.Notification.new(title, body, icon)
        n.show()
    except Exception:
        pass


def process_crashed(process_name: str, project_name: str) -> None:
    _notify(
        f"Process crashed: {process_name}",
        f'In project \u201c{project_name}\u201d',
        "dialog-error-symbolic",
    )


def container_stopped(container_name: str) -> None:
    _notify(
        f"Container stopped: {container_name}",
        "Docker container went down unexpectedly",
        "dialog-warning-symbolic",
    )
