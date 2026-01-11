from __future__ import annotations

from pathlib import Path

from claude_tooling_index.scanner import ToolingScanner


def test_tooling_scanner_safe_scan_records_errors(mock_claude_home: Path, monkeypatch) -> None:
    scanner = ToolingScanner(claude_home=mock_claude_home)

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(scanner.skills_scanner, "scan", boom)
    result = scanner.scan_all(parallel=False)

    assert result.skills == []
    assert result.errors
    assert any("Error scanning skills" in e for e in result.errors)


def test_tooling_scanner_scan_extended_handles_metric_scanner_failures(
    mock_claude_home: Path, monkeypatch
) -> None:
    scanner = ToolingScanner(claude_home=mock_claude_home)

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(scanner.user_settings_scanner, "scan", boom)
    monkeypatch.setattr(scanner.event_queue_scanner, "scan", boom)
    monkeypatch.setattr(scanner.insights_scanner, "scan", boom)
    monkeypatch.setattr(scanner.sessions_scanner, "scan", boom)
    monkeypatch.setattr(scanner.todos_scanner, "scan", boom)
    monkeypatch.setattr(scanner.transcript_scanner, "scan", boom)
    monkeypatch.setattr(scanner.growth_scanner, "scan", boom)

    extended = scanner.scan_extended(parallel=False)
    assert extended.core.errors
    assert any("Error scanning user settings" in e for e in extended.core.errors)
    assert any("Error scanning growth" in e for e in extended.core.errors)

