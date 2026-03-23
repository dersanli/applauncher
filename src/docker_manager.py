from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Callable, Optional

from gi.repository import GLib

try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


def _active_context_name() -> str:
    try:
        config_path = os.path.expanduser("~/.docker/config.json")
        with open(config_path) as f:
            return json.load(f).get("currentContext", "default")
    except Exception:
        return "default"


def _active_docker_socket() -> str | None:
    """Return the socket URL for the active Docker context, or None to use default."""
    try:
        context_name = _active_context_name()
        if context_name == "default":
            return None
        # Context metadata lives at ~/.docker/contexts/meta/<sha256(name)>/meta.json
        name_hash = hashlib.sha256(context_name.encode()).hexdigest()
        meta_path = os.path.expanduser(
            f"~/.docker/contexts/meta/{name_hash}/meta.json"
        )
        with open(meta_path) as f:
            meta = json.load(f)
        return meta["Endpoints"]["docker"]["Host"]
    except Exception:
        return None


class DockerManager:
    def __init__(self) -> None:
        self._client = None
        self._available = False
        self._poll_id: Optional[int] = None

        self.on_containers_updated: Optional[Callable[[list[dict]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def connect(self) -> bool:
        if not DOCKER_AVAILABLE:
            return False
        try:
            socket_url = _active_docker_socket()
            if socket_url:
                self._client = docker.DockerClient(base_url=socket_url)
            else:
                self._client = docker.from_env()
            self._client.ping()
            self._available = True
            return True
        except Exception:
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_desktop_context(self) -> bool:
        return _active_context_name() == "desktop-linux"

    def get_containers(self) -> list[dict]:
        if not self._available or not self._client:
            return []
        try:
            containers = self._client.containers.list(all=True)
            result = []
            for c in containers:
                tags = c.image.tags
                image = tags[0] if tags else c.image.short_id
                result.append(
                    {
                        "id": c.short_id,
                        "name": c.name,
                        "status": c.status,
                        "image": image,
                    }
                )
            return result
        except Exception:
            return []

    def start_container(self, name: str, callback: Optional[Callable] = None) -> None:
        self._run_op(name, "start", callback)

    def stop_container(self, name: str, callback: Optional[Callable] = None) -> None:
        self._run_op(name, "stop", callback)

    def restart_container(self, name: str, callback: Optional[Callable] = None) -> None:
        self._run_op(name, "restart", callback)

    def start_polling(self, interval_ms: int = 3000) -> None:
        self._poll_id = GLib.timeout_add(interval_ms, self._poll)

    def stop_polling(self) -> None:
        if self._poll_id is not None:
            GLib.source_remove(self._poll_id)
            self._poll_id = None

    # ── private ──────────────────────────────────────────────────────────────

    def _run_op(self, name: str, op: str, callback: Optional[Callable]) -> None:
        def _run() -> None:
            try:
                container = self._client.containers.get(name)
                getattr(container, op)()
                if callback:
                    GLib.idle_add(callback)
            except Exception as exc:
                if self.on_error:
                    GLib.idle_add(self.on_error, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _poll(self) -> bool:
        def fetch() -> None:
            containers = self.get_containers()
            if self.on_containers_updated:
                GLib.idle_add(self.on_containers_updated, containers)

        threading.Thread(target=fetch, daemon=True).start()
        return GLib.SOURCE_CONTINUE
