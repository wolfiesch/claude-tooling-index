# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Tooling Index is a Python package that catalogs and analyzes Claude Code setups. It scans `~/.claude` (and optionally `~/.codex`) directories for 6 component types: Skills, Plugins, Commands, Hooks, MCPs, and Binaries. Features include usage analytics, an interactive TUI dashboard, and dual-mode distribution (CLI + Claude Code plugin).

## Commands

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Run TUI directly during development
python3 cli.py tui

# CLI commands (after install)
tooling-index scan              # Scan and index components
tooling-index scan --verbose    # Show all components
tooling-index scan --no-db      # Skip database update
tooling-index scan --platform all  # Scan both Claude and Codex
tooling-index tui               # Launch interactive dashboard
tooling-index stats             # View usage analytics
tooling-index stats --detailed  # Include Phase 6 extended metrics
tooling-index list              # List all indexed components
tooling-index search "query"    # Full-text search
tooling-index export --format markdown -o tooling.md

# Build C++ hook (for <1ms tracking overhead)
cd hooks && ./build_hook.sh
```

## Architecture

### Core Layers

**Scanner Layer** (`scanner.py`, `multi_scanner.py`)
- `ToolingScanner`: Orchestrates parallel scanning of `~/.claude` directory
- `MultiToolingScanner`: Adds Codex platform support via `~/.codex`
- `scan_all()`: Returns `ScanResult` with all 6 component types
- `scan_extended()`: Returns `ExtendedScanResult` with Phase 6 analytics (user settings, event metrics, session analytics, token economics, growth metrics)

**Scanners** (`scanners/`)
- Each component type has a dedicated scanner (e.g., `SkillScanner`, `MCPScanner`)
- Scanners parse component-specific files (SKILL.md frontmatter, mcp.json, YAML commands)
- Extended scanners (Phase 6): `UserSettingsScanner`, `EventQueueScanner`, `InsightsScanner`, `SessionAnalyticsScanner`, `TodoScanner`, `TranscriptScanner`, `GrowthScanner`

**Models** (`models.py`)
- Base class `ComponentMetadata` with type-specific subclasses (`SkillMetadata`, `MCPMetadata`, etc.)
- Each subclass sets `type` field in `__post_init__`
- `ScanResult`: Container for all component lists
- `ExtendedScanResult`: Adds Phase 6 metrics dataclasses

**Database** (`database.py`)
- SQLite with FTS5 full-text search at `~/.claude/data/tooling_index.db`
- Tables: `components`, `invocations`, `installation_events`, `components_fts`
- Handles schema migrations (e.g., adding `platform` column)

**Analytics** (`analytics.py`)
- `AnalyticsTracker`: Wraps database for usage tracking
- Methods: `update_components()`, `track_invocation()`, `get_usage_stats()`, `search_components()`

**Exporters** (`exporters/`)
- `JSONExporter`: Structured JSON output
- `MarkdownExporter`: Human-readable documentation format

**TUI** (`tui/`)
- Built with Textual framework
- `ToolingIndexTUI`: Main app with split pane layout
- Widgets: `ComponentList`, `DetailView`, `SearchBar`
- Filters: Platform (claude/codex) and Type (skill/plugin/command/hook/mcp/binary)
- Keybindings: `/` search, `1-7` type filters, `r` refresh, `q` quit

### Data Flow

1. CLI command → `MultiToolingScanner.scan_all(platform)` → runs scanners in parallel via `ThreadPoolExecutor`
2. Each scanner returns typed metadata list → aggregated into `ScanResult`
3. `AnalyticsTracker.update_components()` persists to SQLite
4. TUI/CLI queries via `AnalyticsTracker` methods

### Key Patterns

- **Parallel scanning**: `ThreadPoolExecutor(max_workers=6)` for speed
- **Error isolation**: `_safe_scan()` wrapper catches exceptions per scanner
- **FTS5 search**: Standalone virtual table (not content-linked) for component search
- **Platform dimension**: Components keyed by `(platform, name, type)` tuple

## Database Location

Default: `~/.claude/data/tooling_index.db`

## Plugin Integration

Slash commands in `plugin-commands/`:
- `/tooling-index` → Launch TUI
- `/tooling-scan` → Refresh index
- `/tooling-stats` → View analytics

## Dependencies

- `textual>=0.47.0` - TUI framework
- `rich>=13.0.0` - Terminal formatting
- `click>=8.0.0` - CLI interface
- `pyyaml>=6.0` - Configuration parsing
