from __future__ import annotations

import os
import tomllib
import tomli_w
from dataclasses import dataclass, field
from typing import Optional

CONFIG_DIR = os.path.expanduser("~/.config/devlauncher")
CONFIG_FILE = os.path.join(CONFIG_DIR, "projects.toml")


@dataclass
class AppSettings:
    minimize_to_tray: bool = True
    theme: str = "system"  # "system" | "light" | "dark"
    log_line_numbers: bool = False
    log_word_wrap: bool = True


@dataclass
class ProcessConfig:
    name: str
    command: str
    auto_start: bool = False


@dataclass
class CommandConfig:
    name: str
    command: str


@dataclass
class ProjectConfig:
    name: str
    directory: str
    processes: list[ProcessConfig] = field(default_factory=list)
    commands: list[CommandConfig] = field(default_factory=list)


def _load_raw() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def load_app_settings() -> AppSettings:
    data = _load_raw()
    app = data.get("app", {})
    return AppSettings(
        minimize_to_tray=app.get("minimize_to_tray", True),
        theme=app.get("theme", "system"),
        log_line_numbers=app.get("log_line_numbers", False),
        log_word_wrap=app.get("log_word_wrap", True),
    )


def save_app_settings(settings: AppSettings) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = _load_raw()
    data["app"] = {"minimize_to_tray": settings.minimize_to_tray, "theme": settings.theme, "log_line_numbers": settings.log_line_numbers, "log_word_wrap": settings.log_word_wrap}
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)


def load_config() -> list[ProjectConfig]:
    data = _load_raw()
    projects = []
    for p in data.get("projects", []):
        processes = [
            ProcessConfig(
                name=proc["name"],
                command=proc["command"],
                auto_start=proc.get("auto_start", False),
            )
            for proc in p.get("processes", [])
        ]
        commands = [
            CommandConfig(name=cmd["name"], command=cmd["command"])
            for cmd in p.get("commands", [])
        ]
        projects.append(
            ProjectConfig(
                name=p["name"],
                directory=p.get("directory", os.path.expanduser("~")),
                processes=processes,
                commands=commands,
            )
        )
    return projects


def save_config(projects: list[ProjectConfig]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = _load_raw()
    data.update({
        "projects": [
            {
                "name": p.name,
                "directory": p.directory,
                "processes": [
                    {
                        "name": proc.name,
                        "command": proc.command,
                        "auto_start": proc.auto_start,
                    }
                    for proc in p.processes
                ],
                "commands": [
                    {"name": cmd.name, "command": cmd.command}
                    for cmd in p.commands
                ],
            }
            for p in projects
        ]
    })
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)
