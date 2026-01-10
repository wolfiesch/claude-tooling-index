"""Component List Widget - Filterable table of all components"""

from typing import List, Optional, Any
from textual.widgets import DataTable
from textual.message import Message


class ComponentList(DataTable):
    """A filterable DataTable showing all components"""

    COMPONENT_TYPES = ["skill", "plugin", "command", "hook", "mcp", "binary"]

    class ComponentSelected(Message):
        """Sent when a component is selected"""

        def __init__(self, component: Any) -> None:
            self.component = component
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.all_components: List[Any] = []
        self.filtered_components: List[Any] = []
        self.current_filter: str = ""
        self.type_filter: Optional[str] = None

    def on_mount(self) -> None:
        """Set up the table columns"""
        self.add_columns("Name", "Type", "Origin", "Status", "Version")
        self.cursor_type = "row"
        self.zebra_stripes = True

    def load_components(self, scan_result) -> None:
        """Load all components from scan result"""
        self.all_components = []

        # Collect all components with their type
        for skill in scan_result.skills:
            self.all_components.append(("skill", skill))
        for plugin in scan_result.plugins:
            self.all_components.append(("plugin", plugin))
        for command in scan_result.commands:
            self.all_components.append(("command", command))
        for hook in scan_result.hooks:
            self.all_components.append(("hook", hook))
        for mcp in scan_result.mcps:
            self.all_components.append(("mcp", mcp))
        for binary in scan_result.binaries:
            self.all_components.append(("binary", binary))

        # Sort by name
        self.all_components.sort(key=lambda x: x[1].name.lower())
        self.filtered_components = self.all_components.copy()

        self._refresh_table()

    def filter_by_text(self, text: str) -> None:
        """Filter components by text search"""
        self.current_filter = text.lower()
        self._apply_filters()

    def filter_by_type(self, component_type: Optional[str]) -> None:
        """Filter by component type"""
        self.type_filter = component_type
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply all active filters"""
        self.filtered_components = []

        for comp_type, component in self.all_components:
            # Type filter
            if self.type_filter and comp_type != self.type_filter:
                continue

            # Text filter
            if self.current_filter:
                searchable = f"{component.name} {getattr(component, 'description', '')}".lower()
                if self.current_filter not in searchable:
                    continue

            self.filtered_components.append((comp_type, component))

        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the table with current filtered data"""
        self.clear()

        for comp_type, component in self.filtered_components:
            status = self._format_status(component.status)
            version = getattr(component, "version", "-") or "-"
            origin = getattr(component, "origin", "unknown")

            self.add_row(
                component.name,
                comp_type,
                origin,
                status,
                version,
                key=f"{comp_type}:{component.name}",
            )

    def _format_status(self, status: str) -> str:
        """Format status with emoji"""
        status_map = {
            "active": "🟢 Active",
            "disabled": "⚪ Disabled",
            "error": "🔴 Error",
            "unknown": "🟡 Unknown",
        }
        return status_map.get(status, status)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection"""
        if event.row_key:
            key = str(event.row_key.value)
            for comp_type, component in self.filtered_components:
                if f"{comp_type}:{component.name}" == key:
                    self.post_message(self.ComponentSelected(component))
                    break

    def get_selected_component(self) -> Optional[Any]:
        """Get the currently selected component"""
        if self.cursor_row is not None and self.cursor_row < len(self.filtered_components):
            return self.filtered_components[self.cursor_row][1]
        return None
