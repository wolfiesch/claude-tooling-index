from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from claude_tooling_index.database import ToolingDatabase
from claude_tooling_index.models import ScanResult, SkillMetadata


def _make_skill(*, name: str, platform: str, install_path: Path, description: str = "") -> SkillMetadata:
    return SkillMetadata(
        name=name,
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=install_path,
        platform=platform,
        version="1.0.0",
        description=description,
        file_count=1,
        total_lines=1,
        has_docs=True,
    )


def test_update_components_inserts_updates_and_searches(tmp_path: Path) -> None:
    db_path = tmp_path / "tooling.sqlite"
    db = ToolingDatabase(db_path=db_path)
    try:
        skill_a = _make_skill(
            name="gmail-gateway",
            platform="claude",
            install_path=tmp_path / "skills" / "gmail-gateway",
            description="Manage Gmail locally.",
        )
        skill_b = _make_skill(
            name="gmail-gateway",
            platform="codex",
            install_path=tmp_path / "codex" / "skills" / "gmail-gateway",
            description="Same name, different platform.",
        )

        db.update_components(ScanResult(skills=[skill_a, skill_b]))

        rows = db.get_components()
        assert len(rows) == 2
        assert {r["platform"] for r in rows} == {"claude", "codex"}

        # FTS: match on description.
        results = db.search_components("Gmail")
        assert any(r["name"] == "gmail-gateway" for r in results)

        # Second update should record updates.
        skill_a.status = "disabled"
        db.update_components(ScanResult(skills=[skill_a, skill_b]))

        cursor = db.conn.cursor()
        cursor.execute("SELECT event_type, COUNT(*) FROM installation_events GROUP BY event_type")
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        assert counts.get("installed") == 2
        assert counts.get("updated") == 2
    finally:
        db.close()


def test_track_invocation_and_usage_stats(tmp_path: Path) -> None:
    db_path = tmp_path / "tooling.sqlite"
    db = ToolingDatabase(db_path=db_path)
    try:
        skill = _make_skill(
            name="test-skill",
            platform="claude",
            install_path=tmp_path / "skills" / "test-skill",
            description="Test skill.",
        )
        db.update_components(ScanResult(skills=[skill]))

        # Add enough invocations to populate performance metrics (HAVING COUNT(*) >= 3).
        for ms in (10, 20, 30):
            db.track_invocation(
                component_name="test-skill",
                component_type="skill",
                session_id="sess-1",
                platform="claude",
                duration_ms=ms,
                success=True,
            )

        stats = db.get_usage_stats(days=30)
        assert stats["total_invocations"] == 3
        assert stats["most_used"][0]["name"] == "test-skill"
        assert any("claude:skill:test-skill" in k for k in stats["performance_avg"].keys())

        per = db.get_component_usage(
            platform="claude",
            name="test-skill",
            component_type="skill",
            days=30,
        )
        assert per["found"] is True
        assert per["total_invocations"] == 3
        assert per["sessions"] == 1
        assert per["success_rate"] == 1.0
        assert per["p95_duration_ms"] in {10, 20, 30}
    finally:
        db.close()


def test_migrates_old_components_schema_adds_platform(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"

    # Create an older schema without the `platform` column.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                origin TEXT,
                status TEXT,
                version TEXT,
                install_path TEXT,
                first_seen DATETIME NOT NULL,
                last_seen DATETIME NOT NULL,
                metadata_json TEXT,
                UNIQUE(name, type)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO components
            (name, type, origin, status, version, install_path, first_seen, last_seen, metadata_json)
            VALUES ('legacy-skill', 'skill', 'in-house', 'active', '1.0.0', '/tmp', datetime('now'), datetime('now'), '{}')
            """
        )
        conn.commit()
    finally:
        conn.close()

    db = ToolingDatabase(db_path=db_path)
    try:
        rows = db.get_components()
        assert len(rows) == 1
        assert rows[0]["name"] == "legacy-skill"
        assert rows[0]["platform"] == "claude"
    finally:
        db.close()
