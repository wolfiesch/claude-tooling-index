from __future__ import annotations

import builtins
import json
import os
import shutil
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from claude_tooling_index.analytics import AnalyticsTracker
from claude_tooling_index.cli import cli


def _seed_core_components(mock_claude_home: Path) -> None:
    skill_dir = mock_claude_home / "skills" / "gmail-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: gmail-skill
description: gmail integration
---

## Performance

| Operation | Time | Speedup |
| --- | --- | --- |
| scan | 10ms | 2x |
"""
    )

    # Command
    (mock_claude_home / "commands" / "hello.md").write_text(
        """---
description: Says hello
---

# /hello
"""
    )

    # Hook (name includes "tooling" => "official")
    (mock_claude_home / "hooks" / "post_tool_use_tooling.py").write_text(
        "#!/usr/bin/env python3\nprint('hook')\n"
    )

    # Binary
    bin_file = mock_claude_home / "bin" / "hello"
    bin_file.write_text("#!/usr/bin/env bash\necho hi\n")
    os.chmod(bin_file, 0o755)

    # Plugin
    plugin_install_dir = mock_claude_home / "plugins" / "cache" / "mkt" / "p1" / "1.0.0"
    plugin_install_dir.mkdir(parents=True)
    (mock_claude_home / "plugins" / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "p1@mkt": [
                        {
                            "installPath": str(plugin_install_dir),
                            "version": "1.0.0",
                            "installedAt": "2026-01-11T00:00:00Z",
                            "lastUpdated": "2026-01-11T00:00:00Z",
                            "gitCommitSha": "abc",
                        }
                    ]
                },
            }
        )
    )

    # MCP (legacy ~/.claude/mcp.json path)
    (mock_claude_home / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "legacy-mcp": {
                        "command": "modelcontextprotocol-mcp",
                        "args": ["--flag"],
                    }
                }
            }
        )
    )


def _seed_codex_components(mock_codex_home: Path) -> None:
    skill_dir = mock_codex_home / "skills" / "codex-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: codex-skill\n---\n")

    (mock_codex_home / "config.toml").write_text(
        """
[mcp_servers.test-server]
command = "python3"
args = ["-m", "test_mcp"]
env = { API_KEY = "${API_KEY}", DEBUG = "true" }
"""
    )


def _seed_extended_phase6_data(tmp_path: Path, mock_claude_home: Path) -> None:
    # ~/.claude.json (Path.home() is patched by fixtures to tmp_path)
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {
                "numStartups": 10,
                "firstStartTime": "2025-01-01T00:00:00Z",
                "memoryUsageCount": 2,
                "promptQueueUseCount": 3,
                "skillUsage": {
                    "gmail-skill": {"usageCount": 5, "lastUsedAt": 1_700_000_000_000},
                },
                "tipsHistory": {"tip-a": 9},
                "projects": {"p": {}},
                "githubRepoPaths": {"repo-a": ["/x/repo-a"]},
            }
        )
    )

    # Event queue metrics
    (mock_claude_home / "data" / "event_queue.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "hook_event_type": "PostToolUse",
                        "timestamp": 1_700_000_000_000,
                        "session_id": "s1",
                        "payload": {"permission_mode": "auto", "tool_name": "read_file"},
                    }
                ),
                json.dumps(
                    {
                        "hook_event_type": "PreToolUse",
                        "timestamp": 1_700_000_000_100,
                        "session_id": "s2",
                        "payload": {
                            "permission_mode": "manual",
                            "tool_input": {"name": "write_file"},
                        },
                    }
                ),
            ]
        )
        + "\n"
    )

    # Insights DB
    db_path = mock_claude_home / "data" / "insights.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE insights (
                category TEXT,
                project_path TEXT,
                insight_text TEXT,
                timestamp DATETIME
            )
            """
        )
        conn.execute("CREATE TABLE processed_sessions (id TEXT)")
        conn.execute("INSERT INTO processed_sessions VALUES ('s1')")
        conn.execute(
            "INSERT INTO insights VALUES ('warning', '/x/proj', 'danger zone', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO insights VALUES ('pattern', '/x/proj', 'a pattern', datetime('now'))"
        )
        conn.execute("CREATE VIRTUAL TABLE insights_fts USING fts5(insight_text)")
        conn.execute(
            "INSERT INTO insights_fts(rowid, insight_text) VALUES (1, 'danger zone')"
        )
        conn.execute("INSERT INTO insights_fts(rowid, insight_text) VALUES (2, 'a pattern')")
        conn.commit()
    finally:
        conn.close()

    # Sessions analytics
    sessions_dir = mock_claude_home / "data" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "s1.json").write_text(
        json.dumps({"prompts": ["a", "b", "c"], "source_app": "demo-project"})
    )

    # Todos
    todos_dir = mock_claude_home / "todos"
    todos_dir.mkdir(parents=True, exist_ok=True)
    (todos_dir / "todos.json").write_text(
        json.dumps([{"status": "completed"}, {"status": "pending"}, {"status": "in_progress"}])
    )

    # Transcripts
    project_dir = mock_claude_home / "projects" / "demo"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "session.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "model": "gpt-test",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "cache_read_input_tokens": 5,
                        "cache_creation_input_tokens": 3,
                    },
                    "content": [{"type": "tool_use", "name": "read_file"}],
                },
            }
        )
        + "\n"
    )

    # Growth
    growth_dir = mock_claude_home / "agentic-growth"
    edges_dir = growth_dir / "edges" / "category-a"
    patterns_dir = growth_dir / "patterns" / "category-b"
    edges_dir.mkdir(parents=True, exist_ok=True)
    patterns_dir.mkdir(parents=True, exist_ok=True)
    (edges_dir / "EDGE-001.md").write_text("# Edge\n")
    (patterns_dir / "PATTERN-001.md").write_text("# Pattern\n")
    (growth_dir / "progression.md").write_text("L4: Meta-Engineer *CURRENT LEVEL*\n")
    (growth_dir / "project-edges.json").write_text(json.dumps({"proj": ["EDGE-001"]}))


