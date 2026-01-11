# Maximize Docstring (Google) + Unit Test Coverage

*Date: 2026-01-11*

## Overview

Increase **documentation quality** and **behavioral confidence** by:
- Converting/standardizing docstrings to **Google-style** (human- and IDE-friendly)
- Expanding unit tests across the core layers (scanners → models → DB → analytics → exporters → CLI/TUI)
- Adding measurable, automated **coverage gates** so progress sticks

The goal is not only “higher percentages”, but **higher signal**: docstrings that explain intent + contracts, and tests that lock down behavior (including edge cases and failure modes).

## Current State (quick baseline)

- Test suite exists and is healthy: `pytest` passes locally (35 tests).
- Most modules/classes/functions have *some* docstrings, but many appear “one-liner” style rather than full Google docstrings (missing `Args`, `Returns`, `Raises`, examples, etc.).
- No explicit docstring/test coverage tooling is configured yet (no `pytest-cov`, `coverage`, `interrogate`, etc.).

## Requirements & Goals

### Docstring goals (Google style)
- Public API (`claude_tooling_index/__init__.py` exports): **100%** docstring coverage and Google-style content.
- Core “business logic” modules (`scanner`, `multi_scanner`, `database`, `analytics`, `models`, `exporters/*`, `scanners/*`): **near-100%** docstring coverage for public classes/functions.
- For internal helpers: docstrings when behavior is non-trivial, subtle, or security-sensitive (e.g., redaction).

Docstrings should answer:
1) What does it do? (intent)
2) What are the inputs/outputs? (contract)
3) What errors can happen? (failure modes)
4) What are examples of expected usage? (where helpful)

### Unit test goals
- Set an initial “ratchet” target (so we don’t stall):
  - Overall: **≥ 85% line coverage** (first milestone)
  - Core modules: **≥ 90–95%**
- Over time, tighten thresholds as coverage grows.

### Non-goals (to stay practical)
- “100% coverage” via trivial tests that assert implementation details.
- Full end-to-end tests that depend on a real `~/.claude` / `~/.codex` on the developer machine (keep tests hermetic).

## Technical Approach & Architecture

### Coverage gates (two complementary lenses)

1) **Unit test coverage** (execution-based)
   - Tooling: `coverage.py` + `pytest-cov`
   - Output: line + branch coverage, missing lines report

2) **Docstring coverage** (structure-based)
   - Tooling: `interrogate`
   - Output: percent coverage for modules/classes/functions and exclusions

ASCII “quality loop”:

```
     (write/upgrade docstrings)         (add tests)
                │                        │
                ├────────────┬───────────┤
                             ▼
                   run linters + pytest
                             ▼
               coverage reports (test + doc)
                             ▼
                 tighten thresholds (ratchet)
```

### Decisions (with rationale)
- Chose `ruff` + `pydocstyle` rules over `pydocstyle` alone because `ruff` is fast, widely adopted, and consolidates linting in one tool.
- Chose `interrogate` for docstring coverage because it measures “docstring presence” across modules/classes/functions and supports sensible exclusions.
- Chose a “ratchet” threshold strategy over an immediate 95–100% mandate because it avoids blocking development while still guaranteeing monotonic improvement.

## Implementation Steps (phased)

### Phase 0 — Instrumentation (1 PR)
1) Add dev dependencies:
   - `pytest-cov` (or `coverage[toml]` + `pytest-cov`)
   - `interrogate`
   - `ruff` (and optionally `ruff-format` if you want to replace Black later; otherwise keep Black)
2) Configure in `pyproject.toml`:
   - `[tool.coverage.run]` / `[tool.coverage.report]`
   - `[tool.pytest.ini_options]` default `--cov` args (optional)
   - `[tool.interrogate]` + baseline thresholds
   - `[tool.ruff]` + `pydocstyle` with Google convention
3) Add a single “quality” command entry point (choose one):
   - `make test`, `make quality`, or `scripts/quality.sh`

Suggested commands:
```bash
pytest --cov=claude_tooling_index --cov-report=term-missing
interrogate -v claude_tooling_index
ruff check .
```

### Phase 1 — Docstring standardization (Google style) (1–2 PRs)
Target: exported/public surfaces first, then core logic.

1) Define a local standard (1-pager in `CLAUDE.md` or a new `docs/` page):
   - When to include `Args`, `Returns`, `Raises`, `Examples`
   - How to document dataclasses (`Attributes` section vs constructor args)
2) Convert module + class + public method docstrings to Google style in:
   - `claude_tooling_index/scanner.py`
   - `claude_tooling_index/multi_scanner.py`
   - `claude_tooling_index/database.py`
   - `claude_tooling_index/analytics.py`
   - `claude_tooling_index/models.py`
   - `claude_tooling_index/exporters/*`
   - `claude_tooling_index/scanners/*`
