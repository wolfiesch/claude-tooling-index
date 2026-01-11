from __future__ import annotations

from datetime import datetime
from pathlib import Path

from claude_tooling_index.scanners.commands import CommandScanner


def test_command_scanner_extracts_rich_metadata(tmp_path: Path, monkeypatch) -> None:
    # Ensure plugin cache scan doesn't depend on a real home.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    claude_home = tmp_path / ".claude"
    commands_dir = claude_home / "commands"
    plugins_cache = claude_home / "plugins" / "cache" / "custom" / "p1" / ".claude-plugin"
    commands_dir.mkdir(parents=True)
    plugins_cache.mkdir(parents=True)

    # Plugin command source
    (plugins_cache / "plugin.json").write_text(
        """
{"name":"p1","commands":{"hello":{"description":"Hi"}}}
"""
    )

    cmd_file = commands_dir / "email.md"
    cmd_file.write_text(
        """---
description: Sends an email
timeout: 30
---

# /email
**Arguments:** first arg is recipient (treat remainder as $1)

Implement the plan from: @$1

Use @CLAUDE.md and $other-skill.

## Inputs
- recipient_email: Who to email
- api_key: From ${API_KEY}

## Outputs
- sent_email: Confirmation

## Safety
- Redact ${API_KEY}

## Install
- brew install x

```bash
pip install y
export API_KEY=secret
```

## Gotchas
- Beware rate limits

## Example
```python
run_composio_tool("GMAIL_SEND_EMAIL", {"to": "x"})
```

```sql
select 1; -- mcp__neon__run_sql
```
"""
    )

    disabled_dir = commands_dir / ".disabled"
    disabled_dir.mkdir()
    (disabled_dir / "hidden.md").write_text("# /hidden\n")

    scanned = CommandScanner(commands_dir).scan()
    by_name = {c.name: c for c in scanned}

    assert "email" in by_name
    assert by_name["email"].status == "active"
    assert by_name["hidden"].status == "disabled"
    assert "/email" in by_name["email"].invocation_aliases
    assert by_name["email"].invocation_arguments
    assert by_name["email"].invocation_instruction.startswith("Implement")
    assert "API_KEY" in by_name["email"].required_env_vars
    assert "brew install x" in by_name["email"].prerequisites
    assert "Beware rate limits" in by_name["email"].gotchas
    assert "GMAIL_SEND_EMAIL" in by_name["email"].detected_tools["composio_tools"]
    assert "mcp__neon__run_sql" in by_name["email"].detected_tools["mcp_tools"]
    assert "email" in by_name["email"].capability_tags
    assert "database" in by_name["email"].capability_tags
    assert by_name["email"].risk_level in {"medium", "high", "low"}

    # Plugin command exposed without colliding with DB identity.
    assert "plugin:p1:hello" in by_name
    assert by_name["plugin:p1:hello"].from_plugin == "p1"
    assert "/hello" in by_name["plugin:p1:hello"].invocation_aliases


def test_command_metadata_is_serializable_defaults(tmp_path: Path) -> None:
    # Coverage for basic CommandMetadata defaults via scan of minimal file.
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "x.md").write_text("# /x\n")
    cmd = CommandScanner(commands_dir).scan()[0]
    assert cmd.last_modified <= datetime.now()

