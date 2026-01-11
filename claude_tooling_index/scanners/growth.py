"""Growth Scanner - extracts L1-L5 progression metrics from agentic-growth framework"""

import json
import re
from pathlib import Path
from typing import Optional

from ..models import GrowthMetrics


class GrowthScanner:
    """Scans agentic-growth framework for progression metrics"""

    def __init__(self, growth_dir: Optional[Path] = None):
        self.growth_dir = growth_dir or (Path.home() / ".claude" / "agentic-growth")

    def scan(self) -> Optional[GrowthMetrics]:
        """Scan growth framework and extract metrics"""
        if not self.growth_dir.exists():
            return None

        result = GrowthMetrics()

        # Count edges by category
        edges_dir = self.growth_dir / "edges"
        if edges_dir.exists():
            result.total_edges = self._count_edges(edges_dir)
            result.edges_by_category = self._categorize_edges(edges_dir)

        # Count patterns
        patterns_dir = self.growth_dir / "patterns"
        if patterns_dir.exists():
            result.total_patterns = self._count_patterns(patterns_dir)
            result.patterns_by_category = self._categorize_patterns(patterns_dir)

        # Parse progression level
        progression_file = self.growth_dir / "progression.md"
        if progression_file.exists():
            result.current_level = self._parse_progression_level(progression_file)

        # Parse project-edges mapping
        project_edges = self.growth_dir / "project-edges.json"
        if project_edges.exists():
            result.projects_with_edges = self._count_project_edges(project_edges)

        return result

    def _count_edges(self, edges_dir: Path) -> int:
        """Count total edge files (EDGE-XXX.md)"""
        count = 0
        try:
            for subdir in edges_dir.iterdir():
                if subdir.is_dir():
                    count += len(list(subdir.glob("EDGE-*.md")))
        except OSError:
            pass
        return count

    def _categorize_edges(self, edges_dir: Path) -> dict:
        """Count edges by category subdirectory"""
        categories = {}
        try:
            for subdir in edges_dir.iterdir():
                if subdir.is_dir() and subdir.name not in ("index.md",):
                    edge_count = len(list(subdir.glob("EDGE-*.md")))
                    if edge_count > 0:
                        categories[subdir.name] = edge_count
        except OSError:
            pass
        return categories

    def _count_patterns(self, patterns_dir: Path) -> int:
        """Count total pattern files"""
        count = 0
        try:
            for subdir in patterns_dir.iterdir():
                if subdir.is_dir():
                    count += len(list(subdir.glob("PATTERN-*.md")))
        except OSError:
            pass
        return count

    def _categorize_patterns(self, patterns_dir: Path) -> dict:
        """Count patterns by category"""
        categories = {}
        try:
            for subdir in patterns_dir.iterdir():
                if subdir.is_dir() and subdir.name not in ("index.md",):
                    pattern_count = len(list(subdir.glob("PATTERN-*.md")))
                    if pattern_count > 0:
                        categories[subdir.name] = pattern_count
        except OSError:
            pass
        return categories

    def _parse_progression_level(self, progression_file: Path) -> str:
        """Extract current L1-L5 level from progression.md"""
        try:
            content = progression_file.read_text()
            # Look for patterns like "L4" or "L4: Meta-Engineer" with CURRENT marker
            # Pattern 1: "L4: Meta-Engineer ← *CURRENT LEVEL*"
            match = re.search(r"(L[1-5])[^*]*\*CURRENT", content)
            if match:
                return match.group(1)

            # Pattern 2: "*Current Position*: L4" or "**Current**: L4"
            match = re.search(r"[Cc]urrent[^:]*:\s*(L[1-5])", content)
            if match:
                return match.group(1)

            # Pattern 3: Look for the highest level marked as achieved
            levels_found = re.findall(r"(L[1-5]).*(?:✅|achieved|complete)", content, re.I)
            if levels_found:
                # Return highest level
                return max(levels_found, key=lambda x: int(x[1]))

        except IOError:
            pass
        return "L1"  # Default

    def _count_project_edges(self, project_edges_file: Path) -> int:
        """Count projects with documented edges"""
        try:
            data = json.loads(project_edges_file.read_text())
            # Exclude _comment and _categories keys
            return len([k for k in data.keys() if not k.startswith("_")])
        except (IOError, json.JSONDecodeError):
            return 0