3) Add/upgrade docstrings for tricky helpers (examples):
   - redaction, parsing, migrations, concurrency orchestration

Docstring template (Google style):
```python
def fn(x: int) -> int:
    """One-line summary.

    Longer description (optional).

    Args:
        x: What this parameter represents.

    Returns:
        What the function returns.

    Raises:
        ValueError: When input is invalid.
    """
```

### Phase 2 — Unit test expansion by layer (multiple PRs, parallelizable)

#### 2A) Models + parsing helpers
- Validate dataclass invariants (`__post_init__`), derived fields, and normalization.
- Add focused tests for helpers that transform or redact data.

#### 2B) Scanners
For each scanner in `claude_tooling_index/scanners/`:
- “Happy path” fixture: minimal valid structure in `tmp_path`
- “Missing/empty” fixture: returns empty lists, no crash
- “Malformed input” fixture: graceful error capture when expected
- Security checks: redact env vars, avoid leaking secrets into metadata

Pattern:
```
tmp_path/
  .claude/ or .codex/
    ... required files ...
```
Use `monkeypatch.setattr(Path, "home", ...)` to prevent real home access.

#### 2C) Database + migrations
- Use a temp sqlite DB (file-based or in-memory depending on current implementation).
- Assert schema init creates expected tables/indexes (including FTS if applicable).
- Test migrations:
  - old schema → migrate → new schema
  - data preserved; uniqueness constraints enforced
- Test key queries (filters, search, stats) on small deterministic datasets.

#### 2D) Analytics + exporters
- Analytics: verify aggregation logic against a seeded DB.
- Exporters: snapshot-ish tests for JSON/Markdown output structure:
  - stable ordering (sort inputs or compare parsed structures)
  - minimal “golden output” comparisons

#### 2E) CLI + TUI (smoke level)
- CLI: `click.testing.CliRunner` for:
  - `--help` output
  - a few “happy path” commands with `--no-db` / temp homes
- TUI: aim for lightweight tests only (Textual apps can be tricky); focus on:
  - widget construction
  - pure formatting methods
  - avoid requiring a real terminal

### Phase 3 — Automation (CI / local hooks)
Pick at least one:
- GitHub Actions workflow for `pytest + coverage + interrogate + ruff`
- Pre-commit hooks for fast feedback

Quality gates:
- Fail CI if:
  - unit test coverage drops below threshold
  - docstring coverage drops below threshold
  - linting fails (including docstring convention rules)

### Phase 4 — Ratchet & maintenance
- After each coverage jump, raise thresholds modestly (e.g., +2–5%).
- Add a checklist item to PR template: “docs/tests updated for behavior changes”.

## Files to Create / Modify

### Likely modified
- `pyproject.toml` (dev deps + tool configs)
- `CLAUDE.md` (docstring style guidance + quality commands)
- `claude_tooling_index/**/*.py` (Google docstring upgrades)
- `tests/` (new and expanded unit tests)

### Possibly new
- `scripts/quality.sh` (one-command local quality run)
- `.github/workflows/ci.yml` (if you want CI enforcement)
- `docs/Docstrings.md` (optional, if `CLAUDE.md` should stay shorter)

## Dependencies & Prerequisites

- Python tooling:
  - `pytest`, `pytest-asyncio` (already present)
  - `pytest-cov`, `coverage[toml]` (add)
  - `ruff` (add)
  - `interrogate` (add)
  - Optional: `hypothesis` (property-based tests), `freezegun` (time), `pytest-mock`

## Testing Strategy (principles)

- Prefer small, deterministic unit tests over broad integration tests.
- Keep tests hermetic:
  - no real home directory reads
  - no network
  - no reliance on local sqlite files outside `tmp_path`
- Treat concurrency as an implementation detail:
  - unit test deterministic merge/results
  - smoke test “parallel=True” paths without asserting timing

## Potential Challenges & Edge Cases

- **Filesystem variability**: symlinks, permissions, odd encodings.
- **Time-based fields**: `last_modified` and scan times; freeze or assert “is set”, not exact values.
- **SQLite/FTS differences**: ensure tests run consistently across platforms/python versions.
- **Textual TUI**: avoid flaky tests tied to terminal rendering; keep to smoke/pure logic.
- **Secret handling**: ensure tests never embed real secrets; validate redaction behavior explicitly.

## Success Criteria

- Google-style docstrings for all exported/public APIs and core modules.
- `pytest` passes with meaningful new unit tests across:
  - scanners, db, analytics, exporters
- Coverage reports are visible and actionable:
  - missing lines report for tests
  - docstring coverage report with exclusions documented
- Coverage gates prevent regressions (local + CI).

