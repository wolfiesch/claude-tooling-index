"""Transcript Scanner - extracts token economics and tool usage from JSONL files"""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Optional

from ..models import TranscriptMetrics


class TranscriptScanner:
    """Scans project JSONL transcript files for analytics"""

    def __init__(self, projects_dir: Optional[Path] = None):
        self.projects_dir = projects_dir or (Path.home() / ".claude" / "projects")

    def scan(self, sample_limit: int = 500) -> Optional[TranscriptMetrics]:
        """Scan transcript files and extract metrics.

        Args:
            sample_limit: Max files to scan (for performance). 0 = all files.
        """
        if not self.projects_dir.exists():
            return None

        result = TranscriptMetrics()
        tool_counter = Counter()
        model_counter = Counter()
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_read = 0
        total_cache_create = 0
        file_count = 0

        try:
            # Iterate project directories
            for entry in os.scandir(self.projects_dir):
                if not entry.is_dir():
                    continue

                project_dir = Path(entry.path)

                for jsonl_file in project_dir.glob("*.jsonl"):
                    if sample_limit > 0 and file_count >= sample_limit:
                        break

                    file_count += 1
                    result.total_transcripts += 1

                    # Process file
                    file_tokens = self._process_file(
                        jsonl_file, tool_counter, model_counter
                    )
                    total_input_tokens += file_tokens["input"]
                    total_output_tokens += file_tokens["output"]
                    total_cache_read += file_tokens["cache_read"]
                    total_cache_create += file_tokens["cache_create"]

                if sample_limit > 0 and file_count >= sample_limit:
                    break

        except OSError:
            return None

        # Populate results
        result.tool_usage = dict(tool_counter)
        result.model_usage = dict(model_counter)
        result.top_tools = tool_counter.most_common(20)
        result.total_input_tokens = total_input_tokens
        result.total_output_tokens = total_output_tokens
        result.total_cache_read_tokens = total_cache_read
        result.total_cache_creation_tokens = total_cache_create

        return result

    def _process_file(
        self, jsonl_file: Path, tool_counter: Counter, model_counter: Counter
    ) -> dict:
        """Process a single JSONL file and return token counts"""
        tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}

        try:
            with open(jsonl_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        self._process_line(data, tool_counter, model_counter, tokens)
                    except json.JSONDecodeError:
                        continue
        except IOError:
            pass

        return tokens

    def _process_line(
        self, data: dict, tool_counter: Counter, model_counter: Counter, tokens: dict
    ):
        """Process a single JSONL line"""
        msg_type = data.get("type")

        if msg_type == "assistant" and "message" in data:
            msg = data["message"]

            # Track model usage
            model = msg.get("model")
            if model:
                model_counter[model] += 1

            # Extract token usage
            if "usage" in msg:
                usage = msg["usage"]
                tokens["input"] += usage.get("input_tokens", 0)
                tokens["output"] += usage.get("output_tokens", 0)
                tokens["cache_read"] += usage.get("cache_read_input_tokens", 0)
                tokens["cache_create"] += usage.get("cache_creation_input_tokens", 0)

            # Track tool usage
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_name = item.get("name")
                        if tool_name:
                            tool_counter[tool_name] += 1
