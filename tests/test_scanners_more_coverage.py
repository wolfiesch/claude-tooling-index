from __future__ import annotations

import os
from pathlib import Path

from claude_tooling_index.multi_scanner import MultiToolingScanner
from claude_tooling_index.scanners import BinaryScanner, HookScanner


def test_hook_scanner_detects_multiple_languages_and_error_path(
    mock_claude_home: Path, monkeypatch
) -> None:
    hooks_dir = mock_claude_home / "hooks"

    (hooks_dir / ".hidden").write_text("ignored\n")
    (hooks_dir / "a.py").write_text("print('x')\n")
    (hooks_dir / "b.sh").write_text("#!/usr/bin/env bash\necho hi\n")
    (hooks_dir / "c.js").write_text("#!/usr/bin/env node\nconsole.log('x')\n")

    extless_cpp = hooks_dir / "compiled-hook"
    extless_cpp.write_text("not a script\n")

    extless_py = hooks_dir / "py-hook"
    extless_py.write_text("#!/usr/bin/env python3\nprint('x')\n")

    # Force one file down the scanner error branch.
    original_scan_hook = HookScanner._scan_hook

    def raise_for_one(self: HookScanner, hook_file: Path):
        if hook_file.name == "b.sh":
            raise RuntimeError("boom")
        return original_scan_hook(self, hook_file)

    monkeypatch.setattr(HookScanner, "_scan_hook", raise_for_one)

    hooks = HookScanner(hooks_dir).scan()
    by_name = {h.name: h for h in hooks}
    assert by_name["a.py"].language == "python"
    assert by_name["c.js"].language == "javascript"
    assert by_name["compiled-hook"].language == "cpp"
    assert by_name["py-hook"].language == "python"
    assert by_name["b.sh"].status == "error"


def test_binary_scanner_detects_magic_numbers_shebang_and_error_path(
    mock_claude_home: Path, monkeypatch
) -> None:
    bin_dir = mock_claude_home / "bin"

    (bin_dir / ".hidden").write_text("ignored\n")
    (bin_dir / "a.py").write_text("print('x')\n")
    (bin_dir / "b.rb").write_text("#!/usr/bin/env ruby\nputs 'x'\n")
    (bin_dir / "c.pl").write_text("#!/usr/bin/env perl\nprint \"x\";\n")
    (bin_dir / "d.js").write_text("#!/usr/bin/env node\nconsole.log('x')\n")

    elf = bin_dir / "elf-bin"
    elf.write_bytes(b"\x7fELF" + b"\x00" * 10)
    os.chmod(elf, 0o755)

    macho = bin_dir / "macho-bin"
    macho.write_bytes(b"\xfe\xed\xfa\xcf" + b"\x00" * 10)
    os.chmod(macho, 0o755)

    extless_bash = bin_dir / "bash-bin"
    extless_bash.write_text("#!/usr/bin/env bash\necho hi\n")
    os.chmod(extless_bash, 0o755)

    unknown = bin_dir / "unknown"
    unknown.write_bytes(b"ABCD")
    os.chmod(unknown, 0o755)

    original_scan_binary = BinaryScanner._scan_binary

    def raise_for_one(self: BinaryScanner, binary_file: Path):
        if binary_file.name == "a.py":
            raise RuntimeError("boom")
        return original_scan_binary(self, binary_file)

    monkeypatch.setattr(BinaryScanner, "_scan_binary", raise_for_one)

    binaries = BinaryScanner(bin_dir).scan()
    by_name = {b.name: b for b in binaries}
    assert by_name["elf-bin"].language == "compiled"
    assert by_name["macho-bin"].language == "compiled"
    assert by_name["bash-bin"].language == "bash"
    assert by_name["unknown"].language == "unknown"
    assert by_name["a.py"].status == "error"


def test_multi_scanner_records_claude_scan_failure(monkeypatch, tmp_path: Path) -> None:
    # Patch Path.home to a temp without ~/.claude so ToolingScanner auto-detect fails.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    scanner = MultiToolingScanner()
    result = scanner.scan_all(platform="all", parallel=False)
    assert result.errors
    assert any("claude" in e for e in result.errors)

