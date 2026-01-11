from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from claude_tooling_index.scanners import (
    BinaryScanner,
    CommandScanner,
    EventQueueScanner,
    GrowthScanner,
    HookScanner,
    InsightsScanner,
    MCPScanner,
    PluginScanner,
    SessionAnalyticsScanner,
    SkillScanner,
    TodoScanner,
    TranscriptScanner,
    UserSettingsScanner,
)


def test_skill_scanner_scans_active_and_disabled(mock_claude_home: Path) -> None:
    skills_dir = mock_claude_home / "skills"

    active_dir = skills_dir / "active-skill"
    active_dir.mkdir(parents=True)
    (active_dir / "SKILL.md").write_text(
        """---
name: active-skill
version: 1.0.0
description: Active skill
metadata:
  short-description: Active skill short
---

# Claude slash command: /active
**Alias:** `/active`
**Arguments:** first argument after the command token (treat remainder as $1)

Implement the plan from: @$1

## When to use
- When you need to email
- When you need a calendar event

## Trigger rules
- Run after planning docs are updated

## Inputs
- recipient_email: Who to email
- calendar_date - When to schedule

## Outputs
- sent_email: Confirmation
- event_id: Created calendar event id

## Safety
- Never paste secrets into email body
- Redact API keys

```python
run_composio_tool("GMAIL_SEND_EMAIL", {"to": "x"})
```

```sql
-- demo MCP
select 1; -- mcp__neon__run_sql
```

# Active Skill
"""
    )
    (active_dir / "main.py").write_text("print('hi')\n")
    (active_dir / "requirements.txt").write_text("requests>=2\n# comment\n")
    (active_dir / "pyproject.toml").write_text(
        "[project]\ndependencies = ['rich>=13', 'textual']\n"
    )
    (active_dir / "package.json").write_text('{"dependencies": {"left-pad": "^1"}}')

    disabled_dir = skills_dir / ".disabled" / "disabled-skill"
    disabled_dir.mkdir(parents=True)
    (disabled_dir / "SKILL.md").write_text("---\nname: disabled-skill\n---\n")

    scanner = SkillScanner(skills_dir)
    skills = scanner.scan()

    by_name = {s.name: s for s in skills}
    assert by_name["active-skill"].status == "active"
    assert by_name["disabled-skill"].status == "disabled"
    assert by_name["active-skill"].file_count >= 2
    assert "requests>=2" in by_name["active-skill"].dependencies
    assert "rich>=13" in by_name["active-skill"].dependencies
    assert "textual" in by_name["active-skill"].dependencies
    assert "left-pad@^1" in by_name["active-skill"].dependencies
    assert "requirements.txt" in by_name["active-skill"].dependency_sources
    assert "pyproject.toml" in by_name["active-skill"].dependency_sources
    assert "package.json" in by_name["active-skill"].dependency_sources
    assert by_name["active-skill"].frontmatter_extra["metadata"]["short-description"] == "Active skill short"
    assert "/active" in by_name["active-skill"].invocation_aliases
    assert "$1" in by_name["active-skill"].invocation_arguments
    assert by_name["active-skill"].invocation_instruction == "Implement the plan from: @$1"
    assert by_name["active-skill"].references["files"] == ["@$1"]
    assert "When you need to email" in by_name["active-skill"].when_to_use
    assert by_name["active-skill"].trigger_rules == ["Run after planning docs are updated"]
    assert "mcp__neon__run_sql" in by_name["active-skill"].detected_tools["mcp_tools"]
    assert "GMAIL_SEND_EMAIL" in by_name["active-skill"].detected_tools["composio_tools"]
    assert "neon" in by_name["active-skill"].detected_toolkits
    assert "gmail" in by_name["active-skill"].detected_toolkits
    assert by_name["active-skill"].inputs[:2] == [
        "recipient_email: Who to email",
        "calendar_date: When to schedule",
    ]
    assert by_name["active-skill"].outputs[:2] == [
        "sent_email: Confirmation",
        "event_id: Created calendar event id",
    ]
    assert "Redact API keys" in by_name["active-skill"].safety_notes
    assert "email" in by_name["active-skill"].capability_tags
    assert "database" in by_name["active-skill"].capability_tags


def test_command_scanner_reads_frontmatter(mock_claude_home: Path) -> None:
    cmd_path = mock_claude_home / "commands" / "hello.md"
    cmd_path.write_text(
        """---
description: Says hello
tags:
  - t1
timeout: 30
---

# /hello
"""
    )

    scanner = CommandScanner(mock_claude_home / "commands")
    commands = scanner.scan()

    assert len(commands) == 1
    assert commands[0].name == "hello"
    assert commands[0].description == "Says hello"
    assert commands[0].frontmatter_extra == {"tags": ["t1"], "timeout": 30}


