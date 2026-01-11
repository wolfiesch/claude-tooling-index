#!/usr/bin/env python3
"""post_tool_use_tooling.py

Python fallback hook for tracking skill and command invocations.
Use this if you cannot compile the C++ version.

Performance: ~50ms (vs <1ms for C++ version)

To install:
  cp hooks/post_tool_use_tooling.py ~/.claude/hooks/
  chmod +x ~/.claude/hooks/post_tool_use_tooling.py
"""

import json
import os
import sys
from pathlib import Path


def get_db_path() -> Path:
    """Get the database path"""
    return Path.home() / ".claude" / "data" / "tooling_index.db"


def track_invocation(component_name: str, component_type: str,
                     session_id: str, duration_ms: int, success: bool):
    """Track a component invocation in the database"""
    import sqlite3

    db_path = get_db_path()
    if not db_path.exists():
        return  # Silently skip if database doesn't exist

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get component_id
        cursor.execute(
            "SELECT id FROM components WHERE name = ? AND type = ? LIMIT 1",
            (component_name, component_type)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return  # Component not in database

        component_id = row[0]

        # Insert invocation record
        cursor.execute(
            """INSERT INTO invocations
               (component_id, session_id, timestamp, duration_ms, success)
               VALUES (?, ?, datetime('now'), ?, ?)""",
            (component_id, session_id, duration_ms, 1 if success else 0)
        )

        conn.commit()
        conn.close()

    except Exception:
        # Silent failure - don't break hooks
        pass


def main():
    # Parse tool data from environment
    tool_data_str = os.environ.get("TOOL_DATA", "{}")
    try:
        tool_data = json.loads(tool_data_str)
    except json.JSONDecodeError:
        return 0

    tool_name = tool_data.get("name", "")
    if not tool_name:
        return 0

    # Detect component type
    component_type = None
    component_name = None

    if tool_name.startswith("Skill:"):
        component_type = "skill"
        component_name = tool_name.replace("Skill:", "").strip()
    elif tool_name.startswith("/"):
        component_type = "command"
        component_name = tool_name[1:].strip()
    else:
        return 0  # Not a tracked component

    if not component_name:
        return 0

    # Get session ID and other metadata
    session_id = os.environ.get("SESSION_ID", "unknown")
    duration_ms = tool_data.get("duration_ms", 0)
    success = tool_data.get("success", True)

    # Track the invocation
    track_invocation(component_name, component_type, session_id, duration_ms, success)

    return 0


if __name__ == "__main__":
    sys.exit(main())
