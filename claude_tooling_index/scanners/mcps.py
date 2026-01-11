"""MCP scanner - extracts metadata from all MCP sources."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import MCPMetadata

_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|bearer|authorization|auth|cookie)"
)
_HEX_TOKEN_RE = re.compile(r"(?i)^[0-9a-f]{32,}$")
_B64_TOKEN_RE = re.compile(r"^[A-Za-z0-9+/=_-]{32,}$")


def _redact_env_vars(env: dict) -> dict:
    redacted = {}
    for key, value in (env or {}).items():
        if value is None:
            redacted[str(key)] = ""
            continue
        if isinstance(value, str):
            # Preserve placeholders and common non-secret path-like values for usability.
            if value.startswith("${") and value.endswith("}"):
                redacted[str(key)] = value
                continue
            if value.startswith(("/", "~", "./", "../")):
                redacted[str(key)] = value
                continue
        redacted[str(key)] = "<redacted>"
    return redacted


def _redact_extra_config(value: object, *, key: str = "") -> object:
    """Redact unknown MCP config fields conservatively to avoid leaking secrets."""
    if value is None or isinstance(value, (bool, int, float)):
        return value

    key_str = str(key or "")
    if _SENSITIVE_KEY_RE.search(key_str):
        return "<redacted>"

    if isinstance(value, str):
        if value.startswith("${") and value.endswith("}"):
            return value
        if value.startswith(("/", "~", "./", "../")):
            return value
        # Heuristic: redact high-entropy token-like strings.
        compact = value.strip()
        if len(compact) >= 32 and (  # tokens tend to be long and space-free
            _HEX_TOKEN_RE.match(compact) or _B64_TOKEN_RE.match(compact)
        ):
            return "<redacted>"
        return value

    if isinstance(value, list):
        return [_redact_extra_config(v, key=key_str) for v in value]

    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out[str(k)] = _redact_extra_config(v, key=str(k))
        return out

    return str(value)


def _pretty_path(path: Path) -> str:
    """Render a path relative to the current user's home for display."""
    try:
        home = str(Path.home())
        p = str(path)
        if p.startswith(home):
            return "~" + p[len(home) :]
        return p
    except Exception:  # pragma: no cover
        return str(path)


def _find_git_remote(path: Path) -> Optional[str]:
    """Best-effort: find a git remote URL for a path by walking up to `.git/config`."""
    try:
        cur = path
        if cur.is_file():
            cur = cur.parent

        # Walk up until filesystem root.
        while True:
            git_dir = cur / ".git"
            config_path = git_dir / "config"
            if git_dir.is_dir() and config_path.exists():
                text = config_path.read_text(errors="ignore")
                current_remote = None
                remotes = {}
                for line in text.splitlines():
                    m = re.match(r'^\s*\[remote\s+"([^"]+)"\]\s*$', line)
                    if m:
                        current_remote = m.group(1)
                        continue
                    m2 = re.match(r"^\s*url\s*=\s*(.+)\s*$", line)
                    if m2 and current_remote:
                        remotes[current_remote] = m2.group(1).strip()
                        continue

                if "origin" in remotes:
                    return remotes["origin"]
                if remotes:
                    # Return first remote by insertion order.
                    return next(iter(remotes.values()))
                return None

            if cur.parent == cur:
                break
            cur = cur.parent
    except Exception:
        return None
    return None


