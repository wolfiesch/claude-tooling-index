"""Codex scanner orchestrator - scans ~/.codex for supported components."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .models import ScanResult
from .scanners.skills import SkillScanner
from .scanners.codex_mcps import CodexMCPScanner


class CodexToolingScanner:
    """Scans ~/.codex directory and extracts supported component metadata."""

    def __init__(self, codex_home: Optional[Path] = None):
        self.codex_home = codex_home or self._detect_codex_home()

        self.skills_scanner = SkillScanner(
            self.codex_home / "skills", platform="codex", origin="in-house"
        )
        self.mcps_scanner = CodexMCPScanner(self.codex_home / "config.toml")

    def scan_all(self, parallel: bool = True) -> ScanResult:
        scan_start = datetime.now()
        errors: List[str] = []

        if parallel:
            with ThreadPoolExecutor(max_workers=2) as executor:
                skills_future = executor.submit(self._safe_scan, self.skills_scanner.scan, "skills", errors)
                mcps_future = executor.submit(self._safe_scan, self.mcps_scanner.scan, "mcps", errors)

                result = ScanResult(
                    skills=skills_future.result(),
                    plugins=[],
                    commands=[],
                    hooks=[],
                    mcps=mcps_future.result(),
                    binaries=[],
                )
        else:
            result = ScanResult(
                skills=self._safe_scan(self.skills_scanner.scan, "skills", errors),
                plugins=[],
                commands=[],
                hooks=[],
                mcps=self._safe_scan(self.mcps_scanner.scan, "mcps", errors),
                binaries=[],
            )

        result.scan_time = datetime.now()
        result.errors = errors
        return result

    def _safe_scan(self, scan_func, component_type: str, errors: list):
        try:
            return scan_func()
        except Exception as e:
            errors.append(f"[codex] Error scanning {component_type}: {e}")
            return []

    def _detect_codex_home(self) -> Path:
        codex_home = Path.home() / ".codex"
        if not codex_home.exists():
            raise ValueError("~/.codex directory not found. Install Codex CLI first.")
        return codex_home
