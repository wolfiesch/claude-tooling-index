from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from claude_tooling_index.models import ExtendedScanResult, ScanResult
from claude_tooling_index.scanner import ToolingScanner


def test_tooling_scanner_scan_all_finds_core_components(mock_claude_home: Path) -> None:
    # Skill
    skill_dir = mock_claude_home / "skills" / "s1"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: s1\ndescription: hi\n---\n")

    # Command
    (mock_claude_home / "commands" / "c1.md").write_text(
        "---\ndescription: cmd\n---\n"
    )

    # Binary (non-executable is still scanned; status will be error)
    (mock_claude_home / "bin" / "b1").write_text("#!/usr/bin/env bash\necho hi\n")

    scanner = ToolingScanner(claude_home=mock_claude_home)
    result = scanner.scan_all(parallel=False)

    assert isinstance(result, ScanResult)
    assert result.scan_time is not None
    assert any(s.name == "s1" for s in result.skills)
    assert any(c.name == "c1" for c in result.commands)


def test_tooling_scanner_scan_extended_includes_phase6_metrics(
    tmp_path: Path, mock_claude_home: Path
) -> None:
    # Minimal data for Phase 6 scanners.
    (tmp_path / ".claude.json").write_text(
        json.dumps({"numStartups": 1, "skillUsage": {}, "projects": {}})
    )

    event_queue = mock_claude_home / "data" / "event_queue.jsonl"
    event_queue.write_text(
        json.dumps(
            {
                "hook_event_type": "PostToolUse",
                "timestamp": 1_700_000_000_000,
                "session_id": "s1",
                "payload": {"permission_mode": "auto", "tool_name": "read_file"},
            }
        )
        + "\n"
    )

    # Insights DB.
    insights_db = mock_claude_home / "data" / "insights.db"
    conn = sqlite3.connect(str(insights_db))
    try:
        conn.execute(
            """
            CREATE TABLE insights (
                category TEXT,
                project_path TEXT,
                insight_text TEXT,
                timestamp DATETIME
            )
            """
        )
        conn.execute(
            "INSERT INTO insights VALUES ('warning', '/x/p', 'w', datetime('now'))"
        )
        conn.commit()
    finally:
        conn.close()

    # Sessions dir.
    sessions_dir = mock_claude_home / "data" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "s1.json").write_text(json.dumps({"prompts": []}))

    # Todos dir.
    todos_dir = mock_claude_home / "todos"
    todos_dir.mkdir(parents=True, exist_ok=True)
    (todos_dir / "t1.json").write_text(json.dumps([{"status": "completed"}]))

    # Projects dir for transcripts.
    proj_dir = mock_claude_home / "projects" / "p1"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "t.jsonl").write_text("")

    # Growth dir.
    growth_dir = mock_claude_home / "agentic-growth"
    (growth_dir / "edges").mkdir(parents=True, exist_ok=True)

    scanner = ToolingScanner(claude_home=mock_claude_home)
    extended = scanner.scan_extended(parallel=False)

    assert isinstance(extended, ExtendedScanResult)
    assert isinstance(extended.core, ScanResult)
    # Metrics are optional; ensure no crash and at least one metric is present.
    assert extended.event_metrics is not None

