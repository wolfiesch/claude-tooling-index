"""Session analytics scanner - extracts metrics from session JSON files."""

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import SessionMetrics


class SessionAnalyticsScanner:
    """Scan session JSON files for engagement and activity metrics."""

    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or (
            Path.home() / ".claude" / "data" / "sessions"
        )

    def scan(self) -> Optional[SessionMetrics]:
        """Scan session files and extract analytics."""
        if not self.sessions_dir.exists():
            return None

        result = SessionMetrics()
        project_counter = Counter()
        day_counter = Counter()
        total_prompts = 0
        session_count = 0

        try:
            # Use os.scandir for efficient directory iteration
            for entry in os.scandir(self.sessions_dir):
                if not entry.name.endswith(".json"):
                    continue

                session_count += 1

                # Get file modification time for activity_by_day
                try:
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                    day_key = mtime.strftime("%Y-%m-%d")
                    day_counter[day_key] += 1
                except (OSError, ValueError):
                    pass

                # Parse session JSON for prompts and source_app
                try:
                    with open(entry.path, "r") as f:
                        session = json.load(f)

                    # Count prompts
                    prompts = session.get("prompts", [])
                    if isinstance(prompts, list):
                        total_prompts += len(prompts)

                    # Track project/app distribution
                    source_app = session.get("source_app", "unknown")
                    if source_app:
                        project_counter[source_app] += 1

                except (json.JSONDecodeError, IOError, KeyError):
                    # Skip corrupted files
                    continue

        except OSError:
            return None

        # Populate result
        result.total_sessions = session_count
        result.prompts_per_session = (
            total_prompts / session_count if session_count > 0 else 0.0
        )
        result.project_distribution = dict(project_counter)
        result.activity_by_day = dict(day_counter)
        result.top_projects = project_counter.most_common(20)

        return result
