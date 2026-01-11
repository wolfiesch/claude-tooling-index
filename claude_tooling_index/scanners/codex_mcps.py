"""Codex MCP scanner - extracts MCP servers from `~/.codex/config.toml`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..models import MCPMetadata


def _load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib  # py311+
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    with open(path, "rb") as f:
        return tomllib.load(f)


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
        mcp_servers = data.get("mcp_servers") or {}
        if not isinstance(mcp_servers, dict):
            return mcps

        last_modified = datetime.fromtimestamp(self.config_toml_path.stat().st_mtime)
        install_path = self.config_toml_path

        for name, cfg in mcp_servers.items():
            if not isinstance(cfg, dict):
                continue

            command = cfg.get("command") or ""
            args = cfg.get("args") or []
            env = cfg.get("env") or {}

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
                    status="active",
                    last_modified=last_modified,
                    install_path=install_path,
                    platform=self.platform,
                    command=str(command),
                    args=args,
                    env_vars=env_vars,
                    transport="stdio",
                    git_remote=None,
                )
            )

        return mcps
