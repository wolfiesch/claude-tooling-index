"""Todo scanner - extracts task metrics from todo JSON files."""

import json
import os
from pathlib import Path
from typing import Optional

from ..models import TaskMetrics


class TodoScanner:
    """Scan todo JSON files for task completion metrics."""

    def __init__(self, todos_dir: Optional[Path] = None):
        self.todos_dir = todos_dir or (Path.home() / ".claude" / "todos")

    def scan(self) -> Optional[TaskMetrics]:
        """Scan todo files and extract task metrics."""
        if not self.todos_dir.exists():
            return None

        result = TaskMetrics()
        total_tasks = 0
        completed = 0
        pending = 0
        in_progress = 0

        try:
            # Use os.scandir for efficient directory iteration
            for entry in os.scandir(self.todos_dir):
                if not entry.name.endswith(".json"):
                    continue

                # Skip empty files (size <= 2 bytes = "[]")
                try:
                    if entry.stat().st_size <= 2:
                        continue
                except OSError:
                    continue

                # Parse todo JSON
                try:
                    with open(entry.path, "r") as f:
                        tasks = json.load(f)

                    if not isinstance(tasks, list):
                        continue

                    for task in tasks:
                        if not isinstance(task, dict):
                            continue

                        status = task.get("status", "")
                        total_tasks += 1

                        if status == "completed":
                            completed += 1
                        elif status == "pending":
                            pending += 1
                        elif status == "in_progress":
                            in_progress += 1

                except (json.JSONDecodeError, IOError, KeyError):
                    # Skip corrupted files
                    continue

        except OSError:
            return None

        # Populate result
        result.total_tasks = total_tasks
        result.completed = completed
        result.pending = pending
        result.in_progress = in_progress
        result.completion_rate = completed / total_tasks if total_tasks > 0 else 0.0

        return result
