from __future__ import annotations

import json
from pathlib import Path

from claude_tooling_index.scanners import PluginScanner


def test_plugin_scanner_v1_format_single_entry_and_invalid_dates(
    mock_claude_home: Path, tmp_path: Path
) -> None:
    plugins_dir = mock_claude_home / "plugins"
    install_dir = tmp_path / "plugin-install"
    install_dir.mkdir()

    # v1 format: flat dict; plugin key without "@"
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(
            {
                "my-plugin": {
                    "installPath": str(install_dir),
                    "version": "1.2.3",
                    "installedAt": "not-a-timestamp",
                    "lastUpdated": "also-not-a-timestamp",
                    "gitCommitSha": "abc",
                }
            }
        )
    )

    plugins = PluginScanner(plugins_dir).scan()
    assert len(plugins) == 1
    assert plugins[0].name == "my-plugin"
    assert plugins[0].marketplace == "unknown"
    assert plugins[0].status == "active"


def test_plugin_scanner_origin_heuristics_and_invalid_json_is_ignored(
    mock_claude_home: Path,
) -> None:
    plugins_dir = mock_claude_home / "plugins"

    # Invalid JSON should not crash.
    (plugins_dir / "installed_plugins.json").write_text("{not-json")
    assert PluginScanner(plugins_dir).scan() == []

    # Version 2 format with multiple marketplaces.
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "p-official@claude-plugins-official": [{"installPath": ""}],
                    "p-community@cc-marketplace": [{"installPath": ""}],
                    "p-inhouse@custom": [{"installPath": ""}],
                    "p-external@something-else": [{"installPath": ""}],
                },
            }
        )
    )
    plugins = PluginScanner(plugins_dir).scan()
    by_name = {p.name: p for p in plugins}

    assert by_name["p-official"].origin == "official"
    assert by_name["p-community"].origin == "community"
    assert by_name["p-inhouse"].origin == "in-house"
    assert by_name["p-external"].origin == "external"

