"""Plugin scanner - extracts metadata from `installed_plugins.json`."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models import PluginMetadata


class PluginScanner:
    """Scan `installed_plugins.json` for plugin metadata."""

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.installed_plugins_file = plugins_dir / "installed_plugins.json"
        self.plugins_cache_dir = plugins_dir / "cache"

    def scan(self) -> List[PluginMetadata]:
        """Scan installed plugins from `installed_plugins.json`."""
        plugins = []

        if not self.installed_plugins_file.exists():
            return plugins

        cache_index = self._scan_plugin_cache()

        try:
            with open(self.installed_plugins_file, "r") as f:
                data = json.load(f)

            # Handle both v1 and v2 format
            version = data.get("version", 1)

            if version == 2:
                plugins_data = data.get("plugins", {})
            else:
                # v1 format (flat dict)
                plugins_data = data

            for plugin_key, plugin_entries in plugins_data.items():
                # plugin_key format: "name@marketplace"
                if "@" in plugin_key:
                    plugin_name, marketplace = plugin_key.rsplit("@", 1)
                else:
                    plugin_name = plugin_key
                    marketplace = "unknown"

                # Handle array of plugin versions (typically just one)
                if isinstance(plugin_entries, list):
                    for entry in plugin_entries:
                        plugin = self._parse_plugin_entry(
                            plugin_name, marketplace, entry, cache_index
                        )
                        if plugin:
                            plugins.append(plugin)
                elif isinstance(plugin_entries, dict):
                    # Single entry (v1 format)
                    plugin = self._parse_plugin_entry(
                        plugin_name, marketplace, plugin_entries, cache_index
                    )
                    if plugin:
                        plugins.append(plugin)

        except (json.JSONDecodeError, KeyError, OSError):
            # Log error but don't crash
            pass

        return plugins

    def _parse_plugin_entry(
        self,
        name: str,
        marketplace: str,
        entry: dict,
        cache_index: Dict[str, Dict[str, object]],
    ) -> PluginMetadata:
        """Parse a single plugin entry."""
        install_path_str = entry.get("installPath", "")
        install_path = Path(install_path_str).expanduser() if install_path_str else None

        version = entry.get("version", "unknown")
        installed_at_str = entry.get("installedAt")
        last_updated_str = entry.get("lastUpdated")
        git_commit_sha = entry.get("gitCommitSha", "")

        # Parse timestamps
        installed_at = None
        last_modified = datetime.now()

        if installed_at_str:
            try:
                installed_at = datetime.fromisoformat(
                    installed_at_str.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        if last_updated_str:
            try:
                last_modified = datetime.fromisoformat(
                    last_updated_str.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Detect origin from marketplace
        origin = self._detect_origin_from_marketplace(marketplace)

        # Check if plugin directory exists to determine status
        status = "active" if (install_path and install_path.exists()) else "error"

        cache_meta = cache_index.get(name) or {}
        description = cache_meta.get("description") or ""
        author = cache_meta.get("author") or ""
        homepage = cache_meta.get("homepage") or ""
        repository = cache_meta.get("repository") or ""
        license_value = cache_meta.get("license") or ""
        provides_commands = list(cache_meta.get("provides_commands") or [])
        provides_mcps = list(cache_meta.get("provides_mcps") or [])
        commands_detail = dict(cache_meta.get("commands_detail") or {})
        mcps_detail = dict(cache_meta.get("mcps_detail") or {})

        return PluginMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=install_path,
            marketplace=marketplace,
            version=version,
            description=str(description) if description else "",
            author=str(author) if author else "",
            homepage=str(homepage) if homepage else "",
            repository=str(repository) if repository else "",
            license=str(license_value) if license_value else "",
            installed_at=installed_at,
            git_commit_sha=git_commit_sha,
            provides_commands=provides_commands,
            provides_mcps=provides_mcps,
            commands_detail=commands_detail,
            mcps_detail=mcps_detail,
        )

    def _detect_origin_from_marketplace(self, marketplace: str) -> str:
        """Detect origin from marketplace name (heuristic)."""
        if marketplace in ["claude-plugins-official", "claude-code-plugins"]:
            return "official"
        elif marketplace in [
            "superpowers-marketplace",
            "awesome-claude-skills",
            "cc-marketplace",
        ]:
            return "community"
        elif marketplace.startswith("local-") or marketplace == "custom":
            return "in-house"
        else:
            return "external"

    def _scan_plugin_cache(self) -> Dict[str, Dict[str, object]]:
        """Scan plugin cache to derive description and provided commands/MCPs."""
        index: Dict[str, Dict[str, object]] = {}

        if not self.plugins_cache_dir.exists():
            return index

        def ensure(name: str) -> Dict[str, object]:
            if name not in index:
                index[name] = {
                    "description": "",
                    "author": "",
                    "homepage": "",
                    "repository": "",
                    "license": "",
                    "provides_commands": [],
                    "provides_mcps": [],
                    "commands_detail": {},
                    "mcps_detail": {},
                }
            return index[name]

        # Parse plugin.json files.
        plugin_json_paths = list(
            self.plugins_cache_dir.glob("*/*/.claude-plugin/plugin.json")
        ) + list(self.plugins_cache_dir.glob("*/*/*/.claude-plugin/plugin.json"))

        for plugin_json in plugin_json_paths:
            try:
                data = json.loads(plugin_json.read_text())
            except Exception:
                continue

            plugin_name = self._infer_plugin_name_from_plugin_json(plugin_json, data)
            if not plugin_name:
                continue

            meta = ensure(plugin_name)
            desc = data.get("description")
            if isinstance(desc, str) and desc.strip():
                meta["description"] = desc.strip()

            author = data.get("author")
            if isinstance(author, str) and author.strip():
                meta["author"] = author.strip()

            homepage = data.get("homepage")
            if isinstance(homepage, str) and homepage.strip():
                meta["homepage"] = homepage.strip()

            repository = data.get("repository")
            if isinstance(repository, str) and repository.strip():
                meta["repository"] = repository.strip()
            elif isinstance(repository, dict):
                url = repository.get("url")
                if isinstance(url, str) and url.strip():
                    meta["repository"] = url.strip()

            license_value = data.get("license")
            if isinstance(license_value, str) and license_value.strip():
                meta["license"] = license_value.strip()

            commands = self._extract_commands_from_plugin_json(data)
            if commands:
                meta["provides_commands"] = sorted(
                    set(list(meta["provides_commands"]) + commands)
                )
            commands_detail = self._extract_command_details_from_plugin_json(data)
            if commands_detail:
                merged = dict(meta.get("commands_detail") or {})
                merged.update(commands_detail)
                meta["commands_detail"] = merged

            mcp_servers = data.get("mcpServers") or {}
            if isinstance(mcp_servers, dict):
                mcps = [f"plugin:{plugin_name}:{k}" for k in mcp_servers.keys()]
                meta["provides_mcps"] = sorted(
                    set(list(meta["provides_mcps"]) + mcps)
                )
                details = self._extract_mcp_details_from_mcp_servers(mcp_servers)
                if details:
                    merged = dict(meta.get("mcps_detail") or {})
                    merged.update(details)
                    meta["mcps_detail"] = merged

        # Parse .mcp.json files.
        mcp_json_paths = list(self.plugins_cache_dir.glob("*/*/.mcp.json")) + list(
            self.plugins_cache_dir.glob("*/*/*/.mcp.json")
        )
        for mcp_json in mcp_json_paths:
            try:
                data = json.loads(mcp_json.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            # cache/<marketplace>/<plugin>/<version>/.mcp.json OR cache/<marketplace>/<plugin>/.mcp.json
            plugin_name = mcp_json.parent.name
            if plugin_name and plugin_name[0].isdigit() and mcp_json.parent.parent:
                plugin_name = mcp_json.parent.parent.name

            if not plugin_name:
                continue

            meta = ensure(plugin_name)
            mcps = [f"plugin:{plugin_name}:{k}" for k in data.keys()]
            meta["provides_mcps"] = sorted(set(list(meta["provides_mcps"]) + mcps))
            details = self._extract_mcp_details_from_mcp_servers(data)
            if details:
                merged = dict(meta.get("mcps_detail") or {})
                merged.update(details)
                meta["mcps_detail"] = merged

        return index

    def _infer_plugin_name_from_plugin_json(self, path: Path, data: dict) -> Optional[str]:
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

        # Path patterns:
        # cache/<marketplace>/<plugin>/.claude-plugin/plugin.json
        # cache/<marketplace>/<plugin>/<version>/.claude-plugin/plugin.json
        parent = path.parent.parent  # ".claude-plugin" -> plugin root (or version dir)
        if parent.name and parent.name[0].isdigit() and parent.parent:
            return parent.parent.name
        return parent.name or None

    def _extract_commands_from_plugin_json(self, data: dict) -> List[str]:
        commands = data.get("commands")
        if isinstance(commands, dict):
            return [str(k) for k in commands.keys()]
        if isinstance(commands, list):
            names: List[str] = []
            for item in commands:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict) and "name" in item:
                    names.append(str(item["name"]))
            return names
        return []

    def _extract_command_details_from_plugin_json(self, data: dict) -> Dict[str, str]:
        commands = data.get("commands")
        details: Dict[str, str] = {}
        if isinstance(commands, dict):
            for name, cfg in commands.items():
                desc = ""
                if isinstance(cfg, dict):
                    maybe = cfg.get("description") or cfg.get("help") or ""
                    if isinstance(maybe, str):
                        desc = maybe.strip()
                details[str(name)] = desc
            return details
        if isinstance(commands, list):
            for item in commands:
                if isinstance(item, str):
                    details[item] = ""
                elif isinstance(item, dict) and "name" in item:
                    desc = item.get("description") or item.get("help") or ""
                    details[str(item["name"])] = str(desc).strip() if desc else ""
        return details

    def _extract_mcp_details_from_mcp_servers(self, mcp_servers: dict) -> Dict[str, object]:
        details: Dict[str, object] = {}
        for name, cfg in (mcp_servers or {}).items():
            if not isinstance(cfg, dict):
                continue
            command = cfg.get("command") or cfg.get("url") or ""
            transport = cfg.get("transport") or cfg.get("type") or (
                "http" if cfg.get("url") else "stdio"
            )
            args = cfg.get("args") or []
            env = cfg.get("env") or {}
            env_keys: List[str] = []
            placeholders: List[str] = []
            if isinstance(env, dict):
                for k, v in env.items():
                    env_keys.append(str(k))
                    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                        placeholders.append(str(k))
            details[str(name)] = {
                "command": str(command),
                "transport": str(transport),
                "args_count": len(args) if isinstance(args, list) else 1,
                "env_keys": sorted(set(env_keys)),
                "env_placeholders": sorted(set(placeholders)),
            }
        return details
