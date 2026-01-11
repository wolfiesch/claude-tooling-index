from __future__ import annotations

import json
from pathlib import Path

from claude_tooling_index.scanners import MCPScanner


def test_mcp_scanner_covers_http_origin_duplicates_and_plugin_json(
    mock_claude_home: Path, tmp_path: Path
) -> None:
    # User + project MCPs live in ~/.claude.json (Path.home() patched by fixtures).
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "anthropic-mcp": {
                        "command": "python3",
                        "args": ["-m", "x"],
                        "timeout": 5,
                        "token": "abcdef0123456789abcdef0123456789",
                        "id": "0123456789abcdef0123456789abcdef",
                        "headers": {"Authorization": "Bearer SECRET"},
                    },
                    "http-mcp": {"url": "https://example.com/mcp"},
                    "inhouse-mcp": {"command": "~/.local/bin/mcp", "args": []},
                    "dup-mcp": {"command": "python3", "args": []},
                },
                "projects": {
                    str(mock_claude_home): {
                        "mcpServers": {"local-mcp": {"command": "echo", "args": ["hi"]}}
                    }
                },
            }
        )
    )

    # Legacy ~/.claude/mcp.json includes a duplicate to exercise seen_names skip.
    (mock_claude_home / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "dup-mcp": {"command": "python3", "args": []},
                    "external-mcp": {"command": "npx", "args": ["some-pkg"]},
                }
            }
        )
    )

    # Built-in: Chrome host.
    chrome_host = mock_claude_home / "chrome" / "chrome-native-host"
    chrome_host.parent.mkdir(parents=True, exist_ok=True)
    chrome_host.write_text("x")

    # Plugin cache: non-versioned plugin.json
    plugin_root = mock_claude_home / "plugins" / "cache" / "mkt" / "p2"
    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    plugin_json.parent.mkdir(parents=True, exist_ok=True)
    plugin_json.write_text(
        json.dumps(
            {
                "name": "p2",
                "mcpServers": {
                    "srv": {
                        "command": "python3",
                        "args": ["${CLAUDE_PLUGIN_ROOT}/server.py"],
                        "env": {"BIN": "${CLAUDE_PLUGIN_ROOT}/bin"},
                    }
                },
            }
        )
    )

    # Plugin cache: versioned plugin.json
    plugin_root_v = mock_claude_home / "plugins" / "cache" / "mkt" / "p3" / "1.0.0"
    plugin_json_v = plugin_root_v / ".claude-plugin" / "plugin.json"
    plugin_json_v.parent.mkdir(parents=True, exist_ok=True)
    plugin_json_v.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "srv2": {
                        "command": "python3",
                        "args": ["${CLAUDE_PLUGIN_ROOT}/srv2.py"],
                    }
                }
            }
        )
    )

    # Plugin cache: .mcp.json file
    plugin_root_mcp = mock_claude_home / "plugins" / "cache" / "mkt" / "p4" / "1.0.0"
    plugin_root_mcp.mkdir(parents=True, exist_ok=True)
    (plugin_root_mcp / ".mcp.json").write_text(
        json.dumps(
            {
                "m1": {
                    "command": "python3",
                    "args": ["${CLAUDE_PLUGIN_ROOT}/m1.py"],
                    "env": {"A": "${CLAUDE_PLUGIN_ROOT}/a"},
                }
            }
        )
    )

    mcps = MCPScanner(mock_claude_home / "mcp.json").scan()
    by_name = {m.name: m for m in mcps}

    assert by_name["anthropic-mcp"].origin == "official"
    assert by_name["anthropic-mcp"].config_extra["timeout"] == 5
    assert by_name["anthropic-mcp"].config_extra["token"] == "<redacted>"
    assert by_name["anthropic-mcp"].config_extra["id"] == "<redacted>"
    assert (
        by_name["anthropic-mcp"].config_extra["headers"]["Authorization"]
        == "<redacted>"
    )
    assert by_name["local-mcp"].origin == "local"
    assert by_name["http-mcp"].transport == "http"
    assert by_name["http-mcp"].command.startswith("https://")
    assert by_name["claude-in-chrome"].transport == "native-messaging"

    p2 = by_name["plugin:p2:srv"]
    assert p2.origin == "plugin"
    assert str(plugin_root) in p2.args[0]
    assert str(plugin_root) in p2.env_vars["BIN"]

    p4 = by_name["plugin:p4:m1"]
    assert p4.origin == "plugin"
    assert str(plugin_root_mcp) in p4.args[0]
    assert str(plugin_root_mcp) in p4.env_vars["A"]
