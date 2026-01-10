"""MCP scanner - extracts metadata from mcp.json"""

import json
from pathlib import Path
from datetime import datetime
from typing import List

from ..models import MCPMetadata


class MCPScanner:
    """Scans ~/.claude/mcp.json for MCP server configurations"""

    def __init__(self, mcp_json_path: Path):
        self.mcp_json_path = mcp_json_path

    def scan(self) -> List[MCPMetadata]:
        """Scan MCP servers from mcp.json"""
        mcps = []

        if not self.mcp_json_path.exists():
            return mcps

        try:
            with open(self.mcp_json_path, "r") as f:
                data = json.load(f)

            # mcp.json format: { "mcpServers": { "name": { config } } }
            mcp_servers = data.get("mcpServers", {})

            for name, config in mcp_servers.items():
                try:
                    mcp = self._parse_mcp_config(name, config)
                    if mcp:
                        mcps.append(mcp)
                except Exception as e:
                    # Track error but continue
                    error_mcp = MCPMetadata(
                        name=name,
                        origin="unknown",
                        status="error",
                        last_modified=datetime.now(),
                        install_path=self.mcp_json_path,
                        error_message=str(e),
                    )
                    mcps.append(error_mcp)

        except (json.JSONDecodeError, OSError) as e:
            # If mcp.json is corrupted, return empty list
            pass

        return mcps

    def _parse_mcp_config(self, name: str, config: dict) -> MCPMetadata:
        """Parse a single MCP server configuration"""
        command = config.get("command", "")
        args = config.get("args", [])
        env_vars = config.get("env", {})
        transport = config.get("transport", "stdio")

        # Detect origin from name or command
        origin = self._detect_origin(name, command)

        # MCP servers are active if defined in mcp.json
        status = "active"

        # Use mcp.json's modification time
        last_modified = datetime.fromtimestamp(
            self.mcp_json_path.stat().st_mtime
        )

        # Install path could be the command path if local
        install_path = Path(command).expanduser() if command else self.mcp_json_path

        return MCPMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=install_path,
            command=command,
            args=args,
            env_vars=env_vars,
            transport=transport,
            git_remote=None,  # TODO: Detect git remote if local repo
        )

    def _detect_origin(self, name: str, command: str) -> str:
        """Detect MCP origin from name or command"""
        name_lower = name.lower()
        command_lower = command.lower()

        # Official: Anthropic/Claude
        if "anthropic" in name_lower or "claude" in name_lower:
            return "official"

        # Community: modelcontextprotocol repos
        if "modelcontextprotocol" in command_lower:
            return "community"

        # In-house: Local paths
        if command.startswith("/") or command.startswith("~"):
            # Local file path
            return "in-house"

        # External: npx or other package managers
        return "external"
