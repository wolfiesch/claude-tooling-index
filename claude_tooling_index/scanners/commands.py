"""Command scanner - extracts metadata from command .md files"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml

from ..models import CommandMetadata


class CommandScanner:
    """Scans ~/.claude/commands/ directory for command metadata"""

    def __init__(self, commands_dir: Path):
        self.commands_dir = commands_dir

    def scan(self) -> List[CommandMetadata]:
        """Scan all commands in the commands directory"""
        commands = []

        if not self.commands_dir.exists():
            return commands

        for command_file in self.commands_dir.glob("*.md"):
            try:
                command = self._scan_command(command_file)
                if command:
                    commands.append(command)
            except Exception as e:
                # Track error but continue
                error_command = CommandMetadata(
                    name=command_file.stem,
                    origin="unknown",
                    status="error",
                    last_modified=datetime.now(),
                    install_path=command_file,
                    error_message=str(e),
                )
                commands.append(error_command)

        return commands

    def _scan_command(self, command_file: Path) -> CommandMetadata:
        """Scan a single command file"""
        content = command_file.read_text()
        frontmatter = self._extract_frontmatter(content)

        name = command_file.stem  # filename without .md
        description = frontmatter.get("description", "")

        # Get last modified time
        last_modified = datetime.fromtimestamp(command_file.stat().st_mtime)

        # Commands in ~/.claude/commands/ are typically in-house
        origin = "in-house"
        status = "active"

        return CommandMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=command_file,
            description=description,
            from_plugin=None,  # TODO: Detect if from plugin
        )

    def _extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from command .md file"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}