def test_command_scanner_scans_disabled_commands(mock_claude_home: Path) -> None:
    disabled_cmd = mock_claude_home / "commands" / ".disabled" / "hidden.md"
    disabled_cmd.parent.mkdir(parents=True, exist_ok=True)
    disabled_cmd.write_text("# /hidden\n")

    commands = CommandScanner(mock_claude_home / "commands").scan()
    by_name = {c.name: c for c in commands}
    assert by_name["hidden"].status == "disabled"


def test_plugin_scanner_supports_v2_format(mock_claude_home: Path, tmp_path: Path) -> None:
    install_dir = tmp_path / "plugin-install"
    install_dir.mkdir()

    plugins_file = mock_claude_home / "plugins" / "installed_plugins.json"
    plugins_file.write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "my-plugin@custom": [
                        {
                            "installPath": str(install_dir),
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

    cache_root = mock_claude_home / "plugins" / "cache" / "custom" / "my-plugin"
    plugin_json = cache_root / ".claude-plugin" / "plugin.json"
    plugin_json.parent.mkdir(parents=True, exist_ok=True)
    plugin_json.write_text(
        json.dumps(
            {
                "name": "my-plugin",
                "description": "Plugin description",
                "author": "Me",
                "homepage": "https://example.com",
                "repository": {"url": "https://github.com/example/repo"},
                "license": "MIT",
                "commands": {"hello": {"description": "Says hi"}},
                "mcpServers": {
                    "srv": {
                        "command": "python3",
                        "args": [],
                        "env": {"API_KEY": "${API_KEY}", "SECRET": "x"},
                    }
                },
            }
        )
    )

    versioned = cache_root / "1.0.0"
    versioned.mkdir(parents=True, exist_ok=True)
    (versioned / ".mcp.json").write_text(
        json.dumps({"m1": {"command": "python3", "args": []}})
    )

    scanner = PluginScanner(mock_claude_home / "plugins")
    plugins = scanner.scan()

    assert len(plugins) == 1
    assert plugins[0].name == "my-plugin"
    assert plugins[0].marketplace == "custom"
    assert plugins[0].status == "active"
    assert plugins[0].description == "Plugin description"
    assert plugins[0].author == "Me"
    assert plugins[0].homepage == "https://example.com"
    assert plugins[0].repository == "https://github.com/example/repo"
    assert plugins[0].license == "MIT"
    assert "hello" in plugins[0].provides_commands
    assert "plugin:my-plugin:srv" in plugins[0].provides_mcps
    assert "plugin:my-plugin:m1" in plugins[0].provides_mcps
    assert plugins[0].commands_detail["hello"] == "Says hi"
    assert "API_KEY" in plugins[0].mcps_detail["srv"]["env_keys"]
    assert "SECRET" in plugins[0].mcps_detail["srv"]["env_keys"]
    assert plugins[0].mcps_detail["srv"]["env_placeholders"] == ["API_KEY"]


def test_command_scanner_includes_plugin_commands(mock_claude_home: Path) -> None:
    cache_root = mock_claude_home / "plugins" / "cache" / "custom" / "p1"
    plugin_json = cache_root / ".claude-plugin" / "plugin.json"
    plugin_json.parent.mkdir(parents=True, exist_ok=True)
    plugin_json.write_text(
        json.dumps(
            {
                "name": "p1",
                "commands": {"hello": {"description": "Hi"}},
            }
        )
    )

    cmds = CommandScanner(mock_claude_home / "commands").scan()
    by_name = {c.name: c for c in cmds}
    assert "plugin:p1:hello" in by_name
    assert by_name["plugin:p1:hello"].from_plugin == "p1"
    assert "/hello" in by_name["plugin:p1:hello"].invocation_aliases


def test_hook_and_binary_scanners_detect_language_and_executable(mock_claude_home: Path) -> None:
    hook_file = mock_claude_home / "hooks" / "post_tool_use_tooling.py"
    hook_file.write_text(
        "#!/usr/bin/env python3\n"
        "print('hook')\n"
        "print('mcp__neon__run_sql')\n"
        "print('${API_KEY}')\n"
    )

    hook_scanner = HookScanner(mock_claude_home / "hooks")
    hooks = hook_scanner.scan()
    by_name = {h.name: h for h in hooks}
    assert by_name["post_tool_use_tooling.py"].language == "python"
    assert by_name["post_tool_use_tooling.py"].origin in {"official", "in-house"}
    assert by_name["post_tool_use_tooling.py"].trigger_event == "post_tool_use"
    assert by_name["post_tool_use_tooling.py"].shebang.startswith("#!")
    assert "API_KEY" in by_name["post_tool_use_tooling.py"].required_env_vars
    assert "mcp__neon__run_sql" in by_name["post_tool_use_tooling.py"].detected_tools["mcp_tools"]

    disabled_hook = mock_claude_home / "hooks" / ".disabled" / "disabled.py"
    disabled_hook.parent.mkdir(parents=True, exist_ok=True)
    disabled_hook.write_text("#!/usr/bin/env python3\nprint('x')\n")
    hooks = hook_scanner.scan()
    by_name = {h.name: h for h in hooks}
    assert by_name["disabled.py"].status == "disabled"

    bin_file = mock_claude_home / "bin" / "hello"
    bin_file.write_text("#!/usr/bin/env bash\necho hi\n")
    os.chmod(bin_file, 0o755)

    bin_scanner = BinaryScanner(mock_claude_home / "bin")
    binaries = bin_scanner.scan()
    by_name = {b.name: b for b in binaries}
    assert by_name["hello"].is_executable is True

    disabled_bin = mock_claude_home / "bin" / ".disabled" / "disabled-bin"
    disabled_bin.parent.mkdir(parents=True, exist_ok=True)
    disabled_bin.write_text("#!/usr/bin/env bash\necho x\n")
    os.chmod(disabled_bin, 0o755)
    binaries = bin_scanner.scan()
    by_name = {b.name: b for b in binaries}
    assert by_name["disabled-bin"].status == "disabled"


def test_mcp_scanner_scans_disabled_mcps(tmp_path: Path, mock_claude_home: Path) -> None:
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "enabled": {
                        "command": "echo",
                        "args": ["hi"],
                        "env": {"API_KEY": "secret", "PLACEHOLDER": "${KEY}"},
                    }
                },
                "mcpServersDisabled": {
                    "disabled": {
                        "command": "echo",
                        "args": ["x"],
                        "env": {"TOKEN": "secret2"},
                    }
                },
                "projects": {},
            }
        )
    )

    mcps = MCPScanner(mock_claude_home / "mcp.json").scan()
    by_name = {m.name: m for m in mcps}
    assert by_name["enabled"].status == "active"
    assert by_name["disabled"].status == "disabled"
    assert by_name["enabled"].source == "user"
    assert by_name["enabled"].source_detail == "~/.claude.json:mcpServers.enabled"
    assert by_name["disabled"].source_detail == "~/.claude.json:mcpServersDisabled.disabled"
    assert by_name["enabled"].env_vars["API_KEY"] == "<redacted>"
    assert by_name["enabled"].env_vars["PLACEHOLDER"] == "${KEY}"
    assert by_name["disabled"].env_vars["TOKEN"] == "<redacted>"


