"""Enable/disable mutations for Claude/Codex tooling components.

This module performs *real* enable/disable operations by mutating the underlying
files/directories on disk (e.g. moving items into a `.disabled/` folder or
moving MCP configs into a disabled section).
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ToggleNotSupported(RuntimeError):
    """Raised when enable/disable isn't supported for a component."""


class ToggleError(RuntimeError):
    """Raised when an enable/disable operation fails."""


@dataclass(frozen=True)
class ToggleResult:
    """Result of a toggle operation."""

    new_status: str
    message: str


def toggle_component(
    component: Any,
    *,
    claude_home: Optional[Path] = None,
    codex_home: Optional[Path] = None,
) -> ToggleResult:
    """Toggle a component between enabled/disabled if supported."""
    comp_type = getattr(component, "type", None) or "unknown"
    platform = getattr(component, "platform", None) or "claude"
    status = getattr(component, "status", None) or "unknown"

    if status not in {"active", "disabled"}:
        raise ToggleNotSupported("Toggle only supported for active/disabled items.")

    enable = status == "disabled"

    if comp_type in {"skill", "command", "hook", "binary"}:
        if comp_type == "command" and getattr(component, "from_plugin", None):
            raise ToggleNotSupported(
                "Plugin-provided commands can't be toggled here; disable the plugin instead."
            )
        _toggle_file_or_dir(Path(getattr(component, "install_path")), enable=enable)
        return ToggleResult(
            new_status="active" if enable else "disabled",
            message=("Enabled" if enable else "Disabled") + f" {comp_type}: {component.name}",
        )

    if comp_type == "mcp":
        if platform == "codex":
            codex_home = codex_home or (Path.home() / ".codex")
            _toggle_codex_mcp(codex_home / "config.toml", component.name, enable=enable)
            return ToggleResult(
                new_status="active" if enable else "disabled",
                message=("Enabled" if enable else "Disabled") + f" Codex MCP: {component.name}",
            )

        if platform == "claude":
            origin = getattr(component, "origin", None) or ""
            if origin == "plugin":
                raise ToggleNotSupported(
                    "Plugin-provided MCPs can't be toggled here; disable the plugin instead."
                )
            if component.name == "claude-in-chrome":
                raise ToggleNotSupported(
                    "Built-in MCPs can't be toggled here (managed by the integration)."
                )

            claude_home = claude_home or (Path.home() / ".claude")
            changed = _toggle_claude_mcp_configs(
                claude_home=claude_home,
                mcp_name=component.name,
                enable=enable,
            )
            if not changed:
                raise ToggleError(
                    f"Couldn't find MCP '{component.name}' in Claude config files."
                )
            return ToggleResult(
                new_status="active" if enable else "disabled",
                message=("Enabled" if enable else "Disabled") + f" Claude MCP: {component.name}",
            )

        raise ToggleNotSupported(f"Unknown MCP platform '{platform}'.")

    raise ToggleNotSupported(f"Enable/disable not implemented for type '{comp_type}'.")


def _toggle_file_or_dir(path: Path, *, enable: bool) -> None:
    if not path.exists():
        raise ToggleError(f"Path not found: {path}")

    name = path.name
    parent = path.parent

    if parent.name == ".disabled":
        active_parent = parent.parent
        src = path
        dst = active_parent / name
    else:
        disabled_parent = parent / ".disabled"
        src = path
        dst = disabled_parent / name

    if enable and src.parent.name != ".disabled":
        raise ToggleError(f"{src} is already enabled.")
    if not enable and src.parent.name == ".disabled":
        raise ToggleError(f"{src} is already disabled.")

    if dst.exists():
        raise ToggleError(f"Destination already exists: {dst}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.rename(dst)
    except OSError:
        shutil.move(str(src), str(dst))


def _toggle_codex_mcp(config_toml_path: Path, mcp_name: str, *, enable: bool) -> None:
    if not config_toml_path.exists():
        raise ToggleError(f"Missing Codex config: {config_toml_path}")

    text = config_toml_path.read_text()
    lines = text.splitlines(keepends=True)

    header_re = re.compile(
        r'^\[\s*(?P<table>mcp_servers(?:_disabled)?)\.(?P<key>.+?)\s*\]\s*(?P<comment>#.*)?$'
    )

    def normalize_key(raw: str) -> str:
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            return raw[1:-1].replace('\\"', '"')
        return raw

    matches: List[Tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        m = header_re.match(line.rstrip("\n"))
        if not m:
            continue
        key = normalize_key(m.group("key"))
        if key == mcp_name:
            matches.append((idx, m.group("table"), m.group("key")))

    if len(matches) != 1:
        raise ToggleError(
            f"Expected exactly one MCP table for '{mcp_name}', found {len(matches)}."
        )

    idx, table, raw_key = matches[0]
    if enable and table == "mcp_servers":
        raise ToggleError(f"Codex MCP '{mcp_name}' is already enabled.")
    if not enable and table == "mcp_servers_disabled":
        raise ToggleError(f"Codex MCP '{mcp_name}' is already disabled.")

    new_table = "mcp_servers" if enable else "mcp_servers_disabled"
    lines[idx] = re.sub(r"\[\s*mcp_servers(?:_disabled)?\.", f"[{new_table}.", lines[idx])

    config_toml_path.write_text("".join(lines))


def _toggle_claude_mcp_configs(*, claude_home: Path, mcp_name: str, enable: bool) -> bool:
    changed = False

    # ~/.claude.json (primary)
    changed |= _toggle_claude_mcp_json(Path.home() / ".claude.json", mcp_name, enable)

    # ~/.claude/mcp.json (legacy)
    changed |= _toggle_claude_mcp_json(claude_home / "mcp.json", mcp_name, enable)

    return changed


def _toggle_claude_mcp_json(path: Path, mcp_name: str, enable: bool) -> bool:
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise ToggleError(f"Invalid JSON in {path}: {e}") from e

    changed = _move_mcp_entry_in_dict(data, mcp_name, enable)

    # Also search project-level MCPs (if present).
    projects = data.get("projects")
    if isinstance(projects, dict):
        for _, cfg in projects.items():
            if isinstance(cfg, dict):
                changed |= _move_mcp_entry_in_dict(cfg, mcp_name, enable)

    if changed:
        path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
    return changed


def _move_mcp_entry_in_dict(container: Dict[str, Any], mcp_name: str, enable: bool) -> bool:
    enabled_key = "mcpServers"
    disabled_key = "mcpServersDisabled"

    enabled = container.get(enabled_key)
    disabled = container.get(disabled_key)

    if not isinstance(enabled, dict):
        enabled = {}
    if not isinstance(disabled, dict):
        disabled = {}

    if enable:
        if mcp_name not in disabled:
            return False
        enabled[mcp_name] = disabled.pop(mcp_name)
    else:
        if mcp_name not in enabled:
            return False
        disabled[mcp_name] = enabled.pop(mcp_name)

    container[enabled_key] = enabled
    container[disabled_key] = disabled
    return True
