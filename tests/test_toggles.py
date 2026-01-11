from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from claude_tooling_index.models import CommandMetadata, MCPMetadata, SkillMetadata
from claude_tooling_index.toggles import (
    ToggleError,
    ToggleNotSupported,
    toggle_component,
)


def test_toggle_skill_moves_between_active_and_disabled(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n")

    active = SkillMetadata(
        name="my-skill",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=skill_dir,
        platform="claude",
    )
    result = toggle_component(active)
    assert result.new_status == "disabled"
    assert (skills_dir / ".disabled" / "my-skill").exists()

    disabled = SkillMetadata(
        name="my-skill",
        origin="in-house",
        status="disabled",
        last_modified=datetime.now(),
        install_path=skills_dir / ".disabled" / "my-skill",
        platform="claude",
    )
    result = toggle_component(disabled)
    assert result.new_status == "active"
    assert (skills_dir / "my-skill").exists()


def test_toggle_command_moves_between_active_and_disabled(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    cmd = commands_dir / "hello.md"
    cmd.write_text("# /hello\n")

    active = CommandMetadata(
        name="hello",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=cmd,
        platform="claude",
        description="",
        from_plugin=None,
    )
    result = toggle_component(active)
    assert result.new_status == "disabled"
    assert (commands_dir / ".disabled" / "hello.md").exists()

    disabled = CommandMetadata(
        name="hello",
        origin="in-house",
        status="disabled",
        last_modified=datetime.now(),
        install_path=commands_dir / ".disabled" / "hello.md",
        platform="claude",
        description="",
        from_plugin=None,
    )
    result = toggle_component(disabled)
    assert result.new_status == "active"
    assert (commands_dir / "hello.md").exists()


def test_toggle_plugin_command_not_supported(tmp_path: Path) -> None:
    cmd = CommandMetadata(
        name="plugin:my-plugin:hello",
        origin="plugin",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / "plugin.json",
        platform="claude",
        description="",
        from_plugin="my-plugin",
    )

    with pytest.raises(ToggleNotSupported):
        toggle_component(cmd)


def test_toggle_codex_mcp_renames_table_header(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        """
[mcp_servers.test-server]
command = "echo"
"""
    )

    active = MCPMetadata(
        name="test-server",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=codex_home / "config.toml",
        platform="codex",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    result = toggle_component(active, codex_home=codex_home)
    assert result.new_status == "disabled"
    assert "[mcp_servers_disabled.test-server]" in (codex_home / "config.toml").read_text()

    disabled = MCPMetadata(
        name="test-server",
        origin="in-house",
        status="disabled",
        last_modified=datetime.now(),
        install_path=codex_home / "config.toml",
        platform="codex",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    result = toggle_component(disabled, codex_home=codex_home)
    assert result.new_status == "active"
    assert "[mcp_servers.test-server]" in (codex_home / "config.toml").read_text()


def test_toggle_codex_mcp_handles_quoted_keys(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        """
[mcp_servers."quoted"]
command = "echo"
"""
    )

    active = MCPMetadata(
        name="quoted",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=codex_home / "config.toml",
        platform="codex",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    toggle_component(active, codex_home=codex_home)
    assert '[mcp_servers_disabled."quoted"]' in (codex_home / "config.toml").read_text()


def test_toggle_claude_mcp_moves_entry_between_enabled_and_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps({"mcpServers": {"m1": {"command": "echo"}}, "projects": {}})
    )

    active = MCPMetadata(
        name="m1",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=claude_json,
        platform="claude",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    result = toggle_component(active, claude_home=tmp_path / ".claude")
    assert result.new_status == "disabled"
    data = json.loads(claude_json.read_text())
    assert "m1" not in data.get("mcpServers", {})
    assert "m1" in data.get("mcpServersDisabled", {})

    disabled = MCPMetadata(
        name="m1",
        origin="in-house",
        status="disabled",
        last_modified=datetime.now(),
        install_path=claude_json,
        platform="claude",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    result = toggle_component(disabled, claude_home=tmp_path / ".claude")
    assert result.new_status == "active"
    data = json.loads(claude_json.read_text())
    assert "m1" in data.get("mcpServers", {})
    assert "m1" not in data.get("mcpServersDisabled", {})


def test_toggle_rejects_plugin_mcps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude.json").write_text(json.dumps({"projects": {}}))

    plugin_mcp = MCPMetadata(
        name="plugin:some:server",
        origin="plugin",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / ".claude.json",
        platform="claude",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    with pytest.raises(ToggleNotSupported):
        toggle_component(plugin_mcp, claude_home=tmp_path / ".claude")


def test_toggle_rejects_non_active_status(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# x\n")

    bad = SkillMetadata(
        name="x",
        origin="in-house",
        status="error",
        last_modified=datetime.now(),
        install_path=skill_dir,
        platform="claude",
    )
    with pytest.raises(ToggleNotSupported):
        toggle_component(bad)


def test_toggle_rejects_builtin_mcp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude.json").write_text(json.dumps({"projects": {}}))

    builtin = MCPMetadata(
        name="claude-in-chrome",
        origin="official",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / ".claude.json",
        platform="claude",
        command="chrome-extension",
        args=[],
        env_vars={},
        transport="native-messaging",
        git_remote=None,
    )
    with pytest.raises(ToggleNotSupported):
        toggle_component(builtin, claude_home=tmp_path / ".claude")


def test_toggle_claude_mcp_missing_entry_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude.json").write_text(json.dumps({"projects": {}}))

    missing = MCPMetadata(
        name="missing",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / ".claude.json",
        platform="claude",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(missing, claude_home=tmp_path / ".claude")


def test_toggle_claude_mcp_invalid_json_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude.json").write_text("{not-json")

    mcp = MCPMetadata(
        name="m1",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / ".claude.json",
        platform="claude",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(mcp, claude_home=tmp_path / ".claude")


def test_toggle_codex_mcp_missing_config_raises(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    mcp = MCPMetadata(
        name="x",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=codex_home / "config.toml",
        platform="codex",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(mcp, codex_home=codex_home)


def test_toggle_codex_mcp_duplicate_tables_raises(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        """
[mcp_servers.x]
command = "echo"

[mcp_servers_disabled.x]
command = "echo"
"""
    )

    mcp = MCPMetadata(
        name="x",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=codex_home / "config.toml",
        platform="codex",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(mcp, codex_home=codex_home)


def test_toggle_rejects_unknown_platform_for_mcp(tmp_path: Path) -> None:
    mcp = MCPMetadata(
        name="x",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / "noop",
        platform="weird",
        command="echo",
        args=[],
        env_vars={},
        transport="stdio",
        git_remote=None,
    )
    with pytest.raises(ToggleNotSupported):
        toggle_component(mcp)


def test_toggle_rejects_unsupported_component_type(tmp_path: Path) -> None:
    component = type(
        "X",
        (),
        {
            "type": "plugin",
            "platform": "claude",
            "status": "active",
            "name": "p",
            "install_path": tmp_path / "p",
        },
    )()
    with pytest.raises(ToggleNotSupported):
        toggle_component(component)


def test_toggle_file_or_dir_inconsistent_status_raises(tmp_path: Path) -> None:
    # Status says disabled, but path isn't in .disabled.
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    cmd = commands_dir / "x.md"
    cmd.write_text("# /x\n")

    wrong = CommandMetadata(
        name="x",
        origin="in-house",
        status="disabled",
        last_modified=datetime.now(),
        install_path=cmd,
        platform="claude",
        description="",
        from_plugin=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(wrong)


def test_toggle_file_or_dir_missing_path_raises(tmp_path: Path) -> None:
    missing = CommandMetadata(
        name="missing",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=tmp_path / "commands" / "missing.md",
        platform="claude",
        description="",
        from_plugin=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(missing)


def test_toggle_file_or_dir_already_disabled_raises(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    disabled_dir = commands_dir / ".disabled"
    disabled_dir.mkdir(parents=True)
    disabled_cmd = disabled_dir / "x.md"
    disabled_cmd.write_text("# /x\n")

    inconsistent = CommandMetadata(
        name="x",
        origin="in-house",
        status="active",
        last_modified=datetime.now(),
        install_path=disabled_cmd,
        platform="claude",
        description="",
        from_plugin=None,
    )
    with pytest.raises(ToggleError):
        toggle_component(inconsistent)
