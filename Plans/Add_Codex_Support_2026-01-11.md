# Add Codex Support (Codex CLI) to Tooling Index

*Date: 2026-01-11*

## Overview

Extend `claude-tooling-index` so it can index and analyze **Codex CLI** tooling (from `~/.codex`) in addition to **Claude Code** tooling (from `~/.claude`). The goal is a single database + UI that can show “what tools I have installed and how I use them” across both ecosystems.

## Requirements & Goals

### Goals (MVP)
- Index Codex **skills** (`~/.codex/skills/*/SKILL.md`) alongside Claude skills.
- Index Codex **MCP servers** from `~/.codex/config.toml` (`[mcp_servers.*]` blocks).
- Prevent naming collisions between Claude and Codex components (same `type` + `name` should be allowed if they’re from different platforms).
- CLI supports selecting a platform: `claude`, `codex`, or `all`.
- Exporters and TUI can display which platform a component belongs to.

### Non-goals (initially)
- Full parity for Claude-only concepts that Codex doesn’t have (plugins, hooks, commands, binaries).
- Deep usage analytics from Codex session logs/history (can be a follow-on).
- Changing the plugin packaging for Claude (keep existing behavior working).

## Codex Surface Area (what exists today)

Based on the local Codex home layout (`~/.codex`):
- `skills/` mirrors the Claude skills structure (`SKILL.md` with YAML frontmatter).
- `config.toml` includes:
  - `model`, `model_reasoning_effort`
  - `projects."<path>".trust_level`
  - `mcp_servers.<name>` blocks with `command`, `args`, optional `env`, and timeouts
- `sessions/**.jsonl` contains event streams (`session_meta`, `response_item`, `event_msg`) that could be used later for analytics.
- `history.jsonl` appears to be minimal (`ts`, `session_id`, `text`) and likely needs parsing/normalization.

## Technical Approach & Architecture

### Core design decision: add a `platform` dimension

Today, uniqueness in the DB is `UNIQUE(name, type)`. Adding Codex introduces collisions (e.g., a `skill` with the same name exists in both).

Introduce a `platform` field (e.g., `claude`, `codex`) and make uniqueness `UNIQUE(platform, name, type)`.

At a high level:

```
          ┌────────────────────┐
          │ Platform Scanner   │
          │  - claude          │
          │  - codex           │
          └─────────┬──────────┘
                    │ produces
                    ▼
             ScanResult (flat)
                    │
                    ▼
         ToolingDatabase.update_components
                    │
                    ▼
             TUI / exporters / stats
```

### Minimal refactor strategy

Keep the existing per-component scanners (`SkillScanner`, `MCPScanner`, …) and wrap them in a **multi-platform orchestrator**.

Two options:

1) **Introduce a new orchestrator** (recommended):
   - `MultiToolingScanner(platforms=[...])` merges results from:
     - existing `ToolingScanner` (Claude)
     - new `CodexToolingScanner` (Codex)
   - Keeps Claude logic intact and isolates Codex-specific parsing.

2) **Modify `ToolingScanner` to accept a platform**:
   - `ToolingScanner(platform="claude"|"codex", home=Path(...))`
   - Potentially cleaner long-term, but touches more call sites at once.

## Data Model Changes

### Models
- Add `platform: str` to `ComponentMetadata` (and therefore all subclasses).
  - Values: `"claude"` and `"codex"` (keep simple strings; avoid enums unless the codebase already uses them).
- Ensure scanners set `platform` explicitly.
  - Claude scanners: `platform="claude"`
  - Codex scanners: `platform="codex"`

### Database schema + migration

In `claude_tooling_index/database.py`:
- Add `platform TEXT NOT NULL DEFAULT 'claude'` to `components`.
- Update uniqueness constraint to include platform.
  - Because SQLite doesn’t support altering constraints directly, plan for a migration that:
    - creates a new table, copies rows, drops old table, renames, recreates indexes + FTS.

Migration strategy:
1. Detect whether `platform` exists.
2. If missing, run a one-time migration:
   - All existing rows get `platform='claude'`.
3. Update all queries that look up components by `(name, type)` to also filter by platform.

## Scanner Changes

### 1) Codex home detection
- Add a `detect_codex_home()` helper similar to `_detect_claude_home()`:
  - default `~/.codex`
  - if missing and user requested Codex, show a clear error

### 2) Codex skills
- Reuse `SkillScanner` for `~/.codex/skills`.
- Update `SkillScanner` to accept an `origin` and `platform` override (or wrap it):
  - `origin` default could remain `"in-house"`, but platform clarifies provenance.
  - Alternatively set `origin="codex"` or `"in-house"` and rely on `platform` for source.

