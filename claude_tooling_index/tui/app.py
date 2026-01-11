"""Main TUI Application for Claude Tooling Index"""

from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button, Label
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

from .widgets import ComponentList, DetailView, SearchBar
from ..scanner import ToolingScanner
from ..analytics import AnalyticsTracker


class TypeFilter(Horizontal):
    """Filter buttons for component types"""

    DEFAULT_CSS = """
    TypeFilter {
        height: 3;
        width: 100%;
        padding: 0 1;
    }

    TypeFilter Button {
        min-width: 10;
        margin: 0 1 0 0;
    }

    TypeFilter Button.active {
        background: $accent;
    }
    """

    def compose(self) -> ComposeResult:
        yield Button("All", id="filter-all", classes="active")
        yield Button("Skills", id="filter-skill")
        yield Button("Plugins", id="filter-plugin")
        yield Button("Commands", id="filter-command")
        yield Button("Hooks", id="filter-hook")
        yield Button("MCPs", id="filter-mcp")
        yield Button("Binaries", id="filter-binary")


class StatsPanel(Static):
    """Panel showing quick statistics including extended Phase 6 metrics"""

    DEFAULT_CSS = """
    StatsPanel {
        height: auto;
        min-height: 5;
        width: 100%;
        background: $surface;
        padding: 0 1;
    }
    """

    def update_stats(self, extended_result) -> None:
        """Update the stats display with extended metrics"""
        # Get core scan result
        core = extended_result.core if hasattr(extended_result, 'core') else extended_result
        total = core.total_count
        skills = len(core.skills)
        plugins = len(core.plugins)
        commands = len(core.commands)
        hooks = len(core.hooks)
        mcps = len(core.mcps)
        binaries = len(core.binaries)

        # Claude orange for numbers
        orange = "#DA7756"
        cyan = "#5CCFE6"
        green = "#87D65A"

        # Line 1: Component counts
        line1 = (
            f"[bold {orange}]◉[/bold {orange}] [bold]Total:[/bold] [{orange}]{total}[/{orange}]  "
            f"│  Skills: [{orange}]{skills}[/{orange}]  "
            f"│  Plugins: [{orange}]{plugins}[/{orange}]  "
            f"│  Commands: [{orange}]{commands}[/{orange}]  "
            f"│  Hooks: [{orange}]{hooks}[/{orange}]  "
            f"│  MCPs: [{orange}]{mcps}[/{orange}]  "
            f"│  Binaries: [{orange}]{binaries}[/{orange}]"
        )

        lines = [line1]

        # Line 2: Activity metrics (from user_settings)
        if hasattr(extended_result, 'user_settings') and extended_result.user_settings:
            us = extended_result.user_settings
            top_skill = us.top_skills[0].name if us.top_skills else "none"
            top_count = us.top_skills[0].usage_count if us.top_skills else 0
            line2 = (
                f"[{cyan}]📊[/{cyan}] Activity: [{cyan}]{us.total_startups}[/{cyan}] sessions  "
                f"│  [{cyan}]{us.sessions_per_day:.1f}[/{cyan}]/day  "
                f"│  [{cyan}]{us.account_age_days}[/{cyan}] days  "
                f"│  [{cyan}]{us.total_projects}[/{cyan}] projects  "
                f"│  Top: [{cyan}]{top_skill}[/{cyan}] ({top_count}x)"
            )
            lines.append(line2)

        # Line 3: Event metrics (tool usage)
        if hasattr(extended_result, 'event_metrics') and extended_result.event_metrics:
            em = extended_result.event_metrics
            top_tool = em.top_tools[0][0] if em.top_tools else "none"
            top_tool_count = em.top_tools[0][1] if em.top_tools else 0
            line3 = (
                f"[{green}]🔧[/{green}] Events: [{green}]{em.total_events}[/{green}] total  "
                f"│  [{green}]{em.session_count}[/{green}] sessions  "
                f"│  Top tool: [{green}]{top_tool}[/{green}] ({top_tool_count}x)"
            )
            lines.append(line3)

        # Line 4: Insights
        if hasattr(extended_result, 'insight_metrics') and extended_result.insight_metrics:
            im = extended_result.insight_metrics
            warnings = im.by_category.get('warning', 0)
            tradeoffs = im.by_category.get('tradeoff', 0)
            patterns = im.by_category.get('pattern', 0)
            line4 = (
                f"[#FFD580]📈[/#FFD580] Insights: [#FFD580]{im.total_insights}[/#FFD580] total  "
                f"│  [#FFD580]{warnings}[/#FFD580] warnings  "
                f"│  [#FFD580]{tradeoffs}[/#FFD580] tradeoffs  "
                f"│  [#FFD580]{patterns}[/#FFD580] patterns"
            )
            lines.append(line4)

        # Line 5: Session metrics (T1)
        if hasattr(extended_result, 'session_metrics') and extended_result.session_metrics:
            sm = extended_result.session_metrics
            project_count = len(sm.project_distribution) if sm.project_distribution else 0
            line5 = (
                f"[#B39DDB]📁[/#B39DDB] Sessions: [#B39DDB]{sm.total_sessions}[/#B39DDB] total  "
                f"│  [#B39DDB]{sm.prompts_per_session:.1f}[/#B39DDB] prompts/session  "
                f"│  [#B39DDB]{project_count}[/#B39DDB] projects"
            )
            lines.append(line5)

        # Line 6: Task metrics (T1)
        if hasattr(extended_result, 'task_metrics') and extended_result.task_metrics:
            tm = extended_result.task_metrics
            completion_pct = tm.completion_rate * 100
            line6 = (
                f"[#FFE082]✅[/#FFE082] Tasks: [#FFE082]{tm.total_tasks}[/#FFE082] total  "
                f"│  [#FFE082]{tm.completed}[/#FFE082] done ({completion_pct:.0f}%)  "
                f"│  [#FFE082]{tm.pending}[/#FFE082] pending  "
                f"│  [#FFE082]{tm.in_progress}[/#FFE082] active"
            )
            lines.append(line6)

        # Line 7: Token economics (T2)
        if hasattr(extended_result, 'transcript_metrics') and extended_result.transcript_metrics:
            trm = extended_result.transcript_metrics
            total_tokens = trm.total_input_tokens + trm.total_output_tokens
            cache_efficiency = (trm.total_cache_read_tokens / trm.total_input_tokens * 100) if trm.total_input_tokens > 0 else 0
            top_tool = trm.top_tools[0][0] if trm.top_tools else "N/A"
            line7 = (
                f"[#90CAF9]🪙[/#90CAF9] Tokens: [#90CAF9]{total_tokens:,}[/#90CAF9] total  "
                f"│  [#90CAF9]{cache_efficiency:.0f}%[/#90CAF9] cache hit  "
                f"│  Top tool: [#90CAF9]{top_tool}[/#90CAF9]"
            )
            lines.append(line7)

        # Line 8: Growth progression (T2)
        if hasattr(extended_result, 'growth_metrics') and extended_result.growth_metrics:
            gm = extended_result.growth_metrics
            line8 = (
                f"[#A5D6A7]🌱[/#A5D6A7] Growth: [#A5D6A7]{gm.current_level}[/#A5D6A7]  "
                f"│  [#A5D6A7]{gm.total_edges}[/#A5D6A7] edges  "
                f"│  [#A5D6A7]{gm.total_patterns}[/#A5D6A7] patterns  "
                f"│  [#A5D6A7]{gm.projects_with_edges}[/#A5D6A7] projects"
            )
            lines.append(line8)

        self.update("\n".join(lines))


