"""Shared pytest fixtures for tooling-index tests."""

from pathlib import Path

import pytest


@pytest.fixture
def mock_codex_home(tmp_path: Path) -> Path:
    """Create a mock ~/.codex directory structure."""
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    # Create skills directory
    skills_dir = codex_home / "skills"
    skills_dir.mkdir()

    return codex_home


@pytest.fixture
def mock_claude_home(tmp_path: Path) -> Path:
    """Create a mock ~/.claude directory structure."""
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()

    # Create required directories
    (claude_home / "skills").mkdir()
    (claude_home / "plugins").mkdir()
    (claude_home / "commands").mkdir()
    (claude_home / "hooks").mkdir()
    (claude_home / "bin").mkdir()
    (claude_home / "data").mkdir()

    # Create empty mcp.json
    (claude_home / "mcp.json").write_text("{}")

    return claude_home


@pytest.fixture
def sample_skill(tmp_path: Path) -> Path:
    """Create a sample skill directory with SKILL.md."""
    skill_dir = tmp_path / "sample-skill"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: sample-skill
version: 1.0.0
description: A sample skill for testing
---

# Sample Skill

This is a test skill.
""")

    # Add a Python file
    (skill_dir / "main.py").write_text("print('hello')\n")

    return skill_dir


@pytest.fixture
def sample_config_toml(tmp_path: Path) -> Path:
    """Create a sample Codex config.toml with MCP servers."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[mcp_servers.test-server]
command = "python3"
args = ["-m", "test_mcp"]
env = { API_KEY = "${API_KEY}", DEBUG = "true" }

[mcp_servers.another-server]
command = "npx"
args = ["@modelcontextprotocol/server-test"]
""")
    return config_path
