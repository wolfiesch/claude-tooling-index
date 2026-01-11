---
**IMPLEMENTATION STATUS**: 🚧 IN PROGRESS
**Implemented Date**: 2026-01-11
**Implementation Summary**: Completed Sprints 1–6 (Skills structured metadata; MCP source, redaction, and source detail; Plugin manifest summary + extra fields; Command frontmatter extras) plus TUI enable/disable + refresh UX. Sprint 7 (optional follow-ups) remains.
---

## Usage

- Run `tooling-index tui` and select a component to view new sections in the right-hand detail panel.
- Press `r` (or click Refresh) to rescan.
- Press `e` to toggle enable/disable for supported component types (skills/commands/hooks/binaries, and MCPs where supported by config source).

## What Was Implemented

- Sprint 1: Skills structured metadata (dependency sources + frontmatter extras) shown in TUI.
- Sprint 2: MCP source + env redaction, plus Codex MCP enabled/disabled support.
- Sprint 3: Plugin manifest summary (description + provides commands/MCPs) shown in TUI.
- Sprint 4: MCP source detail + scan-error visibility (helps explain empty Codex views).
- Sprint 5: Plugin extra manifest fields (author/homepage/repository/license) shown in TUI.
- Sprint 6: Command frontmatter extras shown in TUI.
- TUI: Enable/disable toggle (`e`) for supported types; Refresh button + improved filter persistence.

## Testing

- `ruff check .`
- `pytest -q`

---

# Structured Metadata in TUI (Sprint Plan) — 2026-01-11

## Overview

Add a structured metadata layer that extracts key configuration information from Claude Code (`~/.claude`) and Codex CLI (`~/.codex`) sources and displays it in the Tooling Index TUI in a consistent, safe-to-render way (redacting secrets by default).

This plan is intentionally sprint-shaped: it breaks work into small, shippable increments that can be implemented and validated independently.

## Requirements & Goals

### Goals

- Show richer, structured metadata per component in the TUI detail panel.
- Ensure all sensitive values are redacted (preserve `${ENV_VAR}` placeholders).
- Keep scanning fast and failure-isolated (scanner errors should not crash the UI).
- Keep changes compatible with multi-platform scanning (`claude`, `codex`, `all`).

### Non-goals (initially)

- Plugin enable/disable (needs a separate decision on what “disable” means operationally).
- Persisting full raw configs in the DB (we’ll store only safe, summarized metadata).
- Complex semantic parsing of long markdown bodies (start with deterministic config sources).

## Data Sources (Inventory)

### Claude

- Skills: `~/.claude/skills/**/SKILL.md` (+ optional dependency files)
- Commands: `~/.claude/commands/*.md`
- Hooks: `~/.claude/hooks/*`
- Binaries: `~/.claude/bin/*`
- Plugins: `~/.claude/plugins/installed_plugins.json` and cached plugin manifests
- MCPs:
  - `~/.claude.json` (`mcpServers`, `projects.*.mcpServers`)
  - `~/.claude/mcp.json` (legacy)
  - Plugin-provided: plugin cache (`.mcp.json`, `plugin.json`)
  - Built-in: detected paths (e.g., `claude-in-chrome`)

### Codex

- Skills: `~/.codex/skills/**/SKILL.md` (+ optional dependency files)
- MCPs: `~/.codex/config.toml` (`[mcp_servers.*]`, `[mcp_servers_disabled.*]`)

## Structured Metadata v1 (Schema)

### Skills (Sprint 1)

Extract and display:

- **Frontmatter extras**: any YAML keys beyond `name`, `description`, `version`
  - Example: `metadata.short-description`, `toolkits`, etc.
- **Dependencies** (best-effort):
  - Python: `requirements.txt`, `pyproject.toml` / `project.dependencies`
  - Node: `package.json` / `dependencies`
  - (Future): lockfiles, optional language-specific dep files
- **Dependency sources**: which files contributed to the dependency list

Display in TUI detail view:

- Existing “Dependencies” section populated from real dep files
- New “Frontmatter” section showing parsed key/value pairs

### MCPs (Sprint 2)

Extract and display:

- Source (user/project/legacy/plugin/builtin for Claude; enabled/disabled table for Codex)
- Command / args / transport
- Redacted env keys and placeholder-vs-literal distinction

### Plugins (Sprint 3)

Extract and display:

- Installed plugin metadata (name/marketplace/version/installedAt/lastUpdated/git)
- Cached manifest summaries (description, provides MCPs/commands if discoverable)

## Architecture / Technical Approach

### Principles

- **No secrets in UI**: redact literal env values and any obvious credentials.
- **Stable interface**: add fields to models in a backwards-compatible way (defaults).
- **Best-effort parsing**: if a config file is missing/invalid, skip with a per-component error string (don’t crash scanning).
- **Keep scanning fast**: avoid deep recursion beyond what’s already done; dependency parsing should be shallow and optional.

### Code Touchpoints