def test_event_queue_scanner_extracts_basic_metrics(mock_claude_home: Path) -> None:
    event_queue = mock_claude_home / "data" / "event_queue.jsonl"
    event_queue.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "hook_event_type": "PostToolUse",
                        "timestamp": 1_700_000_000_000,
                        "session_id": "s1",
                        "payload": {
                            "permission_mode": "auto",
                            "tool_name": "read_file",
                        },
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

    scanner = EventQueueScanner(event_queue)
    metrics = scanner.scan()
    assert metrics is not None
    assert metrics.total_events == 2
    assert metrics.session_count == 2
    assert metrics.tool_frequency["read_file"] == 1


def test_user_settings_scanner_parses_basic_fields(tmp_path: Path, mock_claude_home: Path) -> None:
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps(
            {
                "numStartups": 10,
                "firstStartTime": "2026-01-01T00:00:00Z",
                "memoryUsageCount": 2,
                "promptQueueUseCount": 3,
                "skillUsage": {
                    "a-skill": {"usageCount": 5, "lastUsedAt": 1_700_000_000_000},
                },
                "projects": {},
            }
        )
    )

    scanner = UserSettingsScanner()
    settings = scanner.scan()
    assert settings is not None
    assert settings.total_startups == 10
    assert settings.memory_usage_count == 2
    assert "a-skill" in settings.skill_usage


def test_sessions_and_todos_scanners_read_json(tmp_path: Path, mock_claude_home: Path) -> None:
    sessions_dir = mock_claude_home / "data" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "s1.json").write_text(
        json.dumps({"prompts": ["hi", "there"], "source_app": "my-project"})
    )

    sm = SessionAnalyticsScanner(sessions_dir).scan()
    assert sm is not None
    assert sm.total_sessions == 1
    assert sm.prompts_per_session == 2.0

    todos_dir = mock_claude_home / "todos"
    todos_dir.mkdir(parents=True, exist_ok=True)
    (todos_dir / "todos.json").write_text(
        json.dumps(
            [
                {"status": "completed"},
                {"status": "pending"},
                {"status": "in_progress"},
            ]
        )
    )
    tm = TodoScanner(todos_dir).scan()
    assert tm is not None
    assert tm.total_tasks == 3
    assert tm.completed == 1