### 3) Codex MCPs
- Add `CodexMCPScanner`:
  - Parse `~/.codex/config.toml` for `[mcp_servers]`.
  - Map to existing `MCPMetadata`:
    - `name`: server key
    - `command`: `command`
    - `args`: `args`
    - `env_vars`: keys/values from `env`
    - `transport`: assume `"stdio"` unless config indicates otherwise

Security requirement:
- Redact secrets in env by default (recommended):
  - Store only env var *names* (keys), or store values but redact anything matching token-like patterns.
  - Add a CLI flag/config for opt-in raw env storage if needed.

### 4) Multi-platform scan results

Add a merge layer that:
- Combines lists for each type
- Preserves `platform` so the UI/export can group/filter
- Accumulates errors with platform prefix (e.g., `[codex] Error scanning mcps: ...`)

## CLI Changes

In `claude_tooling_index/cli.py`:
- Add `--platform` option: `claude` (default), `codex`, `all`
- Add optional overrides:
  - `--claude-home PATH`
  - `--codex-home PATH`
- Update command output to include per-platform counts when platform != `claude`.

Example output shape:
- Total components
- By platform: claude vs codex
- By type: skills/plugins/...

## TUI Changes

In `claude_tooling_index/tui/widgets/component_list.py` and related UI:
- Add a `Platform` column (and show `claude`/`codex`).
- Add a platform filter:
  - Minimal: toggle buttons `All / Claude / Codex`
  - Or: a dropdown/select near the type filters
- Update title/subtitle to not be Claude-only when showing `all`.

## Exporter Changes

In `claude_tooling_index/exporters/*`:
- Include platform in tables and detail views.
- Update headers when exporting combined data:
  - e.g. “Claude + Codex Tooling Index” or “AI Tooling Index”

## Usage Analytics (Follow-on Phase)

Codex doesn’t have the same hook/event_queue mechanism as Claude’s `~/.claude/data/event_queue.jsonl`, but it does have `~/.codex/sessions/**.jsonl`.

Possible next steps:
- Create `CodexSessionScanner`:
  - Parse `session_meta` events for session counts, project cwd, timestamps.
  - Parse `response_item` payloads for tool usage if tool-call structure is available.
- Add a platform-aware “session metrics” panel in TUI and `stats --detailed`.

## Files to Create / Modify

### Likely modified
- `claude_tooling_index/models.py` (add `platform`)
- `claude_tooling_index/database.py` (schema + migration + queries)
- `claude_tooling_index/scanner.py` (or add a new multi-platform orchestrator)
- `claude_tooling_index/scanners/mcps.py` (optional: shared parsing utilities)
- `claude_tooling_index/cli.py` (new flags + behavior)
- `claude_tooling_index/tui/app.py` (title + platform filter)
- `claude_tooling_index/tui/widgets/component_list.py` (platform column/filter)
- `claude_tooling_index/exporters/markdown_exporter.py` (platform display)

### Likely new
- `claude_tooling_index/scanners/codex_mcps.py` (parse `config.toml`)
- `claude_tooling_index/scanners/codex_home.py` (detection helpers) or similar
- `claude_tooling_index/scanners/codex.py` (Codex-specific orchestrator) if keeping separation

## Dependencies & Prerequisites

- TOML parsing:
  - If already available, use stdlib `tomllib` (Python 3.11+).
  - If the project supports Python 3.8+, add a lightweight dependency like `tomli` for older versions.

## Testing Strategy

There are currently no tests in `tests/`.

Suggested minimal tests to add (if the repo is open to adding tests):
- Unit test for Codex MCP parsing:
  - input: small TOML string with `mcp_servers`
  - output: list of `MCPMetadata` with expected fields
- DB migration smoke test:
  - create an in-memory sqlite db in the old schema
  - run init/migration
  - verify `platform` column exists and uniqueness works
- Merge/orchestrator test:
  - combine two fake scan results and ensure both are present without collisions

If adding tests isn’t desired, add a manual verification checklist instead.

## Potential Challenges & Edge Cases

- **Secrets in `config.toml`**: avoid storing raw values by default.
- **Python version compatibility**: `tomllib` vs `tomli`.
- **DB migration correctness**: ensure FTS table stays in sync and existing users don’t lose history.
- **Component naming collisions**: must update all lookups to include platform (especially invocation tracking).
- **Partial installs**: users might have only Codex or only Claude; scanning should degrade gracefully.

## Success Criteria

- `tooling-index scan --platform claude` behaves exactly as today.
- `tooling-index scan --platform codex` works on a machine with `~/.codex`, even if `~/.claude` is missing.
- `tooling-index scan --platform all` shows a combined view with no collisions.
- TUI and markdown export clearly label each component’s platform.
- DB migration is automatic and preserves existing data.

