"""Claude home scanner orchestrator.

This module coordinates all component scanners for a single Claude home
directory (typically `~/.claude`).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ExtendedScanResult, ScanResult
from .scanners import (
    BinaryScanner,
    CommandScanner,
    EventQueueScanner,
    GrowthScanner,
    HookScanner,
    InsightsScanner,
    MCPScanner,
    PluginScanner,
    # Phase 6 T1: Session and task analytics
    SessionAnalyticsScanner,
    SkillScanner,
    TodoScanner,
    # Phase 6 T2: Transcript and growth analytics
    TranscriptScanner,
    # Phase 6: Extended metadata scanners
    UserSettingsScanner,
)


class ToolingScanner:
    """Scan a Claude home directory and extract component metadata."""

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
        # Phase 6 T2: Transcript and growth analytics
        self.transcript_scanner = TranscriptScanner(self.claude_home / "projects")
        self.growth_scanner = GrowthScanner(self.claude_home / "agentic-growth")

    def scan_all(self, parallel: bool = True) -> ScanResult:
        """Scan all core components.

        Args:
            parallel: If True, run scanners in parallel (faster).
                If False, run sequentially (easier debugging).

        Returns:
            The scan result with all scanned components and any captured errors.
        """
        errors = []

        if parallel:
            result = self._scan_parallel(errors)
        else:
            result = self._scan_sequential(errors)

        result.scan_time = datetime.now()
        result.errors = errors

        return result

    def _scan_parallel(self, errors: list) -> ScanResult:
        """Scan all components in parallel using `ThreadPoolExecutor`."""
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit all scanner tasks
            futures = {
                "skills": executor.submit(
                    self._safe_scan, self.skills_scanner.scan, "skills", errors
                ),
                "plugins": executor.submit(
                    self._safe_scan, self.plugins_scanner.scan, "plugins", errors
                ),
                "commands": executor.submit(
                    self._safe_scan, self.commands_scanner.scan, "commands", errors
                ),
                "hooks": executor.submit(
                    self._safe_scan, self.hooks_scanner.scan, "hooks", errors
                ),
                "mcps": executor.submit(
                    self._safe_scan, self.mcps_scanner.scan, "mcps", errors
                ),
                "binaries": executor.submit(
                    self._safe_scan, self.binaries_scanner.scan, "binaries", errors
                ),
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
        """Scan all components sequentially (for debugging)."""
        return ScanResult(
            skills=self._safe_scan(self.skills_scanner.scan, "skills", errors),
            plugins=self._safe_scan(self.plugins_scanner.scan, "plugins", errors),
            commands=self._safe_scan(self.commands_scanner.scan, "commands", errors),
            hooks=self._safe_scan(self.hooks_scanner.scan, "hooks", errors),
            mcps=self._safe_scan(self.mcps_scanner.scan, "mcps", errors),
            binaries=self._safe_scan(self.binaries_scanner.scan, "binaries", errors),
        )

    def _safe_scan(self, scan_func, component_type: str, errors: list):
        """Run a scanner function and capture errors instead of raising."""
        try:
            return scan_func()
        except Exception as e:
            error_msg = f"Error scanning {component_type}: {str(e)}"
            errors.append(error_msg)
            return []  # Return empty list on error

    def scan_extended(self, parallel: bool = True) -> ExtendedScanResult:
        """Scan all core components plus Phase 6 extended metadata.

        Args:
            parallel: If True, run scanners in parallel (faster).

        Returns:
            The extended scan result with core components and Phase 6 metrics.
        """
        # Get core scan result
        core_result = self.scan_all(parallel=parallel)

        # Scan extended metadata (these are fast, run sequentially)
        user_settings = None
        event_metrics = None
        insight_metrics = None
        session_metrics = None
        task_metrics = None
        transcript_metrics = None
        growth_metrics = None

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

        # T2: Transcript and growth analytics
        try:
            # Scan all transcript files for accurate token analytics.
            transcript_metrics = self.transcript_scanner.scan(sample_limit=0)
        except Exception as e:
            core_result.errors.append(f"Error scanning transcripts: {e}")

        try:
            growth_metrics = self.growth_scanner.scan()
        except Exception as e:
            core_result.errors.append(f"Error scanning growth: {e}")

        return ExtendedScanResult(
            core=core_result,
            user_settings=user_settings,
            event_metrics=event_metrics,
            insight_metrics=insight_metrics,
            session_metrics=session_metrics,
            task_metrics=task_metrics,
            transcript_metrics=transcript_metrics,
            growth_metrics=growth_metrics,
        )

    def _detect_claude_home(self) -> Path:
        """Auto-detect the Claude home directory (`~/.claude`)."""
        claude_home = Path.home() / ".claude"

        if not claude_home.exists():
            raise ValueError(
                "~/.claude directory not found. Install Claude Code first."
            )

        return claude_home
