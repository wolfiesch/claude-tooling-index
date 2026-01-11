from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from claude_tooling_index.models import MCPMetadata, SkillMetadata
from claude_tooling_index.tui.widgets.detail_view import DetailView


def test_detail_view_builds_panel_for_skill(tmp_path: Path) -> None:
    view = DetailView()
    skill = SkillMetadata(
        name="skill",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "skill",
        platform="claude",
        description="A skill",
        file_count=1,
        total_lines=2,
        performance_notes=json.dumps({"op": {"time": "1ms", "speedup": "2x"}}),
        dependencies=["dep1", "dep2"],
        invocation_aliases=["/x"],
        invocation_arguments="arg",
        invocation_instruction="Do: @$1",
        references={"files": ["@CLAUDE.md"], "skills": ["other-skill"]},
        context_fork_hint="This forks context",
        when_to_use="Use when something happens",
        trigger_rules=["After X"],
        detected_tools={"mcp_tools": ["mcp__neon__run_sql"]},
        detected_toolkits=["neon"],
        inputs=["in1: x"],
        outputs=["out1: y"],
        safety_notes="No secrets",
        capability_tags=["database"],
        side_effects=["database"],
        risk_level="medium",
        required_env_vars=["API_KEY"],
        prerequisites=["pip install x"],
        gotchas=["Beware X"],
        examples=["example"],
        trigger_types=["manual"],
        context_behavior="unknown",
        depends_on_skills=["other"],
        used_by_skills=["x"],
    )

    panel = view._build_content(skill)
    assert panel.title is not None


def test_detail_view_renders_usage_and_ref_resolution(tmp_path: Path) -> None:
    from claude_tooling_index.analytics import AnalyticsTracker
    from claude_tooling_index.models import ScanResult

    db_path = tmp_path / "tooling.sqlite"
    tracker = AnalyticsTracker(db_path=db_path)
    try:
        skill = SkillMetadata(
            name="skill",
            origin="in-house",
            status="active",
            last_modified=datetime(2026, 1, 11, 0, 0, 0),
            install_path=tmp_path / "skill",
            platform="claude",
            invocation_aliases=["/skill"],
            references={"files": ["@missing.md"], "skills": ["skill"]},
        )
        scan = ScanResult(skills=[skill])
        tracker.update_components(scan)
        tracker.track_invocation("skill:skill", session_id="s1", duration_ms=10)

        class _FakeApp:
            analytics_tracker = tracker
            scan_result = scan

        class _View(DetailView):
            @property
            def app(self):  # type: ignore[override]
                return _FakeApp()

        view = _View()
        panel = view._build_content(skill)
        assert panel.title is not None
    finally:
        tracker.close()


def test_detail_view_reference_validation_and_usage_empty(tmp_path: Path) -> None:
    from claude_tooling_index.analytics import AnalyticsTracker
    from claude_tooling_index.models import CommandMetadata, ScanResult

    # Create a real file reference to exercise existence checks.
    (tmp_path / "other.md").write_text("x")

    db_path = tmp_path / "tooling.sqlite"
    tracker = AnalyticsTracker(db_path=db_path)
    try:
        cmd = CommandMetadata(
            name="cmd",
            origin="in-house",
            status="active",
            last_modified=datetime(2026, 1, 11, 0, 0, 0),
            install_path=tmp_path / "cmd.md",
            platform="claude",
            references={"files": ["@other.md", f"@{tmp_path}/other.md"], "skills": ["codex-only"]},
        )
        # Cross-platform skill ref: exists only in codex.
        codex_skill = SkillMetadata(
            name="codex-only",
            origin="in-house",
            status="active",
            last_modified=datetime(2026, 1, 11, 0, 0, 0),
            install_path=tmp_path / "codex-only",
            platform="codex",
        )
        scan = ScanResult(commands=[cmd], skills=[codex_skill])
        tracker.update_components(scan)

        class _FakeApp:
            analytics_tracker = tracker
            scan_result = scan

        class _View(DetailView):
            @property
            def app(self):  # type: ignore[override]
                return _FakeApp()

        view = _View()
        panel = view._build_content(cmd)
        assert panel.subtitle is not None
    finally:
        tracker.close()


def test_detail_view_builds_panel_for_command(tmp_path: Path) -> None:
    from claude_tooling_index.models import CommandMetadata

    view = DetailView()
    cmd = CommandMetadata(
        name="cmd",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "cmd.md",
        platform="claude",
        description="Command",
        invocation_aliases=["/cmd"],
        invocation_arguments="arg",
        detected_toolkits=["gmail"],
        detected_tools={"composio_tools": ["GMAIL_SEND_EMAIL"]},
        risk_level="medium",
    )

    panel = view._build_content(cmd)
    assert panel.title is not None


def test_detail_view_builds_panel_for_hook(tmp_path: Path) -> None:
    from claude_tooling_index.models import HookMetadata

    view = DetailView()
    hook = HookMetadata(
        name="post_tool_use.py",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "post_tool_use.py",
        platform="claude",
        trigger="post_tool_use",
        trigger_event="post_tool_use",
        language="python",
        file_size=10,
        shebang="#!/usr/bin/env python3",
        is_executable=False,
        detected_tools={"mcp_tools": ["mcp__neon__run_sql"]},
        detected_toolkits=["neon"],
        risk_level="medium",
    )

    panel = view._build_content(hook)
    assert panel.title is not None


def test_detail_view_builds_panel_for_plugin(tmp_path: Path) -> None:
    from claude_tooling_index.models import PluginMetadata

    view = DetailView()
    plugin = PluginMetadata(
        name="p",
        origin="community",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "p",
        platform="claude",
        marketplace="custom",
        version="1.0.0",
        description="desc",
        provides_commands=["hello"],
        provides_mcps=["plugin:p:srv"],
        commands_detail={"hello": "Says hi"},
        mcps_detail={"srv": {"transport": "stdio", "env_keys": ["API_KEY"]}},
    )
    panel = view._build_content(plugin)
    assert panel.title is not None


def test_detail_view_builds_panel_for_mcp(tmp_path: Path) -> None:
    view = DetailView()
    mcp = MCPMetadata(
        name="mcp",
        origin="community",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "mcp",
        platform="codex",
        command="python3",
        args=["-m", "server"],
        env_vars={"API_KEY": "<redacted>"},
        transport="stdio",
        git_remote="https://example.com/repo.git",
        config_extra={"cwd": "/tmp", "headers": {"Authorization": "<redacted>"}},
    )

    panel = view._build_content(mcp)
    assert panel.subtitle is not None
