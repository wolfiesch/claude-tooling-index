"""Binary scanner - extracts metadata from the bin/ directory."""

import os
from datetime import datetime
from pathlib import Path
from typing import List

from ..models import BinaryMetadata


class BinaryScanner:
    """Scan `~/.claude/bin/` for binary files."""

    def __init__(self, bin_dir: Path):
        self.bin_dir = bin_dir

    def scan(self) -> List[BinaryMetadata]:
        """Scan all binaries in the bin directory."""
        binaries = []

        if not self.bin_dir.exists():
            return binaries

        for location in [self.bin_dir, self.bin_dir / ".disabled"]:
            if not location.exists():
                continue

            is_disabled = location.name == ".disabled"

            for binary_file in location.iterdir():
                if not binary_file.is_file():
                    continue

                # Skip hidden files
                if binary_file.name.startswith("."):
                    continue

                try:
                    binary = self._scan_binary(binary_file)
                    if binary:
                        if is_disabled:
                            binary.status = "disabled"
                        binaries.append(binary)
                except Exception as e:
                    # Track error but continue
                    error_binary = BinaryMetadata(
                        name=binary_file.name,
                        origin="unknown",
                        status="error",
                        last_modified=datetime.now(),
                        install_path=binary_file,
                        error_message=str(e),
                    )
                    binaries.append(error_binary)

        return binaries

    def _scan_binary(self, binary_file: Path) -> BinaryMetadata:
        """Scan a single binary file."""
        name = binary_file.name

        # Detect language
        language = self._detect_language(binary_file)

        # Get file size
        file_size = binary_file.stat().st_size

        # Check if executable
        is_executable = os.access(binary_file, os.X_OK)

        # Get last modified time
        last_modified = datetime.fromtimestamp(binary_file.stat().st_mtime)

        # Binaries in ~/.claude/bin/ are typically in-house
        origin = "in-house"
        status = "active" if is_executable else "error"

        return BinaryMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=binary_file,
            language=language,
            file_size=file_size,
            is_executable=is_executable,
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from extension or shebang."""
        # Check extension first
        ext = file_path.suffix
        if ext == ".py":
            return "python"
        elif ext == ".sh" or ext == ".bash":
            return "bash"
        elif ext == ".js":
            return "javascript"
        elif ext == ".rb":
            return "ruby"
        elif ext == ".pl":
            return "perl"

        # Check shebang for extensionless files
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(4)

                # Check for ELF magic number (compiled binary)
                if first_bytes == b"\x7fELF":
                    return "compiled"

                # Check for Mach-O magic number (macOS binary)
                if first_bytes in [
                    b"\xfe\xed\xfa\xce",
                    b"\xfe\xed\xfa\xcf",
                    b"\xcf\xfa\xed\xfe",
                    b"\xce\xfa\xed\xfe",
                ]:
                    return "compiled"

                # Try to read as text for shebang
                f.seek(0)
                first_line = f.readline().decode("utf-8", errors="ignore")

                if first_line.startswith("#!"):
                    if "python" in first_line:
                        return "python"
                    elif "bash" in first_line or "sh" in first_line:
                        return "bash"
                    elif "node" in first_line:
                        return "javascript"
                    elif "ruby" in first_line:
                        return "ruby"
                    elif "perl" in first_line:
                        return "perl"

        except (OSError, UnicodeDecodeError):
            pass

        return "unknown"
