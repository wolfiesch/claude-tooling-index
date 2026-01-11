"""Skill scanner - extracts metadata from SKILL.md files"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
import yaml

from ..models import SkillMetadata


class PerformanceMetricsExtractor:
    """Extract performance metrics from SKILL.md files"""

    def extract_metrics(self, skill_md_content: str) -> Optional[Dict]:
        """
        Extract performance metrics from SKILL.md.
        Priority: Markdown tables > Regex patterns
        """
        # Try table parsing first
        table_metrics = self._parse_tables(skill_md_content)
        if table_metrics:
            return table_metrics

        # Fallback to regex patterns
        return self._parse_text_patterns(skill_md_content)

    def _parse_tables(self, content: str) -> Optional[Dict]:
        """Parse markdown tables for performance data"""
        # Look for performance-related section headers
        perf_section = self._extract_section(
            content, ["## Performance", "### Performance", "## Benchmarks"]
        )
        if not perf_section:
            return None

        # Parse markdown table
        tables = self._extract_markdown_tables(perf_section)
        if not tables:
            return None

        metrics = {}
        for table in tables:
            # Expected headers: Operation, Time, Speedup, etc.
            for row in table["rows"]:
                operation = row.get("Operation") or row.get("operation")
                time = (
                    row.get("Gateway CLI")
                    or row.get("Time")
                    or row.get("time")
                )
                speedup = row.get("Speedup") or row.get("speedup")

                if operation:
                    metrics[operation] = {"time": time, "speedup": speedup}

        return metrics if metrics else None

    def _parse_text_patterns(self, content: str) -> Optional[Dict]:
        """Fallback: Extract metrics using regex patterns"""
        metrics = {}

        # Pattern 1: "5.6x faster"
        speedup_pattern = r"(\d+\.?\d*)[xX]\s*(faster|speedup)"
        for match in re.finditer(speedup_pattern, content):
            speedup = match.group(1)
            metrics["speedup"] = f"{speedup}x"

        # Pattern 2: "~300ms" or "300 ms"
        time_pattern = r"~?(\d+)\s*(ms|milliseconds)"
        for match in re.finditer(time_pattern, content):
            time_ms = match.group(1)
            metrics["execution_time"] = f"{time_ms}ms"

        # Pattern 3: "saves 800 tokens"
        token_pattern = r"saves?\s+(\d+)\s+tokens?"
        for match in re.finditer(token_pattern, content):
            tokens = match.group(1)
            metrics["token_savings"] = f"{tokens} tokens"

        return metrics if metrics else None

    def _extract_section(
        self, content: str, headers: List[str]
    ) -> Optional[str]:
        """Extract content under section headers"""
        for header in headers:
            pattern = rf"{re.escape(header)}.*?\n(.*?)(?=\n#{1,3}\s|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return None

    def _extract_markdown_tables(self, section: str) -> List[Dict]:
        """Parse markdown tables into structured data"""
        tables = []
        # Split by table boundaries (header row with pipes)
        table_pattern = r"\|.*?\|\n\|[-:\s|]+\|\n((?:\|.*?\|\n)+)"
        for match in re.finditer(table_pattern, section):
            table_text = match.group(0)
            tables.append(self._parse_single_table(table_text))
        return tables

    def _parse_single_table(self, table_text: str) -> Dict:
        """Parse a single markdown table"""
        lines = [l.strip() for l in table_text.split("\n") if l.strip()]

        # Extract headers
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split("|") if h.strip()]

        # Extract rows (skip separator line at index 1)
        rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) == len(headers):
                row_dict = dict(zip(headers, cells))
                rows.append(row_dict)

        return {"headers": headers, "rows": rows}


class SkillScanner:
    """Scans ~/.claude/skills/ directory for skill metadata"""

    def __init__(self, skills_dir: Path, platform: str = "claude", origin: str = "in-house"):
        self.skills_dir = skills_dir
        self.platform = platform
        self.origin = origin
        self.perf_extractor = PerformanceMetricsExtractor()

    def scan(self) -> List[SkillMetadata]:
        """Scan all skills in the skills directory"""
        skills = []

        if not self.skills_dir.exists():
            return skills

        # Scan both active skills and disabled skills
        for location in [self.skills_dir, self.skills_dir / ".disabled"]:
            if not location.exists():
                continue

            is_disabled = location.name == ".disabled"

            for skill_path in location.iterdir():
                if not skill_path.is_dir():
                    continue

                # Skip hidden directories and common non-skill dirs
                if skill_path.name.startswith(".") and not is_disabled:
                    continue

                try:
                    skill = self._scan_skill(skill_path, is_disabled)
                    if skill:
                        skills.append(skill)
                except Exception as e:
                    # Track error but continue scanning
                    error_skill = SkillMetadata(
                        name=skill_path.name,
                        origin="unknown",
                        status="error",
                        last_modified=datetime.now(),
                        install_path=skill_path,
                        platform=self.platform,
                        error_message=str(e),
                    )
                    skills.append(error_skill)

        return skills

    def _scan_skill(
        self, skill_path: Path, is_disabled: bool = False
    ) -> Optional[SkillMetadata]:
        """Scan a single skill directory"""
        skill_md = skill_path / "SKILL.md"

        # Must have SKILL.md to be a valid skill
        if not skill_md.exists():
            return None

        # Parse SKILL.md
        content = skill_md.read_text()
        frontmatter = self._extract_frontmatter(content)

        # Extract metadata
        name = frontmatter.get("name", skill_path.name)
        description = frontmatter.get("description", "")
        version = frontmatter.get("version")

        # Count files and lines
        file_count, total_lines = self._count_files_and_lines(skill_path)

        # Extract performance metrics
        perf_metrics = self.perf_extractor.extract_metrics(content)

        # Get last modified time
        last_modified = datetime.fromtimestamp(skill_md.stat().st_mtime)

        # Detect origin (will be refined by OriginDetector later)
        origin = self.origin

        status = "disabled" if is_disabled else "active"

        return SkillMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=skill_path,
            platform=self.platform,
            version=version,
            description=description,
            file_count=file_count,
            total_lines=total_lines,
            has_docs=skill_md.exists(),
            performance_notes=json.dumps(perf_metrics)
            if perf_metrics
            else None,
            dependencies=[],  # TODO: Extract from requirements or imports
        )

    def _extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from SKILL.md"""
        # Match YAML frontmatter between --- markers
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _count_files_and_lines(self, skill_path: Path) -> tuple[int, int]:
        """Count files and total lines in skill directory"""
        file_count = 0
        total_lines = 0

        exclude_patterns = [
            "__pycache__",
            ".pyc",
            "node_modules",
            ".git",
            "target/debug",
            "target/release",
        ]

        for file_path in skill_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip excluded patterns
            if any(pattern in str(file_path) for pattern in exclude_patterns):
                continue

            file_count += 1

            # Count lines for text files
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    total_lines += sum(1 for _ in f)
            except (UnicodeDecodeError, PermissionError):
                # Skip binary or unreadable files
                pass

        return file_count, total_lines
