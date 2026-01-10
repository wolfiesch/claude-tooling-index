"""Search Bar Widget - Live search input"""

from textual.widgets import Input
from textual.message import Message


class SearchBar(Input):
    """Search input with live filtering"""

    DEFAULT_CSS = """
    SearchBar {
        dock: top;
        width: 100%;
        margin-bottom: 1;
    }
    """

    class SearchChanged(Message):
        """Sent when search text changes"""

        def __init__(self, query: str) -> None:
            self.query = query
            super().__init__()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("placeholder", "Type to search...")
        super().__init__(*args, **kwargs)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes"""
        self.post_message(self.SearchChanged(event.value))

    def clear_search(self) -> None:
        """Clear the search input"""
        self.value = ""
