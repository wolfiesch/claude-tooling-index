"""Unit tests for CodexToolingScanner."""

import pytest
from pathlib import Path

from claude_tooling_index.codex_scanner import CodexToolingScanner
from claude_tooling_index.models import ScanResult


class TestCodexToolingScanner:
    """Tests for CodexToolingScanner."""

    def test_init_with_custom_codex_home(self, mock_codex_home: Path):
        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        assert scanner.codex_home == mock_codex_home

    def test_init_raises_for_missing_codex_home(self, tmp_path: Path, monkeypatch):
        # Mock Path.home() to return tmp_path (which has no .codex)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(ValueError, match="~/.codex directory not found"):
            CodexToolingScanner()  # No codex_home provided, will use _detect_codex_home

    def test_scan_all_returns_scan_result(self, mock_codex_home: Path):
        # Create config.toml
        (mock_codex_home / "config.toml").write_text("")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all()

        assert isinstance(result, ScanResult)
        assert result.scan_time is not None

    def test_scan_all_finds_skills(self, mock_codex_home: Path):
        # Create a skill
        skill_dir = mock_codex_home / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
version: 1.0.0
description: Test skill
---
# Test Skill
""")
        (mock_codex_home / "config.toml").write_text("")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all()

        assert len(result.skills) == 1
        assert result.skills[0].name == "test-skill"
        assert result.skills[0].platform == "codex"

    def test_scan_all_finds_mcps(self, mock_codex_home: Path):
        (mock_codex_home / "config.toml").write_text("""
[mcp_servers.test-mcp]
command = "python3"
args = ["-m", "mcp_server"]
""")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all()

        assert len(result.mcps) == 1
        assert result.mcps[0].name == "test-mcp"
        assert result.mcps[0].platform == "codex"

    def test_scan_all_returns_empty_lists_for_unsupported_types(self, mock_codex_home: Path):
        (mock_codex_home / "config.toml").write_text("")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all()

        # Codex doesn't support these component types
        assert result.plugins == []
        assert result.commands == []
        assert result.hooks == []
        assert result.binaries == []

    def test_scan_all_parallel_vs_sequential(self, mock_codex_home: Path):
        (mock_codex_home / "config.toml").write_text("""
[mcp_servers.mcp1]
command = "cmd1"
""")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)

        result_parallel = scanner.scan_all(parallel=True)
        result_sequential = scanner.scan_all(parallel=False)

        # Both should return same results
        assert len(result_parallel.mcps) == len(result_sequential.mcps)
        assert result_parallel.mcps[0].name == result_sequential.mcps[0].name

    def test_scan_all_captures_errors(self, mock_codex_home: Path):
        # Create invalid config that will cause parsing to fail
        (mock_codex_home / "config.toml").write_text("invalid toml [[[")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all()

        # Should capture error but not crash
        assert len(result.errors) > 0
        assert "[codex]" in result.errors[0]

    def test_scan_all_with_both_skills_and_mcps(self, mock_codex_home: Path):
        # Create skill
        skill_dir = mock_codex_home / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: my-skill
---
# My Skill
""")

        # Create MCP config
        (mock_codex_home / "config.toml").write_text("""
[mcp_servers.my-mcp]
command = "python3"
""")

        scanner = CodexToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all()

        assert len(result.skills) == 1
        assert len(result.mcps) == 1
        assert result.total_count == 2
