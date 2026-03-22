# DevLauncher — Developer Guide

This document covers everything you need to know to set up your environment, understand the project structure, and start contributing to DevLauncher.

---

## Prerequisites

Make sure you have the following installed:

- **Python 3.12+**
- **GTK4** and **libadwaita** development libraries
- **PyGObject** (Python GObject bindings)
- **Flatpak** + **GNOME Builder** or **GNOME Workbench** (for UI prototyping)
- **Docker** (running locally, for Docker integration features)

### Install system dependencies (Ubuntu/Debian)

```bash
sudo apt install \
  python3-dev \
  python3-venv \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  gir1.2-appindicator3-0.1 \
  libgirepository1.0-dev \
  gcc \
  libcairo2-dev \
  pkg-config
```

---

## Project Setup

### 1. Clone the repo

```bash
git clone git@github.com-dersanli:dersanli/applauncher.git
cd applauncher
```

> Note: We use the SSH host alias `github.com-dersanli` to ensure the correct SSH key is used. See `~/.ssh/config`.

### 2. Create and activate the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python src/main.py
```

---

## Understanding GNOME Development

If you're new to GNOME app development, here's a quick mental model before diving into the code.

### GTK4

GTK4 is the UI toolkit used by GNOME. You build interfaces out of **widgets** (buttons, labels, boxes, etc.) arranged in a tree. Every widget has a parent, and the top-level parent is the `Window`.

In Python, GTK4 is accessed via `PyGObject`:

```python
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

app = Gtk.Application(application_id='io.github.dersanli.DevLauncher')
```

### libadwaita

libadwaita (`Adw`) sits on top of GTK4 and provides GNOME-style widgets that automatically follow the system theme (light/dark), spacing conventions, and HIG (Human Interface Guidelines). Always prefer `Adw` widgets over plain `Gtk` ones where available.

```python
gi.require_version('Adw', '1')
from gi.repository import Adw

class MyApp(Adw.Application):
    ...
```

### Key widget concepts

| Concept | Description |
|---|---|
| `Adw.ApplicationWindow` | Main app window with GNOME chrome |
| `Adw.NavigationSplitView` | Sidebar + content layout (used for our project sidebar) |
| `Adw.ToolbarView` | Window layout with header bar + content |
| `Adw.HeaderBar` | The title bar at the top of the window |
| `Gtk.Box` | Stack widgets horizontally or vertically |
| `Gtk.ScrolledWindow` | Make any widget scrollable |
| `Gtk.ListBox` | A list of rows — used for process/container lists |
| `Adw.ActionRow` | A standard list row with title, subtitle, and suffix widgets |

### The GLib event loop

GTK runs on its own event loop (GLib's main loop). You must **never block this loop** with long-running synchronous code — doing so freezes the UI.

For async work (spawning processes, reading logs, polling Docker), use:
- `GLib.idle_add()` — run something on the next idle cycle
- `GLib.timeout_add()` — run something on a timer
- Python `asyncio` bridged to GLib via `gbulb` or `asyncio` with a custom event loop

### UI files vs. code

GTK supports defining UIs in XML `.ui` files (Blueprint syntax in GNOME Workbench). We use **GNOME Workbench** to prototype and preview UI components, then reference them in Python via `Gtk.Template`.

---

## Project Structure

```
applauncher/
├── src/
│   ├── main.py              # Entry point — creates and runs the Adw.Application
│   ├── window.py            # Main application window
│   ├── sidebar.py           # Project sidebar widget
│   ├── project_view.py      # Main content area (processes + docker + commands)
│   ├── log_pane.py          # Live log viewer widget
│   ├── process_row.py       # Individual process list row
│   ├── docker_row.py        # Individual container list row
│   ├── command_row.py       # Individual command row
│   ├── settings_window.py   # Settings / admin page
│   ├── process_manager.py   # Subprocess lifecycle management
│   ├── docker_manager.py    # Docker SDK wrapper
│   └── config.py            # TOML config read/write (~/.config/devlauncher/)
├── data/
│   ├── ui/                  # GTK UI blueprint files (.blp / .ui)
│   └── icons/               # App icons
├── tests/
├── requirements.txt
├── README.md
├── README.DEV.md
└── io.github.dersanli.DevLauncher.json   # Flatpak manifest (later)
```

---

## Config Format

Projects are stored in `~/.config/devlauncher/projects.toml`:

```toml
[[projects]]
name = "my-saas-app"
directory = "/home/devrim/dev/my-saas"
auto_start = ["pnpm dev", "fastapi"]

  [[projects.processes]]
  name = "pnpm dev"
  command = "pnpm dev"
  auto_start = true

  [[projects.processes]]
  name = "fastapi"
  command = "uvicorn main:app --reload"
  auto_start = true

  [[projects.processes]]
  name = "stripe listen"
  command = "stripe listen --forward-to localhost:8000/webhooks"
  auto_start = false

  [[projects.commands]]
  name = "curl health"
  command = "curl -s http://localhost:8000/health | jq"

  [[projects.commands]]
  name = "run migrations"
  command = "alembic upgrade head"
```

Docker containers are discovered automatically from the running Docker daemon — no config needed.

---

## Using GNOME Workbench

GNOME Workbench is a live preview tool for GTK4/libadwaita UIs. Use it to:

1. Prototype individual widgets in Blueprint (`.blp`) syntax
2. See live previews without running the full app
3. Experiment with `Adw` components and layouts

Install via Flatpak:

```bash
flatpak install flathub re.sonny.Workbench
```

---

## Running Tests

```bash
pytest tests/
```

---

## Useful Resources

- [GTK4 Python Tutorial](https://python-gtk-3-tutorial.readthedocs.io/) — starts with GTK3 but concepts carry over
- [libadwaita Docs](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/)
- [PyGObject Docs](https://pygobject.gnome.org/)
- [GNOME HIG](https://developer.gnome.org/hig/) — design guidelines to keep the app feeling native
- [Blueprint UI Language](https://jwestman.pages.gitlab.gnome.org/blueprint-compiler/) — cleaner syntax for `.ui` files
- [Docker Python SDK](https://docker-py.readthedocs.io/)