class MCPScanner:
    """Scan MCP server configurations from all sources.

    1. User-level MCPs: ~/.claude.json -> mcpServers
    2. Project-specific MCPs: ~/.claude.json -> projects.<path>.mcpServers
    3. Plugin-provided MCPs: plugin.json -> mcpServers
    4. Legacy: ~/.claude/mcp.json
    """

    def __init__(self, mcp_json_path: Path):
        self.mcp_json_path = mcp_json_path  # ~/.claude/mcp.json
        self.claude_json_path = Path.home() / ".claude.json"
        self.claude_home = Path.home() / ".claude"
        self.plugins_cache = self.claude_home / "plugins" / "cache"
        self.redact_env = True

    def scan(self) -> List[MCPMetadata]:
        """Scan MCP servers from all config locations."""
        mcps = []
        seen_names = set()

        # 1. Scan user-level MCPs from ~/.claude.json
        mcps.extend(self._scan_user_mcps(seen_names))

        # 2. Scan project-specific MCPs for ~/.claude directory
        mcps.extend(self._scan_project_mcps(seen_names))

        # 3. Scan plugin-provided MCPs
        mcps.extend(self._scan_plugin_mcps(seen_names))

        # 4. Scan legacy ~/.claude/mcp.json
        mcps.extend(self._scan_legacy_mcp_json(seen_names))

        # 5. Detect built-in MCPs (Chrome extension, etc.)
        mcps.extend(self._scan_builtin_mcps(seen_names))

        return mcps

    def _scan_builtin_mcps(self, seen_names: set) -> List[MCPMetadata]:
        """Detect built-in MCPs like `claude-in-chrome`."""
        mcps = []

        # Check for Claude-in-Chrome extension
        chrome_host = self.claude_home / "chrome" / "chrome-native-host"
        if chrome_host.exists():
            name = "claude-in-chrome"
            if name not in seen_names:
                seen_names.add(name)
                mcps.append(
                    MCPMetadata(
                        name=name,
                        origin="official",
                        status="active",
                        last_modified=datetime.fromtimestamp(
                            chrome_host.stat().st_mtime
                        ),
                        install_path=chrome_host,
                        command="chrome-extension",
                        args=[],
                        env_vars={},
                        transport="native-messaging",
                        source="builtin",
                        source_detail=f"detected:{_pretty_path(chrome_host)}",
                        git_remote=None,
                    )
                )

        return mcps

    def _scan_user_mcps(self, seen_names: set) -> List[MCPMetadata]:
        """Scan user-level MCPs from `~/.claude.json` -> `mcpServers`."""
        mcps = []

        if not self.claude_json_path.exists():
            return mcps

        try:
            with open(self.claude_json_path, "r") as f:
                data = json.load(f)

            active_servers = data.get("mcpServers", {}) or {}
            disabled_servers = data.get("mcpServersDisabled", {}) or {}

            for status, mcp_servers in [
                ("active", active_servers),
                ("disabled", disabled_servers),
            ]:
                if not isinstance(mcp_servers, dict):
                    continue
                for name, config in mcp_servers.items():
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    mcp = self._parse_mcp_config(
                        name,
                        config,
                        self.claude_json_path,
                        "user",
                        status=status,
                        source_detail=(
                            f"{_pretty_path(self.claude_json_path)}:"
                            f"{'mcpServers' if status == 'active' else 'mcpServersDisabled'}."
                            f"{name}"
                        ),
                    )
                    if mcp:
                        mcps.append(mcp)

        except (json.JSONDecodeError, OSError):
            pass

        return mcps

    def _scan_project_mcps(self, seen_names: set) -> List[MCPMetadata]:
        """Scan project-specific MCPs from `projects.<path>.mcpServers`."""
        mcps = []

        if not self.claude_json_path.exists():
            return mcps

        try:
            with open(self.claude_json_path, "r") as f:
                data = json.load(f)

            projects = data.get("projects", {})

            # Look for MCPs specific to ~/.claude directory
            project_key = str(self.claude_home)
            if project_key in projects:
                project_config = projects[project_key]
                active_servers = project_config.get("mcpServers", {}) or {}
                disabled_servers = project_config.get("mcpServersDisabled", {}) or {}

                for status, mcp_servers in [
                    ("active", active_servers),
                    ("disabled", disabled_servers),
                ]:
                    if not isinstance(mcp_servers, dict):
                        continue
                    for name, config in mcp_servers.items():
                        if name in seen_names:
                            continue
                        seen_names.add(name)

                        mcp = self._parse_mcp_config(
                            name,
                            config,
                            self.claude_json_path,
                            "local",
                            status=status,
                            source_detail=(
                                f"{_pretty_path(self.claude_json_path)}:"
                                f'projects["{_pretty_path(Path(project_key))}"].'
                                f"{'mcpServers' if status == 'active' else 'mcpServersDisabled'}."
                                f"{name}"
                            ),
                        )
                        if mcp:
                            mcps.append(mcp)

        except (json.JSONDecodeError, OSError):
            pass

        return mcps

    def _scan_plugin_mcps(self, seen_names: set) -> List[MCPMetadata]:
        """Scan plugin-provided MCPs from plugin.json and .mcp.json files."""
        mcps = []

        if not self.plugins_cache.exists():
            return mcps

        # Scan .mcp.json files (primary location for plugin MCPs)
        for mcp_json in self.plugins_cache.glob("*/*/.mcp.json"):
            mcps.extend(self._parse_mcp_json_file(mcp_json, seen_names))

        for mcp_json in self.plugins_cache.glob("*/*/*/.mcp.json"):
            mcps.extend(self._parse_mcp_json_file(mcp_json, seen_names))

        # Also scan plugin.json for mcpServers (alternate location)
        for plugin_json in self.plugins_cache.glob("*/*/.claude-plugin/plugin.json"):
            try:
                with open(plugin_json, "r") as f:
                    plugin_data = json.load(f)

                plugin_name = plugin_data.get("name", plugin_json.parent.parent.name)
                mcp_servers = plugin_data.get("mcpServers", {})

                for mcp_name, config in mcp_servers.items():
                    # Plugin MCPs use format "plugin:<plugin>:<mcp>"
                    full_name = f"plugin:{plugin_name}:{mcp_name}"

                    if full_name in seen_names:
                        continue
                    seen_names.add(full_name)

                    # Resolve ${CLAUDE_PLUGIN_ROOT} in args
                    plugin_root = plugin_json.parent.parent
                    config = self._resolve_plugin_vars(config, plugin_root)

                    mcp = self._parse_mcp_config(
                        full_name,
                        config,
                        plugin_json,
                        "plugin",
                        source_detail=(
                            f"{_pretty_path(plugin_json)}:mcpServers.{mcp_name}"
                        ),
                    )
                    if mcp:
                        mcps.append(mcp)

            except (json.JSONDecodeError, OSError):
                continue

        # Also scan versioned plugin directories
        for plugin_json in self.plugins_cache.glob("*/*/*/.claude-plugin/plugin.json"):
            try:
                with open(plugin_json, "r") as f:
                    plugin_data = json.load(f)

                plugin_name = plugin_data.get("name", plugin_json.parent.parent.name)
                mcp_servers = plugin_data.get("mcpServers", {})

                for mcp_name, config in mcp_servers.items():
                    full_name = f"plugin:{plugin_name}:{mcp_name}"

                    if full_name in seen_names:
                        continue
                    seen_names.add(full_name)

                    plugin_root = plugin_json.parent.parent
                    config = self._resolve_plugin_vars(config, plugin_root)

                    mcp = self._parse_mcp_config(
                        full_name,
                        config,
                        plugin_json,
                        "plugin",
                        source_detail=(
                            f"{_pretty_path(plugin_json)}:mcpServers.{mcp_name}"
                        ),
                    )
                    if mcp:
                        mcps.append(mcp)

            except (json.JSONDecodeError, OSError):
                continue

        return mcps

    def _scan_legacy_mcp_json(self, seen_names: set) -> List[MCPMetadata]:
        """Scan legacy `~/.claude/mcp.json`."""
        mcps = []

        if not self.mcp_json_path.exists():
            return mcps

        try:
            with open(self.mcp_json_path, "r") as f:
                data = json.load(f)

            active_servers = data.get("mcpServers", {}) or {}
            disabled_servers = data.get("mcpServersDisabled", {}) or {}

            for status, mcp_servers in [
                ("active", active_servers),
                ("disabled", disabled_servers),
            ]:
                if not isinstance(mcp_servers, dict):
                    continue
                for name, config in mcp_servers.items():
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    mcp = self._parse_mcp_config(
                        name,
                        config,
                        self.mcp_json_path,
                        "legacy",
                        status=status,
                        source_detail=(
                            f"{_pretty_path(self.mcp_json_path)}:"
                            f"{'mcpServers' if status == 'active' else 'mcpServersDisabled'}."
                            f"{name}"
                        ),
                    )
                    if mcp:
                        mcps.append(mcp)

        except (json.JSONDecodeError, OSError):
            pass

        return mcps

    def _parse_mcp_json_file(
        self, mcp_json: Path, seen_names: set
    ) -> List[MCPMetadata]:
        """Parse a `.mcp.json` file for MCP definitions."""
        mcps = []

        try:
            with open(mcp_json, "r") as f:
                mcp_data = json.load(f)

            # Get plugin name from directory structure
            # Path: cache/<marketplace>/<plugin>/<version>/.mcp.json
            plugin_name = mcp_json.parent.parent.name

            for mcp_name, config in mcp_data.items():
                full_name = f"plugin:{plugin_name}:{mcp_name}"

                if full_name in seen_names:
                    continue
                seen_names.add(full_name)

                # Resolve ${CLAUDE_PLUGIN_ROOT}
                plugin_root = mcp_json.parent
                config = self._resolve_plugin_vars(config, plugin_root)

                mcp = self._parse_mcp_config(
                    full_name,
                    config,
                    mcp_json,
                    "plugin",
                    source_detail=f"{_pretty_path(mcp_json)}:{mcp_name}",
                )
                if mcp:
                    mcps.append(mcp)

        except (json.JSONDecodeError, OSError):
            pass

        return mcps

    def _resolve_plugin_vars(self, config: dict, plugin_root: Path) -> dict:
        """Resolve `${CLAUDE_PLUGIN_ROOT}` variables in config."""
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str):
                resolved[key] = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
            elif isinstance(value, list):
                resolved[key] = [
                    v.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
                    if isinstance(v, str)
                    else v
                    for v in value
                ]
            elif isinstance(value, dict):
                resolved[key] = self._resolve_plugin_vars(value, plugin_root)
            else:
                resolved[key] = value
        return resolved

    def _parse_mcp_config(
        self,
        name: str,
        config: dict,
        config_path: Path,
        source: str,
        *,
        status: str = "active",
        source_detail: str = "",
    ) -> MCPMetadata:
        """Parse a single MCP server configuration."""
        command = config.get("command", config.get("url", ""))
        args = config.get("args", [])
        env_vars = config.get("env", {})
        transport = config.get("transport", config.get("type", "stdio"))
        config_extra = {}
        try:
            known_keys = {"command", "args", "env", "transport", "type", "url"}
            config_extra = {
                str(k): _redact_extra_config(v, key=str(k))
                for k, v in (config or {}).items()
                if str(k) not in known_keys
            }
        except Exception:
            config_extra = {}

        # HTTP MCPs
        if config.get("url"):
            transport = "http"
            command = config.get("url")

        # Detect origin
        origin = self._detect_origin(name, command, source)

        env_vars_safe = {}
        if isinstance(env_vars, dict):
            env_vars_safe = _redact_env_vars(env_vars) if self.redact_env else env_vars

        try:
            last_modified = datetime.fromtimestamp(config_path.stat().st_mtime)
        except OSError:
            last_modified = datetime.now()

        # Install path
        if command and not command.startswith("http"):
            install_path = Path(command).expanduser()
        else:
            install_path = config_path

        git_remote = _find_git_remote(install_path) if install_path else None

        return MCPMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=install_path,
            command=command,
            args=args,
            env_vars=env_vars_safe,
            transport=transport,
            source=source,
            source_detail=source_detail,
            git_remote=git_remote,
            config_extra=config_extra,
        )

    def _detect_origin(self, name: str, command: str, source: str) -> str:
        """Detect MCP origin from name, command, and source."""
        name_lower = name.lower()
        command_lower = command.lower() if command else ""

        # Plugin-provided MCPs
        if source == "plugin":
            return "plugin"

        # Local/project MCPs
        if source == "local":
            return "local"

        # Official: Anthropic/Claude
        if "anthropic" in name_lower or "claude" in name_lower:
            return "official"

        # Community: modelcontextprotocol repos
        if "modelcontextprotocol" in command_lower:
            return "community"

        # In-house: Local paths
        if command and (command.startswith("/") or command.startswith("~")):
            return "in-house"

        # External: npx, URLs, or other
        return "external"