def test_transcript_scanner_extracts_tokens_and_models(mock_claude_home: Path) -> None:
    project_dir = mock_claude_home / "projects" / "demo"
    project_dir.mkdir(parents=True)

    transcript = project_dir / "session.jsonl"
    transcript.write_text(
        "\n".join(
            [
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
                            "content": [
                                {"type": "tool_use", "name": "read_file"},
                                {"type": "text", "text": "hi"},
                            ],
                        },
                    }
                )
            ]
        )
        + "\n"
    )

    metrics = TranscriptScanner(mock_claude_home / "projects").scan(sample_limit=10)
    assert metrics is not None
    assert metrics.total_input_tokens == 10
    assert metrics.model_usage["gpt-test"] == 1
    assert metrics.tool_usage["read_file"] == 1


def test_growth_scanner_counts_edges_patterns_and_level(mock_claude_home: Path) -> None:
    growth_dir = mock_claude_home / "agentic-growth"
    edges_dir = growth_dir / "edges" / "category-a"
    patterns_dir = growth_dir / "patterns" / "category-b"
    edges_dir.mkdir(parents=True)
    patterns_dir.mkdir(parents=True)
    (edges_dir / "EDGE-001.md").write_text("# Edge\n")
    (patterns_dir / "PATTERN-001.md").write_text("# Pattern\n")
    (growth_dir / "progression.md").write_text("L4: Meta-Engineer *CURRENT LEVEL*\n")
    (growth_dir / "project-edges.json").write_text(json.dumps({"proj": ["EDGE-001"]}))

    gm = GrowthScanner(growth_dir).scan()
    assert gm is not None
    assert gm.current_level == "L4"
    assert gm.total_edges >= 1
    assert gm.total_patterns >= 1
    assert gm.projects_with_edges == 1


def test_insights_scanner_and_search(tmp_path: Path, mock_claude_home: Path) -> None:
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
        conn.execute(
            "INSERT INTO insights VALUES ('warning', '/x/proj', 'danger zone', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO insights VALUES ('pattern', '/x/proj', 'a pattern', datetime('now'))"
        )
        conn.execute("CREATE TABLE processed_sessions (id TEXT)")
        conn.execute("INSERT INTO processed_sessions VALUES ('s1')")

        # Optional FTS for search path
        conn.execute("CREATE VIRTUAL TABLE insights_fts USING fts5(insight_text)")
        conn.execute("INSERT INTO insights_fts(rowid, insight_text) VALUES (1, 'danger zone')")
        conn.execute("INSERT INTO insights_fts(rowid, insight_text) VALUES (2, 'a pattern')")
        conn.commit()
    finally:
        conn.close()

    scanner = InsightsScanner(db_path)
    metrics = scanner.scan()
    assert metrics is not None
    assert metrics.total_insights == 2
    assert metrics.processed_sessions == 1

    results = scanner.search_insights("danger", limit=5)
    assert results
    assert results[0]["category"] == "warning"


def test_mcp_scanner_reads_user_project_plugin_and_legacy(mock_claude_home: Path, tmp_path: Path) -> None:
    # User-level + project-level MCPs live in ~/.claude.json (Path.home() is patched).
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps(
            {
                "mcpServers": {"user-mcp": {"command": "python3", "args": ["-m", "mcp"]}},
                "projects": {
                    str(mock_claude_home): {
                        "mcpServers": {"proj-mcp": {"command": "echo", "args": ["hi"]}}
                    }
                },
            }
        )
    )

    # Legacy ~/.claude/mcp.json
    (mock_claude_home / "mcp.json").write_text(
        json.dumps({"mcpServers": {"legacy-mcp": {"command": "node", "args": ["srv"]}}})
    )

    # Built-in: Chrome host.
    chrome_host = mock_claude_home / "chrome" / "chrome-native-host"
    chrome_host.parent.mkdir(parents=True)
    chrome_host.write_text("x")

    # Plugin-provided MCP via .mcp.json.
    plugin_root = (
        mock_claude_home / "plugins" / "cache" / "marketplace" / "p1" / "1.0.0"
    )
    plugin_root.mkdir(parents=True)
    (plugin_root / ".mcp.json").write_text(
        json.dumps(
            {
                "p-mcp": {
                    "command": "python3",
                    "args": ["${CLAUDE_PLUGIN_ROOT}/server.py"],
                }
            }
        )
    )

    scanner = MCPScanner(mock_claude_home / "mcp.json")
    mcps = scanner.scan()

    names = {m.name for m in mcps}
    assert {"user-mcp", "proj-mcp", "legacy-mcp", "claude-in-chrome"}.issubset(names)
