"""Main scanner orchestrator - coordinates all component scanners"""

from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .models import ScanResult
from .scanners import (
    SkillScanner,
    PluginScanner,
    CommandScanner,
    HookScanner,
    MCPScanner,
    BinaryScanner,
)


class ToolingScanner:
    """Scans ~/.claude directory and extracts all component metadata"""

    def __init__(self, claude_home: Optional[Path] = None):
        self.claude_home = claude_home or self._detect_claude_home()

        # Initialize all scanners
        self.skills_scanner = SkillScanner(self.claude_home / "skills")
        self.plugins_scanner = PluginScanner(self.claude_home / "plugins")
        self.commands_scanner = CommandScanner(self.claude_home / "commands")
        self.hooks_scanner = HookScanner(self.claude_home / "hooks")
        self.mcps_scanner = MCPScanner(self.claude_home / "mcp.json")
        self.binaries_scanner = BinaryScanner(self.claude_home / "bin")

    def scan_all(self, parallel: bool = True) -> ScanResult:
        """
        Scan all components in parallel or sequentially.

        Args:
            parallel: If True, run scanners in parallel (faster).
                      If False, run sequentially (easier debugging).

        Returns:
            ScanResult with all scanned components
        """
        scan_start = datetime.now()
        errors = []

        if parallel:
            result = self._scan_parallel(errors)
        else:
            result = self._scan_sequential(errors)

        result.scan_time = datetime.now()
        result.errors = errors

        return result

    def _scan_parallel(self, errors: list) -> ScanResult:
        """Scan all components in parallel using ThreadPoolExecutor"""
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit all scanner tasks
            futures = {
                "skills": executor.submit(self._safe_scan, self.skills_scanner.scan, "skills", errors),
                "plugins": executor.submit(self._safe_scan, self.plugins_scanner.scan, "plugins", errors),
                "commands": executor.submit(self._safe_scan, self.commands_scanner.scan, "commands", errors),
                "hooks": executor.submit(self._safe_scan, self.hooks_scanner.scan, "hooks", errors),
                "mcps": executor.submit(self._safe_scan, self.mcps_scanner.scan, "mcps", errors),
                "binaries": executor.submit(self._safe_scan, self.binaries_scanner.scan, "binaries", errors),
            }

            # Collect results
            return ScanResult(
                skills=futures["skills"].result(),
                plugins=futures["plugins"].result(),
                commands=futures["commands"].result(),
                hooks=futures["hooks"].result(),
                mcps=futures["mcps"].result(),
                binaries=futures["binaries"].result(),
            )

    def _scan_sequential(self, errors: list) -> ScanResult:
        """Scan all components sequentially (for debugging)"""
        return ScanResult(
            skills=self._safe_scan(self.skills_scanner.scan, "skills", errors),
            plugins=self._safe_scan(self.plugins_scanner.scan, "plugins", errors),
            commands=self._safe_scan(self.commands_scanner.scan, "commands", errors),
            hooks=self._safe_scan(self.hooks_scanner.scan, "hooks", errors),
            mcps=self._safe_scan(self.mcps_scanner.scan, "mcps", errors),
            binaries=self._safe_scan(self.binaries_scanner.scan, "binaries", errors),
        )

    def _safe_scan(self, scan_func, component_type: str, errors: list):
        """Wrapper to catch and log scanner errors"""
        try:
            return scan_func()
        except Exception as e:
            error_msg = f"Error scanning {component_type}: {str(e)}"
            errors.append(error_msg)
            return []  # Return empty list on error

    def _detect_claude_home(self) -> Path:
        """Auto-detect ~/.claude directory"""
        claude_home = Path.home() / ".claude"

        if not claude_home.exists():
            raise ValueError(
                "~/.claude directory not found. Install Claude Code first."
            )

        return claude_home
