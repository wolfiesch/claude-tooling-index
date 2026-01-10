"""Main scanner orchestrator - coordinates all component scanners"""

from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .models import ScanResult, ExtendedScanResult
from .scanners import (
    SkillScanner,
    PluginScanner,
    CommandScanner,
    HookScanner,
    MCPScanner,
    BinaryScanner,
    # Phase 6: Extended metadata scanners
    UserSettingsScanner,
    EventQueueScanner,
    InsightsScanner,
    # Phase 6 T1: Session and task analytics
    SessionAnalyticsScanner,
    TodoScanner,
)


class ToolingScanner:
    """Scans ~/.claude directory and extracts all component metadata"""

    def __init__(self, claude_home: Optional[Path] = None):
        self.claude_home = claude_home or self._detect_claude_home()

        # Initialize core component scanners
        self.skills_scanner = SkillScanner(self.claude_home / "skills")
        self.plugins_scanner = PluginScanner(self.claude_home / "plugins")
        self.commands_scanner = CommandScanner(self.claude_home / "commands")
        self.hooks_scanner = HookScanner(self.claude_home / "hooks")
        self.mcps_scanner = MCPScanner(self.claude_home / "mcp.json")
        self.binaries_scanner = BinaryScanner(self.claude_home / "bin")

        # Phase 6: Extended metadata scanners
        self.user_settings_scanner = UserSettingsScanner()
        self.event_queue_scanner = EventQueueScanner(
            self.claude_home / "data" / "event_queue.jsonl"
        )
        self.insights_scanner = InsightsScanner(
            self.claude_home / "data" / "insights.db"
        )
        # Phase 6 T1: Session and task analytics
        self.sessions_scanner = SessionAnalyticsScanner(
            self.claude_home / "data" / "sessions"
        )
        self.todos_scanner = TodoScanner(self.claude_home / "todos")

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

    def scan_extended(self, parallel: bool = True) -> ExtendedScanResult:
        """
        Scan all components plus Phase 6 extended metadata.

        Args:
            parallel: If True, run scanners in parallel (faster).

        Returns:
            ExtendedScanResult with core components and extended metadata
        """
        # Get core scan result
        core_result = self.scan_all(parallel=parallel)

        # Scan extended metadata (these are fast, run sequentially)
        user_settings = None
        event_metrics = None
        insight_metrics = None
        session_metrics = None
        task_metrics = None

        try:
            user_settings = self.user_settings_scanner.scan()
        except Exception as e:
            core_result.errors.append(f"Error scanning user settings: {e}")

        try:
            event_metrics = self.event_queue_scanner.scan()
        except Exception as e:
            core_result.errors.append(f"Error scanning event queue: {e}")

        try:
            insight_metrics = self.insights_scanner.scan()
        except Exception as e:
            core_result.errors.append(f"Error scanning insights: {e}")

        # T1: Session and task analytics
        try:
            session_metrics = self.sessions_scanner.scan()
        except Exception as e:
            core_result.errors.append(f"Error scanning sessions: {e}")

        try:
            task_metrics = self.todos_scanner.scan()
        except Exception as e:
            core_result.errors.append(f"Error scanning todos: {e}")

        return ExtendedScanResult(
            core=core_result,
            user_settings=user_settings,
            event_metrics=event_metrics,
            insight_metrics=insight_metrics,
            session_metrics=session_metrics,
            task_metrics=task_metrics,
        )

    def _detect_claude_home(self) -> Path:
        """Auto-detect ~/.claude directory"""
        claude_home = Path.home() / ".claude"

        if not claude_home.exists():
            raise ValueError(
                "~/.claude directory not found. Install Claude Code first."
            )

        return claude_home
