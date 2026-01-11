from __future__ import annotations

from pathlib import Path

from claude_tooling_index.scanners import BinaryScanner, HookScanner


def test_binary_and_hook_scanners_return_empty_when_dirs_missing(tmp_path: Path) -> None:
    assert BinaryScanner(tmp_path / "missing-bin").scan() == []
    assert HookScanner(tmp_path / "missing-hooks").scan() == []

