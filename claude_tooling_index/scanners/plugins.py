"""Plugin scanner - extracts metadata from installed_plugins.json"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from ..models import PluginMetadata


class PluginScanner:
    """Scans ~/.claude/plugins/installed_plugins.json for plugin metadata"""

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.installed_plugins_file = plugins_dir / "installed_plugins.json"

    def scan(self) -> List[PluginMetadata]:
        """Scan installed plugins from installed_plugins.json"""
        plugins = []

        if not self.installed_plugins_file.exists():
            return plugins

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
                            plugin_name, marketplace, entry
                        )
                        if plugin:
                            plugins.append(plugin)
                elif isinstance(plugin_entries, dict):
                    # Single entry (v1 format)
                    plugin = self._parse_plugin_entry(
                        plugin_name, marketplace, plugin_entries
                    )
                    if plugin:
                        plugins.append(plugin)

        except (json.JSONDecodeError, KeyError, OSError):
            # Log error but don't crash
            pass

        return plugins

    def _parse_plugin_entry(
        self, name: str, marketplace: str, entry: dict
    ) -> PluginMetadata:
        """Parse a single plugin entry"""
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

        # TODO: Extract provided commands and MCPs by scanning plugin directory
        provides_commands = []
        provides_mcps = []

        return PluginMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=install_path,
            marketplace=marketplace,
            version=version,
            installed_at=installed_at,
            git_commit_sha=git_commit_sha,
            provides_commands=provides_commands,
            provides_mcps=provides_mcps,
        )

    def _detect_origin_from_marketplace(self, marketplace: str) -> str:
        """Detect origin from marketplace name (heuristic)"""
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
