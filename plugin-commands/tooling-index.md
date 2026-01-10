---
description: Launch interactive TUI dashboard for Claude Code tooling
---

# Tooling Index Dashboard

Launch the terminal UI dashboard to explore your Claude Code setup.

## Features

- **Component Browser**: View all skills, plugins, commands, hooks, MCPs, and binaries
- **Live Search**: Filter components by name with real-time results
- **Type Filters**: Quick filters for each component type
- **Detail Panel**: Full metadata, performance metrics, and dependencies
- **Usage Analytics**: See which components are used most

## Keyboard Shortcuts

- `/` - Focus search bar
- `q` - Quit dashboard
- `r` - Refresh component list
- `1-7` - Quick filter by type (All, Skills, Plugins, Commands, Hooks, MCPs, Binaries)
- `↑/↓` or `j/k` - Navigate component list
- `Enter` - View component details

## Usage

Run the TUI dashboard:

```bash
cd ~/claude-tooling-index && python3 cli.py tui
```

Or if installed via pip:

```bash
tooling-index tui
```
