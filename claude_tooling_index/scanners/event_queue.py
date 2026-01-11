"""Event queue scanner - extracts analytics from `event_queue.jsonl`."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import EventMetrics


class EventQueueScanner:
    """Scan `event_queue.jsonl` for tool usage and session analytics."""

    def __init__(self, event_queue_path: Optional[Path] = None):
        self.event_queue_path = event_queue_path or (
            Path.home() / ".claude" / "data" / "event_queue.jsonl"
        )

    def scan(self) -> Optional[EventMetrics]:
        """Scan event queue and extract analytics."""
        if not self.event_queue_path.exists():
            return None

        result = EventMetrics()
        tool_counter = Counter()
        event_type_counter = Counter()
        permission_counter = Counter()
        session_ids = set()
        timestamps = []

        try:
            with open(self.event_queue_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        self._process_event(
                            event,
                            tool_counter,
                            event_type_counter,
                            permission_counter,
                            session_ids,
                            timestamps,
                        )
                        result.total_events += 1
                    except json.JSONDecodeError:
                        continue

        except IOError:
            return None

        # Populate result
        result.tool_frequency = dict(tool_counter)
        result.top_tools = tool_counter.most_common(15)
        result.event_types = dict(event_type_counter)
        result.session_count = len(session_ids)

        # Calculate permission distribution
        total_permissions = sum(permission_counter.values())
        if total_permissions > 0:
            result.permission_distribution = {
                mode: count / total_permissions
                for mode, count in permission_counter.items()
            }

        # Date range
        if timestamps:
            result.date_range_start = min(timestamps)
            result.date_range_end = max(timestamps)

        return result

    def _process_event(
        self,
        event: dict,
        tool_counter: Counter,
        event_type_counter: Counter,
        permission_counter: Counter,
        session_ids: set,
        timestamps: list,
    ) -> None:
        """Process a single event record."""
        # Extract event type
        event_type = event.get("hook_event_type", "unknown")
        event_type_counter[event_type] += 1

        # Extract session ID
        session_id = event.get("session_id")
        if session_id:
            session_ids.add(session_id)

        # Extract timestamp
        ts = event.get("timestamp")
        if ts:
            try:
                # Timestamps are in milliseconds
                dt = datetime.fromtimestamp(ts / 1000)
                timestamps.append(dt)
            except (ValueError, TypeError, OSError):
                pass

        # Extract payload details
        payload = event.get("payload", {})

        # Permission mode
        permission_mode = payload.get("permission_mode", "unknown")
        permission_counter[permission_mode] += 1

        # Extract tool name for PreToolUse/PostToolUse events
        if event_type in ("PreToolUse", "PostToolUse"):
            tool_name = self._extract_tool_name(payload)
            if tool_name:
                tool_counter[tool_name] += 1

    def _extract_tool_name(self, payload: dict) -> Optional[str]:
        """Extract tool name from event payload."""
        # Try different possible locations for tool name
        tool_name = payload.get("tool_name")
        if tool_name:
            return tool_name

        # Check in nested tool_input
        tool_input = payload.get("tool_input", {})
        if isinstance(tool_input, dict):
            # Some events have name in tool_input
            name = tool_input.get("name")
            if name:
                return name

        # Check hook_event_name for clues
        hook_name = payload.get("hook_event_name", "")
        if ":" in hook_name:
            # Format might be "PreToolUse:ToolName"
            parts = hook_name.split(":")
            if len(parts) >= 2:
                return parts[1]

        return None
