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
    """Panel showing quick statistics"""

    DEFAULT_CSS = """
    StatsPanel {
        height: 3;
        width: 100%;
        background: $surface;
        padding: 0 1;
    }
    """

    def update_stats(self, scan_result) -> None:
        """Update the stats display"""
        total = scan_result.total_count
        skills = len(scan_result.skills)
        plugins = len(scan_result.plugins)
        commands = len(scan_result.commands)
        hooks = len(scan_result.hooks)
        mcps = len(scan_result.mcps)
        binaries = len(scan_result.binaries)

        # Claude orange for numbers
        orange = "#DA7756"
        self.update(
            f"[bold {orange}]◉[/bold {orange}] [bold]Total:[/bold] [{orange}]{total}[/{orange}]  "
            f"│  Skills: [{orange}]{skills}[/{orange}]  "
            f"│  Plugins: [{orange}]{plugins}[/{orange}]  "
            f"│  Commands: [{orange}]{commands}[/{orange}]  "
            f"│  Hooks: [{orange}]{hooks}[/{orange}]  "
            f"│  MCPs: [{orange}]{mcps}[/{orange}]  "
            f"│  Binaries: [{orange}]{binaries}[/{orange}]"
        )


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
        self.scan_result = None
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
        """Load components from scanner"""
        try:
            scanner = ToolingScanner()
            self.scan_result = scanner.scan_all()

            # Update component list
            component_list = self.query_one("#component-list", ComponentList)
            component_list.load_components(self.scan_result)

            # Update stats
            stats = self.query_one("#stats", StatsPanel)
            stats.update_stats(self.scan_result)

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
