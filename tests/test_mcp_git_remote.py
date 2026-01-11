from __future__ import annotations

import json
from pathlib import Path

from claude_tooling_index.scanners.mcps import MCPScanner


def test_mcp_scanner_populates_git_remote(tmp_path: Path, mock_claude_home: Path) -> None:
    # Create a fake git repo with origin remote.
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text(
        """
[remote "origin"]
    url = https://example.com/repo.git
"""
    )
    cmd = repo / "bin" / "server"
    cmd.parent.mkdir(parents=True)
    cmd.write_text("#!/usr/bin/env bash\necho hi\n")

    # Configure an MCP that points at the command inside the repo.
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "git-mcp": {
                        "command": str(cmd),
                        "args": [],
                        "env": {},
                    }
                },
                "projects": {},
            }
        )
    )

    mcps = MCPScanner(mock_claude_home / "mcp.json").scan()
    by_name = {m.name: m for m in mcps}
    assert by_name["git-mcp"].git_remote == "https://example.com/repo.git"

