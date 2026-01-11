"""Multi-platform scanner - merges Claude + Codex scan results."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .models import ScanResult
from .scanner import ToolingScanner
from .codex_scanner import CodexToolingScanner


class MultiToolingScanner:
    """Scan one or more platforms and merge results into a single ScanResult."""

    def __init__(
        self,
        claude_home: Optional[Path] = None,
        codex_home: Optional[Path] = None,
    ):
        self._claude_home = claude_home
        self._codex_home = codex_home

    def scan_all(self, platform: str = "claude", parallel: bool = True) -> ScanResult:
        scan_time = datetime.now()
        errors: List[str] = []

        platform = (platform or "claude").lower()
        if platform not in {"claude", "codex", "all"}:
            raise ValueError("platform must be one of: claude, codex, all")

        if platform == "claude":
            return self._scan_claude(parallel=parallel)
        if platform == "codex":
            return self._scan_codex(parallel=parallel)

        # platform == "all"
        if parallel:
            with ThreadPoolExecutor(max_workers=2) as executor:
                claude_future = executor.submit(self._try_scan_claude, errors)
                codex_future = executor.submit(self._try_scan_codex, errors)
                claude_result = claude_future.result()
                codex_result = codex_future.result()
        else:
            claude_result = self._try_scan_claude(errors)
            codex_result = self._try_scan_codex(errors)

        merged = self._merge_results(claude_result, codex_result)
        merged.scan_time = scan_time
        merged.errors = (claude_result.errors or []) + (codex_result.errors or []) + errors
        return merged

    def _scan_claude(self, parallel: bool) -> ScanResult:
        scanner = ToolingScanner(claude_home=self._claude_home)
        return scanner.scan_all(parallel=parallel)

    def _scan_codex(self, parallel: bool) -> ScanResult:
        scanner = CodexToolingScanner(codex_home=self._codex_home)
        return scanner.scan_all(parallel=parallel)

    def _try_scan_claude(self, errors: List[str]) -> ScanResult:
        try:
            return self._scan_claude(parallel=True)
        except Exception as e:
            errors.append(f"[claude] scan failed: {e}")
            return ScanResult()

    def _try_scan_codex(self, errors: List[str]) -> ScanResult:
        try:
            return self._scan_codex(parallel=True)
        except Exception as e:
            errors.append(f"[codex] scan failed: {e}")
            return ScanResult()

    def _merge_results(self, a: ScanResult, b: ScanResult) -> ScanResult:
        return ScanResult(
            skills=(a.skills or []) + (b.skills or []),
            plugins=(a.plugins or []) + (b.plugins or []),
            commands=(a.commands or []) + (b.commands or []),
            hooks=(a.hooks or []) + (b.hooks or []),
            mcps=(a.mcps or []) + (b.mcps or []),
            binaries=(a.binaries or []) + (b.binaries or []),
        )

