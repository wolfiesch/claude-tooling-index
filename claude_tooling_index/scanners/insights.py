"""Insights scanner - extracts analytics from `~/.claude/data/insights.db`."""

import sqlite3
from pathlib import Path
from typing import Optional

from ..models import InsightMetrics


class InsightsScanner:
    """Scan insights.db for categorized insights and patterns."""

    def __init__(self, insights_db_path: Optional[Path] = None):
        self.insights_db_path = insights_db_path or (
            Path.home() / ".claude" / "data" / "insights.db"
        )

    def scan(self) -> Optional[InsightMetrics]:
        """Scan insights database and extract analytics."""
        if not self.insights_db_path.exists():
            return None

        result = InsightMetrics()

        try:
            conn = sqlite3.connect(str(self.insights_db_path))
            cursor = conn.cursor()

            # Check if tables exist
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='insights'"
            )
            if not cursor.fetchone():
                conn.close()
                return None

            # Get total insights count
            cursor.execute("SELECT COUNT(*) FROM insights")
            result.total_insights = cursor.fetchone()[0]

            # Get insights by category
            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM insights
                GROUP BY category
                ORDER BY count DESC
            """
            )
            for row in cursor.fetchall():
                result.by_category[row[0]] = row[1]

            # Get insights by project (top 20)
            cursor.execute(
                """
                SELECT project_path, COUNT(*) as count
                FROM insights
                GROUP BY project_path
                ORDER BY count DESC
                LIMIT 20
            """
            )
            for row in cursor.fetchall():
                # Extract project name from path
                project_path = row[0] or "unknown"
                project_name = Path(project_path).name if project_path else "unknown"
                result.by_project[project_name] = row[1]

            # Get processed sessions count
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_sessions'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM processed_sessions")
                result.processed_sessions = cursor.fetchone()[0]

            # Get recent warnings (last 10)
            cursor.execute(
                """
                SELECT insight_text
                FROM insights
                WHERE category = 'warning'
                ORDER BY timestamp DESC
                LIMIT 10
            """
            )
            result.recent_warnings = [
                row[0][:200]
                for row in cursor.fetchall()  # Truncate long text
            ]

            # Get recent patterns (last 10)
            cursor.execute(
                """
                SELECT insight_text
                FROM insights
                WHERE category = 'pattern'
                ORDER BY timestamp DESC
                LIMIT 10
            """
            )
            result.recent_patterns = [row[0][:200] for row in cursor.fetchall()]

            # Get recent tradeoffs (last 10)
            cursor.execute(
                """
                SELECT insight_text
                FROM insights
                WHERE category = 'tradeoff'
                ORDER BY timestamp DESC
                LIMIT 10
            """
            )
            result.recent_tradeoffs = [row[0][:200] for row in cursor.fetchall()]

            conn.close()

        except sqlite3.Error:
            return None

        return result

    def search_insights(self, query: str, limit: int = 20) -> list:
        """Search insights using FTS5 full-text search."""
        if not self.insights_db_path.exists():
            return []

        results = []
        try:
            conn = sqlite3.connect(str(self.insights_db_path))
            cursor = conn.cursor()

            # Check if FTS table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='insights_fts'"
            )
            if cursor.fetchone():
                # Use FTS5 search
                cursor.execute(
                    """
                    SELECT i.category, i.project_path, i.insight_text, i.timestamp
                    FROM insights i
                    JOIN insights_fts fts ON i.rowid = fts.rowid
                    WHERE insights_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """,
                    (query, limit),
                )
            else:
                # Fallback to LIKE search
                cursor.execute(
                    """
                    SELECT category, project_path, insight_text, timestamp
                    FROM insights
                    WHERE insight_text LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (f"%{query}%", limit),
                )

            results = [
                {
                    "category": row[0],
                    "project": Path(row[1]).name if row[1] else "unknown",
                    "text": row[2],
                    "timestamp": row[3],
                }
                for row in cursor.fetchall()
            ]

            conn.close()

        except sqlite3.Error:
            pass

        return results
