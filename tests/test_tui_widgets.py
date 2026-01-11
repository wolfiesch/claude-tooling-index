from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from claude_tooling_index.models import (
    EventMetrics,
    GrowthMetrics,
    InsightMetrics,
    PluginMetadata,
    ScanResult,
    SessionMetrics,
    SkillMetadata,
    SkillUsage,
    TaskMetrics,
    TranscriptMetrics,
    UserSettingsMetadata,
)
from claude_tooling_index.tui.app import StatsPanel
from claude_tooling_index.tui.widgets import ComponentList, DetailView, SearchBar


def test_stats_panel_renders_extended_metrics(tmp_path: Path) -> None:
    skill = SkillMetadata(
        name="s1",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "s1",
        platform="claude",
    )
    core = ScanResult(skills=[skill])
    core.errors = ["[codex] scan failed: example"]

    us = UserSettingsMetadata(total_startups=10, sessions_per_day=1.0, account_age_days=10, total_projects=2)
    us.top_skills = [SkillUsage(name="s1", usage_count=3)]

    em = EventMetrics(total_events=5, session_count=2)
    em.top_tools = [("read_file", 3)]

    im = InsightMetrics(total_insights=2)
    im.by_category = {"warning": 1, "tradeoff": 0, "pattern": 1}

    sm = SessionMetrics(total_sessions=1, prompts_per_session=2.0)
    sm.project_distribution = {"proj": 1}

    tm = TaskMetrics(total_tasks=4, completed=2, pending=1, in_progress=1, completion_rate=0.5)
    trm = TranscriptMetrics(total_input_tokens=10, total_output_tokens=20, total_cache_read_tokens=5)
    trm.top_tools = [("read_file", 1)]
    gm = GrowthMetrics(current_level="L2", total_edges=1, total_patterns=1, projects_with_edges=1)

    panel = StatsPanel()
    rendered = {}

    def _capture_update(text: str) -> None:
        rendered["text"] = text

    panel.update = _capture_update  # type: ignore[method-assign]
    from types import SimpleNamespace

    panel.update_stats(
        SimpleNamespace(
            core=core,
            user_settings=us,
            event_metrics=em,
            insight_metrics=im,
            session_metrics=sm,
            task_metrics=tm,
            transcript_metrics=trm,
            growth_metrics=gm,
        )
    )

    assert "Total" in rendered["text"]
    assert "Activity" in rendered["text"]
    assert "Scan errors" in rendered["text"]


def test_component_list_filters_by_platform_and_text(tmp_path: Path) -> None:
    s1 = SkillMetadata(
        name="alpha",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "alpha",
        platform="claude",
        description="gmail",
    )
    s2 = SkillMetadata(
        name="beta",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "beta",
        platform="codex",
        description="calendar",
    )

    scan = ScanResult(skills=[s1, s2])

    widget = ComponentList()
    widget.clear = lambda: None  # type: ignore[method-assign]
    widget.add_row = lambda *args, **kwargs: None  # type: ignore[method-assign]

    widget.load_components(scan)
    assert len(widget.filtered_components) == 2

    widget.filter_by_platform("claude")
    assert len(widget.filtered_components) == 1

    widget.filter_by_platform(None)
    widget.filter_by_text("gmail")
    assert len(widget.filtered_components) == 1


def test_detail_view_format_size(tmp_path: Path) -> None:
    view = DetailView()
    assert view._format_size(10) == "10B"
    assert view._format_size(2048).endswith("KB")


def test_detail_view_renders_skill_frontmatter_and_dep_sources(tmp_path: Path) -> None:
    from rich.console import Console

    skill = SkillMetadata(
        name="s1",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "s1",
        platform="claude",
        description="Example",
        dependencies=["dep1"],
        dependency_sources=["requirements.txt"],
        frontmatter_extra={"metadata": {"short": "x"}},
    )

    panel = DetailView()._build_content(skill)
    console = Console(width=120, record=True)
    console.print(panel)
    rendered = console.export_text()

    assert "Frontmatter" in rendered
    assert "requirements.txt" in rendered
    assert "metadata" in rendered


def test_detail_view_renders_plugin_provides(tmp_path: Path) -> None:
    from rich.console import Console

    plugin = PluginMetadata(
        name="p1",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "p1",
        platform="claude",
        marketplace="custom",
        version="1.0.0",
        description="desc",
        provides_commands=["c1"],
        provides_mcps=["plugin:p1:m1"],
    )

    panel = DetailView()._build_content(plugin)
    console = Console(width=120, record=True)
    console.print(panel)
    rendered = console.export_text()
    assert "Provides Commands" in rendered
    assert "Provides MCPs" in rendered


@pytest.mark.asyncio
async def test_search_bar_clear_sets_empty_value() -> None:
    from textual.app import App, ComposeResult

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield SearchBar(id="search")

    app = TestApp()
    async with app.run_test() as pilot:
        _ = pilot  # keep `pilot` alive for the active app context
        bar = app.query_one(SearchBar)
        bar.value = "abc"
        bar.clear_search()
        assert bar.value == ""


@pytest.mark.asyncio
async def test_tui_refresh_button_triggers_refresh_action(tmp_path: Path) -> None:
    from claude_tooling_index.tui.app import ToolingIndexTUI

    class TestTUI(ToolingIndexTUI):
        CSS_PATH = None

        def __init__(self) -> None:
            super().__init__(platform="all", claude_home=tmp_path, codex_home=tmp_path)
            self.refresh_calls = 0

        def _load_components(self) -> None:  # type: ignore[override]
            self.refresh_calls += 1

    app = TestTUI()
    async with app.run_test() as pilot:
        _ = pilot  # keep pilot alive for the active app context
        assert app.query_one("#refresh-button") is not None
        assert app.refresh_calls == 1  # on_mount

        dummy_event = type(
            "E",
            (),
            {
                "button": type("B", (), {"id": "refresh-button"})(),
            },
        )()
        app.on_button_pressed(dummy_event)  # type: ignore[arg-type]
        assert app.refresh_calls == 2