- `claude_tooling_index/scanners/skills.py`
  - Enhance to parse dependency files and frontmatter extras
- `claude_tooling_index/models.py`
  - Extend `SkillMetadata` with a structured field for frontmatter extras and dep sources
- `claude_tooling_index/tui/widgets/detail_view.py`
  - Render new “Frontmatter” section for skills
- `claude_tooling_index/database.py`
  - Include new skill fields in `metadata_json` for later search/export
- Exporters
  - `claude_tooling_index/exporters/json_exporter.py` already supports `dependencies`
  - Add support for “frontmatter extras” once implemented

## Implementation Plan (Sprints)

### Sprint 1 — Skills: Structured Metadata (this starts now)

1. **Model**: Add skill fields for:
   - `frontmatter_extra` (dict)
   - `dependency_sources` (list of filenames)
2. **Scanner**: Extract:
   - frontmatter extras
   - dependencies from `requirements.txt`, `pyproject.toml`, `package.json`
3. **TUI**:
   - Render “Frontmatter” and “Dependency Sources” sections in DetailView for skills
4. **DB/Export**:
   - Add new fields to stored `metadata_json`
5. **Tests**:
   - Extend skill scanner tests to cover dependencies + extras parsing

### Sprint 2 — MCPs: Source + Redacted Env

- Add explicit “source” and “enabled/disabled” status in the model for MCPs.
- Display per-MCP config summary with redaction.
- Validate toggling behavior still works.

### Sprint 3 — Plugins: Manifest Summary

- Parse `plugin.json` and `.mcp.json` from cache to show:
  - declared MCP servers, commands, description, repo URL
- Add safe redaction for env vars.

### Sprint 4 — MCPs: Source Detail + Visibility

- Add an explicit `source_detail` field (safe file path / config origin pointer) for MCPs.
- Display the source detail in the MCP detail view.
- Improve empty/failed Codex scans visibility in the UI (so “Codex” doesn’t look broken when nothing is configured).

### Sprint 5 — Plugins: Additional Manifest Fields

- Extract additional `plugin.json` fields when present (author, homepage, repository, license).
- Display those fields in the plugin detail view.
- Ensure values are rendered safely (strings only; redact obviously sensitive values if encountered).

### Sprint 6 — Commands: Frontmatter Extras

- Add `frontmatter_extra` to command metadata (like skills).
- Render command frontmatter extras in the detail view.

### Sprint 7 — Optional Follow-ups

- Unify dependency extraction across skill/command/plugin sources where applicable.
- Add a “Scan errors” viewer in the TUI (optional panel or popover).

### Sprint 8 — Skills: Invocation + References (Heuristics)

Extract and display more structured information from `SKILL.md` bodies:

- Invocation hints:
  - slash command aliases (`/runplan` style)
  - argument string (if present)
  - primary “instruction” line (e.g., `Implement the plan from: @$1`)
- References:
  - file refs (`@CLAUDE.md`, `@Plans/...`, `@$1`)
  - skill refs (`$some-skill`) to approximate “sub-agent” linking
- Context hints:
  - whether the text mentions context forking (store as “hint”, not a fact)

This stays deterministic (regex + shallow parsing) so it’s fast and doesn’t require external APIs.

### Sprint 9 — Optional: LLM-Normalized Summary (Future)

- Add an *opt-in* mode that uses an LLM to generate a short standardized summary and tags for each skill.
- Must run locally/with explicit user consent, and the stored output must be safe (no secrets) and small.

## Files to Modify / Create

- Create: `Plans/Structured_Metadata_TUI_Sprint_2026-01-11.md` (this file)
- Modify:
  - `claude_tooling_index/models.py`
  - `claude_tooling_index/scanners/skills.py`
  - `claude_tooling_index/tui/widgets/detail_view.py`
  - `claude_tooling_index/database.py`
  - `tests/test_scanners.py` and/or new focused tests under `tests/`

## Dependencies / Prerequisites

- Python stdlib parsing: `json`, `tomllib` (with `tomli` fallback already present in repo)
- Keep compatible with Python >= 3.8 (avoid 3.9+ only syntax in public code)

## Testing Strategy

- Unit tests:
  - skill scanner: parses deps and extras correctly
  - redaction and error paths (invalid TOML/JSON should not crash)
- TUI tests:
  - confirm DetailView renders the new sections for a skill with extras/deps

## Potential Challenges & Edge Cases

- Skills without dependency files should show “none” without errors.
- `pyproject.toml` schema variance (`[project]`, `tool.poetry`, etc.) — start with `[project.dependencies]` only.
- Non-string YAML frontmatter values (dict/list) should be rendered safely.
- Large skills directories: keep dependency parsing shallow and bounded.

## Success Criteria

- Selecting a skill in the TUI shows:
  - dependencies (if present)
  - frontmatter extras (if present)
  - dependency sources (if present)
- Scans remain fast and resilient; no crashes on missing or malformed files.
- Tests pass with required coverage threshold.
