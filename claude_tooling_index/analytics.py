"""Analytics tracker for tooling-index.

This module provides a thin facade around `ToolingDatabase` for common analytics
and tracking operations used by the CLI and TUI.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .database import ToolingDatabase
from .models import ScanResult


class AnalyticsTracker:
    """Tracks component usage and installation timeline."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db = ToolingDatabase(db_path)

    def update_components(self, scan_result: ScanResult):
        """Persist a scan result into the database.

        Args:
            scan_result: The scan output to store.
        """
        self.db.update_components(scan_result)

    def track_invocation(
        self,
        component: str,
        session_id: str,
        platform: str = "claude",
        duration_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Record component usage.

        Args:
            component: Component identifier in the form `"type:name"`.
            session_id: Session identifier for correlating invocations.
            platform: Platform the component belongs to (for example, `"claude"`).
            duration_ms: Execution time in milliseconds, if known.
            success: Whether the invocation succeeded.
            error_message: Error message if the invocation failed.
        """
        # Parse component string
        if ":" in component:
            component_type, component_name = component.split(":", 1)
        else:
            # Fallback: assume it's a skill if no type prefix
            component_type = "skill"
            component_name = component

        self.db.track_invocation(
            component_name=component_name,
            component_type=component_type,
            session_id=session_id,
            platform=platform,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
        )

    def get_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get usage statistics for dashboard.

        Args:
            days: Lookback window in days.

        Returns:
            A dictionary of aggregated usage metrics.
        """
        return self.db.get_usage_stats(days)

    def search_components(self, query: str):
        """Run a full-text search over components.

        Args:
            query: Search query string.

        Returns:
            Search results from the underlying database implementation.
        """
        return self.db.search_components(query)

    def get_components(
        self,
        platform: Optional[str] = None,
        type: Optional[str] = None,
        origin: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """Query components with optional filters.

        Args:
            platform: Limit results to a specific platform (for example, `"claude"`).
            type: Limit results to a specific component type.
            origin: Limit results to a specific origin.
            status: Limit results to a specific status.

        Returns:
            A list of matching components from the database.
        """
        return self.db.get_components(
            platform=platform, type=type, origin=origin, status=status
        )

    def close(self):
        """Close the underlying database connection."""
        self.db.close()
