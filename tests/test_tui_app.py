from __future__ import annotations

from datetime import datetime
from pathlib import Path

import claude_tooling_index.tui.app as tui_app
from claude_tooling_index.models import ExtendedScanResult, ScanResult, SkillMetadata


class _DummyButton:
    def __init__(self, button_id: str):
        self.id = button_id
        self._classes: set[str] = set()

    def add_class(self, name: str) -> None:
        self._classes.add(name)

    def remove_class(self, name: str) -> None:
        self._classes.discard(name)


class _DummyComponentList:
    def __init__(self) -> None:
        self.loaded = False
        self.platform_filter = None
        self.type_filter = None
        self.text_filter = None

    def load_components(self, scan_result: ScanResult) -> None:
        _ = scan_result
        self.loaded = True

    def filter_by_platform(self, platform):
        self.platform_filter = platform

    def filter_by_type(self, component_type):
        self.type_filter = component_type

    def filter_by_text(self, text: str) -> None:
        self.text_filter = text

    def focus(self) -> None:
        return None


class _DummyStatsPanel:
    def __init__(self) -> None:
        self.updated = False

    def update_stats(self, extended_result) -> None:
        _ = extended_result
        self.updated = True


class _DummyDetailView:
    def __init__(self) -> None:
        self.cleared = False
        self.last_component = None

    def clear(self) -> None:
        self.cleared = True

    def show_component(self, component) -> None:
        self.last_component = component


def test_tooling_index_tui_load_components_and_actions(monkeypatch, tmp_path: Path) -> None:
    # Build a minimal scan result.
    skill = SkillMetadata(
        name="s1",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "s1",
    )
    scan = ScanResult(skills=[skill])
    extended = ExtendedScanResult(core=scan)

    class DummyScanner:
        def __init__(self, claude_home=None):
            _ = claude_home

        def scan_extended(self):
            return extended

    monkeypatch.setattr(tui_app, "ToolingScanner", DummyScanner)

    # Create an instance without running Textual's App init.
    app = object.__new__(tui_app.ToolingIndexTUI)
    app.platform = "claude"
    app.claude_home = tmp_path / ".claude"
    app.codex_home = tmp_path / ".codex"
    app.scan_result = None
    app.extended_result = None
    app.current_type_filter = None

    # Stub out Textual methods used by the handlers.
    component_list = _DummyComponentList()
    stats_panel = _DummyStatsPanel()
    detail_view = _DummyDetailView()

    def _query_one(selector: str, cls):
        _ = cls
        if selector == "#component-list":
            return component_list
        if selector == "#stats":
            return stats_panel
        if selector == "#detail-view":
            return detail_view
        if selector == "#search":
            return _DummyComponentList()
        raise AssertionError(f"unexpected selector: {selector}")

    platform_buttons = [
        _DummyButton("platform-filter-all"),
        _DummyButton("platform-filter-claude"),
        _DummyButton("platform-filter-codex"),
    ]
    type_buttons = [
        _DummyButton("filter-all"),
        _DummyButton("filter-skill"),
    ]

    def _query(selector: str):
        if selector == "PlatformFilter Button":
            return platform_buttons
        if selector == "TypeFilter Button":
            return type_buttons
        return []

    app.query_one = _query_one  # type: ignore[attr-defined]
    app.query = _query  # type: ignore[attr-defined]
    app.notify = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    app.exit = lambda: None  # type: ignore[attr-defined]

    # Exercise load path.
    tui_app.ToolingIndexTUI._load_components(app)
    assert component_list.loaded is True
    assert stats_panel.updated is True
    assert detail_view.cleared is True

    # Exercise search handler.
    class _SearchEvent:
        query = "x"

    tui_app.ToolingIndexTUI.on_search_bar_search_changed(app, _SearchEvent())
    assert component_list.text_filter == "x"

    # Exercise component selection handler.
    class _SelectEvent:
        component = skill

    tui_app.ToolingIndexTUI.on_component_list_component_selected(app, _SelectEvent())
    assert detail_view.last_component == skill

    # Exercise filter button handler.
    class _PressedEvent:
        def __init__(self, button_id: str):
            self.button = _DummyButton(button_id)

    tui_app.ToolingIndexTUI.on_button_pressed(app, _PressedEvent("type-filter-skill"))
    assert component_list.type_filter == "skill"

    tui_app.ToolingIndexTUI.on_button_pressed(
        app, _PressedEvent("platform-filter-claude")
    )
    assert component_list.platform_filter == "claude"

    # Exercise keybinding actions.
    tui_app.ToolingIndexTUI.action_filter_skill(app)
    tui_app.ToolingIndexTUI.action_filter_all(app)
    tui_app.ToolingIndexTUI.action_refresh(app)
    tui_app.ToolingIndexTUI.action_quit(app)


def test_tooling_index_tui_update_empty_state_codex_message(tmp_path: Path) -> None:
    app = object.__new__(tui_app.ToolingIndexTUI)
    app.scan_result = ScanResult(errors=["[codex] scan failed: boom"])

    class _List:
        filtered_components = []
        platform_filter = "codex"

    class _Detail:
        message = None

        def clear(self, message=None) -> None:
            self.message = message

    component_list = _List()
    detail_view = _Detail()

    def _query_one(selector: str, cls):
        _ = cls
        if selector == "#component-list":
            return component_list
        if selector == "#detail-view":
            return detail_view
        raise AssertionError(selector)

    app.query_one = _query_one  # type: ignore[attr-defined]

    tui_app.ToolingIndexTUI._update_empty_state(app)
    assert detail_view.message is not None
    assert "No Codex components found." in detail_view.message
    assert "[codex] scan failed" in detail_view.message
