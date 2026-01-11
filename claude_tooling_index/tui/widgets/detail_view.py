"""Detail view widget - shows component details."""

import json
from typing import Any, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Static


class DetailView(VerticalScroll):
    """Panel showing detailed component information."""

    DEFAULT_CSS = """
    DetailView {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_component: Optional[Any] = None

    def compose(self):
        yield Static(id="detail-content")

    def show_component(self, component: Any) -> None:
        """Display details for the given component."""
        self.current_component = component
        content = self._build_content(component)
        self.query_one("#detail-content", Static).update(content)

    def clear(self) -> None:
        """Clear the detail view."""
        self.current_component = None
        welcome = Text()
        welcome.append("◉ ", style="#DA7756")
        welcome.append("Select a component to view details", style="dim italic")
        self.query_one("#detail-content", Static).update(welcome)

    def _build_content(self, component: Any) -> Panel:
        """Build rich content for the component."""
        content = []

        # Name and type header
        comp_type = getattr(component, "type", "unknown")
        status = getattr(component, "status", "unknown")
        status_emojis = {
            "active": "🟢",
            "disabled": "⚪",
            "error": "🔴",
            "unknown": "🟡",
        }
        status_emoji = status_emojis.get(status, "❓")

        # Claude orange color
        claude_orange = "#DA7756"

        header = Text()
        header.append(f"{component.name}", style=f"bold {claude_orange}")
        header.append(f" [{comp_type}] ", style="dim")
        header.append(f"{status_emoji} {status}")
        content.append(header)
        content.append("")

        # Description
        description = getattr(component, "description", None)
        if description:
            content.append(Text(description, style="italic"))
            content.append("")

        # Basic info table
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("Key", style="bold")
        info_table.add_column("Value")

        # Add basic fields
        version = getattr(component, "version", None)
        if version:
            info_table.add_row("Version:", version)

        platform = getattr(component, "platform", None)
        if platform:
            info_table.add_row("Platform:", platform)

        origin = getattr(component, "origin", None)
        if origin:
            info_table.add_row("Origin:", origin)

        install_path = getattr(component, "install_path", None)
        if install_path:
            info_table.add_row("Path:", str(install_path))

        last_modified = getattr(component, "last_modified", None)
        if last_modified:
            info_table.add_row("Modified:", last_modified.strftime("%Y-%m-%d %H:%M"))

        # Type-specific fields
        if comp_type == "skill":
            file_count = getattr(component, "file_count", 0)
            total_lines = getattr(component, "total_lines", 0)
            info_table.add_row("Files:", str(file_count))
            info_table.add_row("Lines:", str(total_lines))

            has_docs = getattr(component, "has_docs", False)
            info_table.add_row("Documentation:", "Yes" if has_docs else "No")

        elif comp_type == "plugin":
            marketplace = getattr(component, "marketplace", None)
            if marketplace:
                info_table.add_row("Marketplace:", marketplace)

            installed_at = getattr(component, "installed_at", None)
            if installed_at:
                info_table.add_row("Installed:", installed_at.strftime("%Y-%m-%d"))

        elif comp_type == "command":
            pass  # Description already shown above

        elif comp_type == "hook":
            trigger = getattr(component, "trigger", None)
            if trigger:
                info_table.add_row("Trigger:", trigger)

            language = getattr(component, "language", None)
            if language:
                info_table.add_row("Language:", language)

            file_size = getattr(component, "file_size", 0)
            info_table.add_row("Size:", self._format_size(file_size))

        elif comp_type == "mcp":
            command = getattr(component, "command", None)
            if command:
                info_table.add_row("Command:", command)

            transport = getattr(component, "transport", None)
            if transport:
                info_table.add_row("Transport:", transport)

        elif comp_type == "binary":
            language = getattr(component, "language", None)
            if language:
                info_table.add_row("Language:", language)

            file_size = getattr(component, "file_size", 0)
            info_table.add_row("Size:", self._format_size(file_size))

            is_executable = getattr(component, "is_executable", False)
            info_table.add_row("Executable:", "Yes" if is_executable else "No")

        content.append(info_table)

        # Performance notes
        perf_notes = getattr(component, "performance_notes", None)
        if perf_notes:
            content.append("")
            content.append(Text("Performance", style=f"bold underline {claude_orange}"))
            try:
                perf_data = json.loads(perf_notes)
                if isinstance(perf_data, dict):
                    perf_table = Table(show_header=True, box=None, padding=(0, 1))
                    perf_table.add_column("Operation")
                    perf_table.add_column("Time")
                    perf_table.add_column("Speedup")

                    for op, metrics in perf_data.items():
                        if isinstance(metrics, dict):
                            time_val = metrics.get("time", "-")
                            speedup = metrics.get("speedup", "-")
                            perf_table.add_row(op, str(time_val), str(speedup))
                        else:
                            perf_table.add_row(op, str(metrics), "-")

                    content.append(perf_table)
                else:
                    content.append(Text(str(perf_data)))
            except (json.JSONDecodeError, TypeError):
                content.append(Text(perf_notes))

        # Dependencies
        dependencies = getattr(component, "dependencies", None)
        if dependencies and len(dependencies) > 0:
            content.append("")
            content.append(
                Text("Dependencies", style=f"bold underline {claude_orange}")
            )
            for dep in dependencies:
                content.append(Text(f"  • {dep}"))

        # Error message
        error_msg = getattr(component, "error_message", None)
        if error_msg:
            content.append("")
            content.append(Text("Error", style="bold red"))
            content.append(Text(error_msg, style="red"))

        # Build panel
        from rich.console import Group

        return Panel(
            Group(*content),
            title=f"[bold {claude_orange}]{component.name}[/bold {claude_orange}]",
            border_style=claude_orange,
            subtitle=f"[dim]{comp_type}[/dim]",
        )

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
