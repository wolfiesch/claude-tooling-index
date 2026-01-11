from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from claude_tooling_index.cli import cli


def test_cli_scan_list_search_export_and_tui(
    tmp_path: Path, mock_claude_home: Path, monkeypatch
) -> None:
    runner = CliRunner()

    # Add a skill so scan finds something.
    skill_dir = mock_claude_home / "skills" / "gmail-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: gmail-skill
description: gmail integration
---
"""
    )

    # Scan and update DB in the patched home (~/.claude/data/tooling_index.db).
    result = runner.invoke(
        cli,
        [
            "scan",
            "--platform",
            "claude",
            "--claude-home",
            str(mock_claude_home),
            "--sequential",
        ],
    )
    assert result.exit_code == 0
    assert "Scan complete" in result.output

    # List from DB.
    result = runner.invoke(cli, ["list", "--platform", "claude"])
    assert result.exit_code == 0
    assert "gmail-skill" in result.output

    # Search from DB (FTS).
    result = runner.invoke(cli, ["search", "gmail", "--platform", "claude"])
    assert result.exit_code == 0
    assert "gmail-skill" in result.output

    # Export to Markdown.
    out_md = tmp_path / "tooling.md"
    result = runner.invoke(
        cli,
        [
            "export",
            "--format",
            "markdown",
            "--output",
            str(out_md),
            "--platform",
            "claude",
            "--claude-home",
            str(mock_claude_home),
        ],
    )
    assert result.exit_code == 0
    assert out_md.exists()
    assert "# " in out_md.read_text()

    # Stats should run even without usage data.
    result = runner.invoke(cli, ["stats", "--days", "1"])
    assert result.exit_code == 0
    assert "Usage Statistics" in result.output

    # Detailed stats path uses scan_extended.
    result = runner.invoke(cli, ["stats", "--days", "1", "--detailed"])
    assert result.exit_code == 0
    assert "Extended Metrics" in result.output

    # TUI command: patch App.run() to avoid starting an event loop.
    from claude_tooling_index.tui.app import ToolingIndexTUI

    monkeypatch.setattr(ToolingIndexTUI, "run", lambda self: None)
    result = runner.invoke(
        cli,
        [
            "tui",
            "--platform",
            "claude",
            "--claude-home",
            str(mock_claude_home),
        ],
    )
    assert result.exit_code == 0