def test_cli_scan_platform_all_verbose_by_platform_and_errors(
    mock_claude_home: Path, mock_codex_home: Path, tmp_path: Path
) -> None:
    _seed_core_components(mock_claude_home)
    _seed_codex_components(mock_codex_home)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scan",
            "--platform",
            "all",
            "--claude-home",
            str(mock_claude_home),
            "--codex-home",
            str(mock_codex_home),
            "--sequential",
            "--verbose",
        ],
    )
    assert result.exit_code == 0
    assert "By platform" in result.output
    assert "Component Details" in result.output

    # Trigger scan errors list: remove ~/.codex so codex scan fails under platform=all.
    shutil.rmtree(mock_codex_home)
    result = runner.invoke(
        cli,
        [
            "scan",
            "--platform",
            "all",
            "--claude-home",
            str(mock_claude_home),
            "--sequential",
            "--no-db",
        ],
    )
    assert result.exit_code == 0
    assert "Errors encountered" in result.output


def test_cli_stats_covers_usage_paths_and_extended_metrics(
    mock_claude_home: Path, tmp_path: Path
) -> None:
    _seed_core_components(mock_claude_home)
    _seed_extended_phase6_data(tmp_path, mock_claude_home)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", "--platform", "claude", "--claude-home", str(mock_claude_home), "--sequential"],
    )
    assert result.exit_code == 0

    tracker = AnalyticsTracker()
    try:
        # Ensure we have enough invocations for most_used + performance_avg branches.
        tracker.track_invocation(
            "gmail-skill",
            session_id="fallback-skill",
            duration_ms=99,
            platform="claude",
        )
        for i in range(3):
            tracker.track_invocation(
                "skill:gmail-skill",
                session_id=f"s{i}",
                duration_ms=100 + i,
                platform="claude",
            )
    finally:
        tracker.close()

    result = runner.invoke(cli, ["stats", "--days", "30", "--detailed"])
    assert result.exit_code == 0
    assert "Most Used Components" in result.output
    assert "Recent Installations" in result.output
    assert "Performance (avg execution time)" in result.output
    assert "Extended Metrics" in result.output
    assert "User Activity" in result.output
    assert "Event Queue Analytics" in result.output
    assert "Insights Analytics" in result.output
    assert "Session Analytics" in result.output
    assert "Task Analytics" in result.output
    assert "Token Analytics" in result.output
    assert "Cache efficiency" in result.output
    assert "Agentic Growth" in result.output


def test_cli_list_json_search_filters_and_export_json(
    mock_claude_home: Path, tmp_path: Path
) -> None:
    _seed_core_components(mock_claude_home)
    runner = CliRunner()

    # Populate DB.
    result = runner.invoke(
        cli,
        ["scan", "--platform", "claude", "--claude-home", str(mock_claude_home), "--sequential"],
    )
    assert result.exit_code == 0

    # List as JSON
    result = runner.invoke(cli, ["list", "--platform", "claude", "--json"])
    assert result.exit_code == 0
    assert "gmail-skill" in result.output

    # Search filtered by type
    result = runner.invoke(cli, ["search", "gmail", "--platform", "claude", "--type", "skill"])
    assert result.exit_code == 0
    assert "gmail-skill" in result.output

    # Search no-results branch
    result = runner.invoke(cli, ["search", "nope"])
    assert result.exit_code == 0
    assert "No components found" in result.output

    # Export JSON default output path.
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "export",
                "--format",
                "json",
                "--platform",
                "claude",
                "--claude-home",
                str(mock_claude_home),
            ],
        )
        assert result.exit_code == 0
        assert Path("tooling-index.json").exists()

    # Export JSON to explicit output path.
    out_json = tmp_path / "tooling.json"
    result = runner.invoke(
        cli,
        [
            "export",
            "--format",
            "json",
            "--output",
            str(out_json),
            "--platform",
            "claude",
            "--claude-home",
            str(mock_claude_home),
        ],
    )
    assert result.exit_code == 0
    assert out_json.exists()


def test_cli_tui_import_error_path(
    mock_claude_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("textual"):
            raise ImportError("textual not installed")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = runner.invoke(
        cli,
        ["tui", "--platform", "claude", "--claude-home", str(mock_claude_home)],
    )
    assert result.exit_code != 0
    assert "TUI requires 'textual' package" in result.output


def test_cli_scan_value_error_when_claude_home_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Patch home but do not create ~/.claude so ToolingScanner auto-detect fails.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    runner = CliRunner()

    result = runner.invoke(cli, ["scan", "--sequential", "--no-db"])
    assert result.exit_code != 0
    assert "Install Claude Code first" in result.output


def test_cli_scan_unexpected_exception_path(
    mock_claude_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude_tooling_index import multi_scanner

    monkeypatch.setattr(
        multi_scanner.MultiToolingScanner, "scan_all", lambda *args, **kwargs: 1 / 0
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["scan", "--platform", "claude", "--claude-home", str(mock_claude_home), "--sequential"],
    )
    assert result.exit_code != 0
    assert "Unexpected error" in result.output
