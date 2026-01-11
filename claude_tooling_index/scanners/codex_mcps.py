"""Codex MCP scanner - extracts MCP servers from `~/.codex/config.toml`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..models import MCPMetadata


def _redact_config_extra(value: object, *, key: str = "") -> object:
    key_lower = str(key or "").lower()
    if any(
        token in key_lower
        for token in (
            "token",
            "secret",
            "password",
            "api_key",
            "apikey",
            "bearer",
            "authorization",
            "auth",
            "cookie",
        )
    ):
        return "<redacted>"

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if value.startswith("${") and value.endswith("}"):
            return value
        if value.startswith(("/", "~", "./", "../")):
            return value
        # High-entropy token heuristic
        compact = value.strip()
        if len(compact) >= 32 and all(ch.isalnum() or ch in "+/=_-" for ch in compact):
            return "<redacted>"
        return value
    if isinstance(value, list):
        return [_redact_config_extra(v, key=key_lower) for v in value]
    if isinstance(value, dict):
        return {str(k): _redact_config_extra(v, key=str(k)) for k, v in value.items()}
    return str(value)


def _load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib  # py311+
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    with open(path, "rb") as f:
        return tomllib.load(f)


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


def _find_git_remote(path: Path) -> str:
    # Codex MCPs are generally configured via npx/binaries; we don't try to resolve remotes here.
    _ = path
    return ""


def _redact_env_vars(
    env: Dict[str, Any], *, keep_placeholders: bool = True
) -> Dict[str, str]:
    redacted: Dict[str, str] = {}
    for key, value in (env or {}).items():
        if value is None:
            redacted[key] = ""
            continue
        if (
            keep_placeholders
            and isinstance(value, str)
            and value.startswith("${")
            and value.endswith("}")
        ):
            redacted[key] = value
        else:
            redacted[key] = "<redacted>"
    return redacted


@dataclass
class CodexMCPScanner:
    config_toml_path: Path
    platform: str = "codex"
    origin: str = "in-house"
    redact_env: bool = True

    def scan(self) -> List[MCPMetadata]:
        """Scan Codex MCP definitions from a `config.toml` file.

        Returns:
            A list of MCP metadata objects.
        """
        mcps: List[MCPMetadata] = []

        if not self.config_toml_path.exists():
            return mcps

        data = _load_toml(self.config_toml_path)
        enabled_servers = data.get("mcp_servers") or {}
        disabled_servers = data.get("mcp_servers_disabled") or {}
        if not isinstance(enabled_servers, dict) or not isinstance(
            disabled_servers, dict
        ):
            return mcps

        last_modified = datetime.fromtimestamp(self.config_toml_path.stat().st_mtime)
        install_path = self.config_toml_path

        for status, mcp_servers in [
            ("active", enabled_servers),
            ("disabled", disabled_servers),
        ]:
            for name, cfg in mcp_servers.items():
                if not isinstance(cfg, dict):
                    continue

                command = cfg.get("command") or ""
                args = cfg.get("args") or []
                env = cfg.get("env") or {}
                known_keys = {"command", "args", "env"}
                config_extra = {
                    str(k): _redact_config_extra(v, key=str(k))
                    for k, v in cfg.items()
                    if str(k) not in known_keys
                }

                if not isinstance(args, list):
                    args = [str(args)]
                args = [str(a) for a in args]

                env_vars: Dict[str, str] = {}
                if isinstance(env, dict):
                    env_vars = (
                        _redact_env_vars(env)
                        if self.redact_env
                        else {k: str(v) for k, v in env.items()}
                    )

                mcps.append(
                    MCPMetadata(
                        name=str(name),
                        origin=self.origin,
                        status=status,
                        last_modified=last_modified,
                        install_path=install_path,
                        platform=self.platform,
                        command=str(command),
                        args=args,
                        env_vars=env_vars,
                        transport="stdio",
                        source=str(self.config_toml_path.name),
                        source_detail=(
                            f"{_pretty_path(self.config_toml_path)}:"
                            f"[{'mcp_servers' if status == 'active' else 'mcp_servers_disabled'}.{name}]"
                        ),
                        git_remote=_find_git_remote(install_path) or None,
                        config_extra=config_extra,
                    )
                )

        return mcps
