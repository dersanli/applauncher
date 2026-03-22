# 🚀 DevLauncher

> Your personal developer environment dashboard for GNOME — launch services, manage containers, and run commands from one place.

---

## ✨ What is DevLauncher?

Every developer has a ritual: open the terminal, `pnpm dev`, another tab for `fastapi`, another for `stripe listen`, check Docker... **DevLauncher eliminates that ritual.**

It's a native GNOME application that lets you define your project's entire dev stack once, and control it all from a clean, minimal dashboard — with live logs, Docker management, and one-click commands.

---

## 🎯 Features

- 📁 **Multi-project support** — switch between projects from a collapsible sidebar
- ⚡ **Process management** — start, stop and monitor long-running processes (`pnpm dev`, `fastapi`, `stripe listen`, etc.)
- 🐳 **Docker control** — see all containers, start/stop/restart them without touching the terminal
- 🖥️ **Live logs** — click any running process and watch its stdout/stderr in real time
- 🔧 **One-off commands** — define and run project commands (`curl`, migrations, seed scripts) on demand
- 🔔 **Desktop notifications** — get notified when a process crashes or a container goes down (non-intrusive)
- 🔑 **Global keyboard shortcut** — bring DevLauncher up from anywhere on your desktop
- 🗂️ **System tray icon** — quick status glance without switching windows
- ⚙️ **Settings & auto-start** — configure which services launch automatically when you open a project

---

## 📸 Screenshots

> _Coming soon_

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| UI Framework | GTK4 + libadwaita |
| GNOME Bindings | PyGObject |
| Process Management | asyncio + subprocess |
| Docker | Docker Python SDK |
| Config | TOML (`~/.config/devlauncher/`) |
| Packaging | Flatpak |

---

## 📦 Installation

### Via Flatpak _(coming soon)_

```bash
flatpak install flathub io.github.dersanli.DevLauncher
```

### From source

See [README.DEV.md](README.DEV.md) for full development setup instructions.

---

## 🗺️ Roadmap

- [ ] Core UI — sidebar, process list, Docker panel, log viewer
- [ ] Process management (start/stop/restart)
- [ ] Live log streaming
- [ ] Docker container control
- [ ] One-off commands panel
- [ ] Settings / admin page with auto-start
- [ ] System tray + global shortcut
- [ ] Desktop notifications
- [ ] Flatpak packaging & publishing

---

## 🤝 Contributing

Contributions are welcome! This project is in early development. Feel free to open issues, suggest features, or submit pull requests.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request

Please read [README.DEV.md](README.DEV.md) before contributing to understand the project structure and dev setup.

---

## 📄 License

MIT — do whatever you want with it, just give a little credit. ❤️

---

<p align="center">Built with ❤️ for developers who are tired of juggling terminals</p>