class ToolingIndexTUI(App):
    """Terminal UI dashboard for Claude Code Tooling Index"""

    CSS_PATH = "styles.tcss"
    TITLE = "◉ Claude Code Tooling Index"
    SUB_TITLE = "Component Dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "focus_list", "Focus List"),
        Binding("/", "focus_search", "Search"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "filter_all", "All", show=False),
        Binding("2", "filter_skill", "Skills", show=False),
        Binding("3", "filter_plugin", "Plugins", show=False),
        Binding("4", "filter_command", "Commands", show=False),
        Binding("5", "filter_hook", "Hooks", show=False),
        Binding("6", "filter_mcp", "MCPs", show=False),
        Binding("7", "filter_binary", "Binaries", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scan_result = None  # Core ScanResult for component list
        self.extended_result = None  # ExtendedScanResult with Phase 6 metrics
        self.current_type_filter = None

    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header()

        with Horizontal(id="main-container"):
            # Left sidebar
            with Vertical(id="sidebar"):
                yield SearchBar(id="search")
                yield TypeFilter(id="type-filter")
                yield ComponentList(id="component-list")
                yield StatsPanel(id="stats")

            # Right detail panel
            with Vertical(id="detail-panel"):
                yield DetailView(id="detail-view")

        yield Footer()

    def on_mount(self) -> None:
        """Load data on startup"""
        self.notify("Loading components...")
        self._load_components()

    def _load_components(self) -> None:
        """Load components from scanner including Phase 6 extended metrics"""
        try:
            scanner = ToolingScanner()
            # Use extended scan to get Phase 6 metrics
            self.extended_result = scanner.scan_extended()
            self.scan_result = self.extended_result.core

            # Update component list with core scan result
            component_list = self.query_one("#component-list", ComponentList)
            component_list.load_components(self.scan_result)

            # Update stats with extended result (includes activity, events, insights)
            stats = self.query_one("#stats", StatsPanel)
            stats.update_stats(self.extended_result)

            # Clear detail view
            detail_view = self.query_one("#detail-view", DetailView)
            detail_view.clear()

            self.notify(f"Loaded {self.scan_result.total_count} components")

        except Exception as e:
            self.notify(f"Error loading components: {e}", severity="error")

    def on_search_bar_search_changed(self, event: SearchBar.SearchChanged) -> None:
        """Handle search input changes"""
        component_list = self.query_one("#component-list", ComponentList)
        component_list.filter_by_text(event.query)

    def on_component_list_component_selected(
        self, event: ComponentList.ComponentSelected
    ) -> None:
        """Handle component selection"""
        detail_view = self.query_one("#detail-view", DetailView)
        detail_view.show_component(event.component)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle filter button presses"""
        button_id = event.button.id
        if not button_id or not button_id.startswith("filter-"):
            return

        # Extract filter type
        filter_type = button_id.replace("filter-", "")
        self._apply_type_filter(filter_type if filter_type != "all" else None)

        # Update button styles
        for button in self.query("TypeFilter Button"):
            button.remove_class("active")
        event.button.add_class("active")

    def _apply_type_filter(self, component_type: str | None) -> None:
        """Apply a type filter"""
        self.current_type_filter = component_type
        component_list = self.query_one("#component-list", ComponentList)
        component_list.filter_by_type(component_type)

    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()

    def action_focus_search(self) -> None:
        """Focus the search bar"""
        search = self.query_one("#search", SearchBar)
        search.focus()

    def action_focus_list(self) -> None:
        """Focus the component list"""
        component_list = self.query_one("#component-list", ComponentList)
        component_list.focus()

    def action_refresh(self) -> None:
        """Refresh the component list"""
        self.notify("Refreshing components...")
        self._load_components()

    def action_filter_all(self) -> None:
        """Show all components"""
        self._apply_type_filter(None)
        self._update_filter_buttons("all")

    def action_filter_skill(self) -> None:
        """Filter to skills only"""
        self._apply_type_filter("skill")
        self._update_filter_buttons("skill")

    def action_filter_plugin(self) -> None:
        """Filter to plugins only"""
        self._apply_type_filter("plugin")
        self._update_filter_buttons("plugin")

    def action_filter_command(self) -> None:
        """Filter to commands only"""
        self._apply_type_filter("command")
        self._update_filter_buttons("command")

    def action_filter_hook(self) -> None:
        """Filter to hooks only"""
        self._apply_type_filter("hook")
        self._update_filter_buttons("hook")

    def action_filter_mcp(self) -> None:
        """Filter to MCPs only"""
        self._apply_type_filter("mcp")
        self._update_filter_buttons("mcp")

    def action_filter_binary(self) -> None:
        """Filter to binaries only"""
        self._apply_type_filter("binary")
        self._update_filter_buttons("binary")

    def _update_filter_buttons(self, active_filter: str) -> None:
        """Update filter button styles"""
        for button in self.query("TypeFilter Button"):
            button.remove_class("active")
            if button.id == f"filter-{active_filter}":
                button.add_class("active")


def main():
    """Run the TUI application"""
    app = ToolingIndexTUI()
    app.run()


if __name__ == "__main__":
    main()
