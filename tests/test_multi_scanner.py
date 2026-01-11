"""Unit tests for MultiToolingScanner."""

from pathlib import Path

import pytest

from claude_tooling_index.models import ScanResult
from claude_tooling_index.multi_scanner import MultiToolingScanner


class TestMultiToolingScanner:
    """Tests for MultiToolingScanner."""

    def test_init_accepts_custom_homes(self, tmp_path: Path):
        claude_home = tmp_path / "claude"
        codex_home = tmp_path / "codex"

        scanner = MultiToolingScanner(claude_home=claude_home, codex_home=codex_home)

        assert scanner._claude_home == claude_home
        assert scanner._codex_home == codex_home

    def test_scan_all_rejects_invalid_platform(self, tmp_path: Path):
        scanner = MultiToolingScanner()

        with pytest.raises(ValueError, match="platform must be one of"):
            scanner.scan_all(platform="invalid")

    def test_scan_all_claude_only(self, mock_claude_home: Path):
        # Add a skill to Claude
        skill_dir = mock_claude_home / "skills" / "claude-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: claude-skill\n---\n# Skill\n")

        scanner = MultiToolingScanner(claude_home=mock_claude_home)
        result = scanner.scan_all(platform="claude")

        assert isinstance(result, ScanResult)
        assert len(result.skills) == 1
        assert result.skills[0].platform == "claude"

    def test_scan_all_codex_only(self, mock_codex_home: Path):
        # Add MCP to Codex
        (mock_codex_home / "config.toml").write_text("""
[mcp_servers.codex-mcp]
command = "python3"
""")

        scanner = MultiToolingScanner(codex_home=mock_codex_home)
        result = scanner.scan_all(platform="codex")

        assert isinstance(result, ScanResult)
        assert len(result.mcps) == 1
        assert result.mcps[0].platform == "codex"

    def test_scan_all_merges_both_platforms(
        self, mock_claude_home: Path, mock_codex_home: Path
    ):
        # Add skill to Claude
        claude_skill_dir = mock_claude_home / "skills" / "claude-skill"
        claude_skill_dir.mkdir(parents=True)
        (claude_skill_dir / "SKILL.md").write_text("---\nname: claude-skill\n---\n# Skill\n")

        # Add skill to Codex
        codex_skill_dir = mock_codex_home / "skills" / "codex-skill"
        codex_skill_dir.mkdir(parents=True)
        (codex_skill_dir / "SKILL.md").write_text("---\nname: codex-skill\n---\n# Skill\n")
        (mock_codex_home / "config.toml").write_text("")

        scanner = MultiToolingScanner(
            claude_home=mock_claude_home,
            codex_home=mock_codex_home
        )
        result = scanner.scan_all(platform="all")

        assert len(result.skills) == 2

        platforms = {s.platform for s in result.skills}
        assert platforms == {"claude", "codex"}

        names = {s.name for s in result.skills}
        assert names == {"claude-skill", "codex-skill"}

    def test_scan_all_gracefully_handles_empty_claude(self, mock_codex_home: Path, tmp_path: Path):
        # Create empty Claude home (no skills)
        empty_claude = tmp_path / ".claude"
        empty_claude.mkdir()
        (empty_claude / "skills").mkdir()
        (empty_claude / "plugins").mkdir()
        (empty_claude / "commands").mkdir()
        (empty_claude / "hooks").mkdir()
        (empty_claude / "bin").mkdir()
        (empty_claude / "data").mkdir()
        (empty_claude / "mcp.json").write_text("{}")

        # Add skill to Codex
        codex_skill_dir = mock_codex_home / "skills" / "codex-skill"
        codex_skill_dir.mkdir(parents=True)
        (codex_skill_dir / "SKILL.md").write_text("---\nname: codex-skill\n---\n# Skill\n")
        (mock_codex_home / "config.toml").write_text("")

        scanner = MultiToolingScanner(
            claude_home=empty_claude,
            codex_home=mock_codex_home
        )
        result = scanner.scan_all(platform="all")

        # Should return merged results
        assert isinstance(result, ScanResult)
        # Only Codex skill should be present (Claude has no skills)
        assert len(result.skills) == 1
        assert result.skills[0].platform == "codex"
        assert result.skills[0].name == "codex-skill"

    def test_scan_all_gracefully_handles_empty_codex(self, mock_claude_home: Path, tmp_path: Path):
        # Create empty Codex home (no components)
        empty_codex = tmp_path / ".codex"
        empty_codex.mkdir()
        (empty_codex / "skills").mkdir()
        (empty_codex / "config.toml").write_text("")

        # Add a skill to Claude
        skill_dir = mock_claude_home / "skills" / "claude-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: claude-skill\n---\n# Skill\n")

        scanner = MultiToolingScanner(
            claude_home=mock_claude_home,
            codex_home=empty_codex
        )
        result = scanner.scan_all(platform="all")

        # Should return Claude results merged with empty Codex results
        assert isinstance(result, ScanResult)
        assert len(result.skills) == 1
        assert result.skills[0].platform == "claude"

    def test_scan_all_parallel_vs_sequential(
        self, mock_claude_home: Path, mock_codex_home: Path
    ):
        (mock_codex_home / "config.toml").write_text("")

        scanner = MultiToolingScanner(
            claude_home=mock_claude_home,
            codex_home=mock_codex_home
        )

        result_parallel = scanner.scan_all(platform="all", parallel=True)
        result_sequential = scanner.scan_all(platform="all", parallel=False)

        # Both should work without errors
        assert isinstance(result_parallel, ScanResult)
        assert isinstance(result_sequential, ScanResult)

    def test_scan_all_sets_scan_time(self, mock_claude_home: Path):
        scanner = MultiToolingScanner(claude_home=mock_claude_home)
        result = scanner.scan_all(platform="claude")

        assert result.scan_time is not None

    def test_merge_results_combines_all_lists(self):
        from datetime import datetime

        from claude_tooling_index.models import SkillMetadata

        scanner = MultiToolingScanner()

        # Create mock results
        skill1 = SkillMetadata(
            name="skill1", origin="in-house", status="active",
            last_modified=datetime.now(), install_path=Path("/a"), platform="claude"
        )
        skill2 = SkillMetadata(
            name="skill2", origin="in-house", status="active",
            last_modified=datetime.now(), install_path=Path("/b"), platform="codex"
        )

        result_a = ScanResult(skills=[skill1])
        result_b = ScanResult(skills=[skill2])

        merged = scanner._merge_results(result_a, result_b)

        assert len(merged.skills) == 2
        assert merged.skills[0].name == "skill1"
        assert merged.skills[1].name == "skill2"

    def test_default_platform_is_claude(self, mock_claude_home: Path):
        scanner = MultiToolingScanner(claude_home=mock_claude_home)

        # Default should be claude
        result = scanner.scan_all()
        assert isinstance(result, ScanResult)

    def test_platform_case_insensitive(self, mock_claude_home: Path):
        scanner = MultiToolingScanner(claude_home=mock_claude_home)

        # Should accept uppercase
        result = scanner.scan_all(platform="CLAUDE")
        assert isinstance(result, ScanResult)

        result = scanner.scan_all(platform="Claude")
        assert isinstance(result, ScanResult)
