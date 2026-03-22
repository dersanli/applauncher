from __future__ import annotations

import os
import tomllib
import tomli_w
from dataclasses import dataclass, field
from typing import Optional

CONFIG_DIR = os.path.expanduser("~/.config/devlauncher")
CONFIG_FILE = os.path.join(CONFIG_DIR, "projects.toml")


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


def load_config() -> list[ProjectConfig]:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)
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
    data = {
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
    }
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)
