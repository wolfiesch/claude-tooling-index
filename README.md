# Claude Code Tooling Index

[![CI](https://github.com/wolfiesch/claude-tooling-index/actions/workflows/ci.yml/badge.svg)](https://github.com/wolfiesch/claude-tooling-index/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/wolfiesch/claude-tooling-index/graph/badge.svg)](https://codecov.io/gh/wolfiesch/claude-tooling-index)

A shareable tool that catalogs and analyzes your Claude Code setup with usage analytics and an interactive TUI dashboard.

## Features

- **Auto-indexes** all 6 component types:
  - Skills (`~/.claude/skills/`)
  - Plugins (`~/.claude/plugins/`)
  - Commands (`~/.claude/commands/`)
  - Hooks (`~/.claude/hooks/`)
  - MCPs (`~/.claude/mcp.json`)
  - Binaries (`~/.claude/bin/`)

- **Usage Analytics**
  - Invocation counts and frequency
  - Performance metrics (execution time)
  - Installation timeline
  - Most-used components ranking

- **TUI Dashboard**
  - Terminal UI for exploring your tooling
  - Live search and filtering
  - Type filter buttons
  - Component detail panel
  - Keyboard navigation

- **Dual-Mode Distribution**
  - Works as Claude Code plugin (slash commands)
  - Works as standalone CLI (`pip install`)

- **High-Performance Tracking**
  - C++ hook for <1ms overhead
  - Python fallback for compatibility
  - SQLite with FTS5 full-text search

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/wolfiesch/claude-tooling-index
cd claude-tooling-index
./INSTALL.sh
```

### Via Pip

```bash
pip install claude-tooling-index

# Run initial scan
tooling-index scan
```

### Via Plugin System

```bash
# Register marketplace
claude /marketplace add tooling-index https://github.com/wolfiesch/claude-tooling-index

# Install plugin
claude /plugin install tooling-index@tooling-index
```

## Usage

### TUI Dashboard

Launch the interactive terminal dashboard:

```bash
tooling-index tui
```

**Keyboard Shortcuts:**
| Key | Action |
|-----|--------|
| `/` | Focus search bar |
| `q` | Quit dashboard |
| `r` | Refresh component list |
| `↑/↓` | Navigate list |
| `Enter` | View component details |
| `1` | Show all components |
| `2` | Filter to Skills |
| `3` | Filter to Plugins |
| `4` | Filter to Commands |
| `5` | Filter to Hooks |
| `6` | Filter to MCPs |
| `7` | Filter to Binaries |

### CLI Commands

```bash
# Scan and refresh index
tooling-index scan
tooling-index scan --verbose      # Show all components
tooling-index scan --no-db        # Skip database update

# List components
tooling-index list
tooling-index list --type skill
tooling-index list --origin in-house
tooling-index list --status active
tooling-index list --json         # JSON output

# View analytics
tooling-index stats
tooling-index stats --days 7      # Last week
tooling-index stats --days 90     # Last 3 months

# Search components
tooling-index search "gmail"
tooling-index search "performance" --type skill

# Export to file
tooling-index export --format markdown -o tooling.md
tooling-index export --format json -o tooling.json
tooling-index export --no-disabled  # Exclude disabled
```

### Slash Commands (from Claude Code)

```
/tooling-index    # Launch TUI dashboard
/tooling-scan     # Refresh component index
/tooling-stats    # View usage analytics
```

## What Gets Indexed

### Skills
- Parses `SKILL.md` for metadata
- Extracts version, description, performance metrics
- Counts files and lines of code
- Detects documentation presence

### Plugins
- Parses `installed_plugins.json`
- Tracks marketplace source
- Records installation date and version
- Lists provided commands and MCPs

### Commands
- Extracts YAML frontmatter
- Captures description and metadata
- Detects origin (in-house vs plugin)

### Hooks
- Identifies language (Python, shell, C++)
- Detects trigger type
- Measures file size
- Checks executable status

### MCPs
- Parses `mcp.json` configuration
- Records command and arguments
- Identifies transport type
- Tracks environment variables

### Binaries
- Detects language via shebang
- Checks executable permissions
- Measures file size

## Architecture

```
claude-tooling-index/
├── claude_tooling_index/       # Python package
│   ├── scanner.py              # Main orchestrator (parallel scanning)
│   ├── models.py               # Data classes
│   ├── database.py             # SQLite + FTS5
│   ├── analytics.py            # Usage tracking
│   ├── scanners/               # Component scanners
│   │   ├── skills.py
│   │   ├── plugins.py
│   │   ├── commands.py
│   │   ├── hooks.py
│   │   ├── mcps.py
│   │   └── binaries.py
│   ├── exporters/              # Output formats
│   │   ├── json_exporter.py
│   │   └── markdown_exporter.py
│   └── tui/                    # Terminal UI
│       ├── app.py
│       ├── styles.tcss
│       └── widgets/
├── hooks/                      # Tracking hooks
│   ├── post_tool_use_tooling.cpp   # C++ (<1ms)
│   ├── post_tool_use_tooling.py    # Python fallback
│   ├── CMakeLists.txt
│   └── build_hook.sh
├── plugin-commands/            # Slash commands
│   ├── tooling-index.md
│   ├── tooling-scan.md
│   └── tooling-stats.md
├── .claude-plugin/             # Plugin manifest
│   ├── plugin.json
│   └── marketplace.json
├── cli.py                      # CLI entry point
├── pyproject.toml              # Package config
├── INSTALL.sh                  # Auto-setup
└── README.md
```

## Database

Location: `~/.claude/data/tooling_index.db`

**Tables:**
- `components` - All indexed components with metadata
- `invocations` - Usage tracking (when, duration, success)
- `installation_events` - Install/update/remove timeline
- `components_fts` - Full-text search index

## Configuration

Optional config file: `~/.claude/config/tooling-index.yaml`

```yaml
# Database settings
database:
  path: ~/.claude/data/tooling_index.db
  backup_enabled: true

# Analytics
analytics:
  enabled: true
  track_invocations: true
  track_performance: true
  retention_days: 365

# Scanning
scanning:
  scan_disabled: true     # Scan .disabled/ folders
  scan_symlinks: true
  parallel_workers: 6
  exclude_patterns:
    - "**/__pycache__"
    - "**/node_modules"

# TUI
tui:
  theme: "solarized"      # solarized, dracula, monokai
  vim_mode: true
```

Environment variables:
- `TOOLING_INDEX_TRANSCRIPT_SAMPLE_LIMIT`: Max transcript files to scan for token analytics. Set to `0` to scan all files (default). Use a smaller number (e.g. `500`) to trade accuracy for speed.

## C++ Hook Installation

The C++ hook provides <1ms overhead for tracking (vs ~50ms for Python).

```bash
# Build and install
cd hooks
./build_hook.sh

# Verify
ls -la ~/.claude/hooks/post_tool_use_tooling
```

**Requirements:**
- CMake
- C++ compiler (g++, clang++)
- SQLite3 development files

**To uninstall:**
```bash
rm ~/.claude/hooks/post_tool_use_tooling
```

## Development

```bash
# Clone repository
git clone https://github.com/wolfiesch/claude-tooling-index
cd claude-tooling-index

# Install in development mode
pip install -e .

# Run tests
pytest

# Run TUI directly
python3 cli.py tui

# Build C++ hook
cd hooks && ./build_hook.sh
```

## Requirements

- Python 3.8+
- Dependencies (auto-installed):
  - `textual>=0.47.0` - TUI framework
  - `rich>=13.0.0` - Terminal formatting
  - `click>=8.0.0` - CLI interface
  - `pyyaml>=6.0` - Configuration

## Performance

- **Full scan**: <2 seconds (6 component types in parallel)
- **C++ hook**: <1ms execution time
- **Database queries**: <50ms (indexed, FTS5)
- **TUI responsiveness**: <100ms for all interactions

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Created by Wolfgang Schoenberger

## Links

- **Repository**: https://github.com/wolfiesch/claude-tooling-index
- **Issues**: https://github.com/wolfiesch/claude-tooling-index/issues
