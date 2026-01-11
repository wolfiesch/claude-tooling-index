"""Analytics tracker - usage tracking and statistics"""

from pathlib import Path
from typing import Optional, Dict, Any

from .database import ToolingDatabase
from .models import ScanResult


class AnalyticsTracker:
    """Tracks component usage and installation timeline"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db = ToolingDatabase(db_path)

    def update_components(self, scan_result: ScanResult):
        """Update components from scan result"""
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
        """
        Record component usage.

        Args:
            component: Component identifier in format "type:name" (e.g., "skill:gmail-gateway")
            session_id: Session identifier
            duration_ms: Execution time in milliseconds
            success: Whether the invocation succeeded
            error_message: Error message if invocation failed
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
        """Get usage statistics for dashboard"""
        return self.db.get_usage_stats(days)

    def search_components(self, query: str):
        """Full-text search for components"""
        return self.db.search_components(query)

    def get_components(
        self,
        platform: Optional[str] = None,
        type: Optional[str] = None,
        origin: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """Query components with filters"""
        return self.db.get_components(
            platform=platform, type=type, origin=origin, status=status
        )

    def close(self):
        """Close database connection"""
        self.db.close()
