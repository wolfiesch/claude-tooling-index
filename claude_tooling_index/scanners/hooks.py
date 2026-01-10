"""Hook scanner - extracts metadata from hook files"""

from pathlib import Path
from datetime import datetime
from typing import List

from ..models import HookMetadata


class HookScanner:
    """Scans ~/.claude/hooks/ directory for hook files"""

    def __init__(self, hooks_dir: Path):
        self.hooks_dir = hooks_dir

    def scan(self) -> List[HookMetadata]:
        """Scan all hooks in the hooks directory"""
        hooks = []

        if not self.hooks_dir.exists():
            return hooks

        for hook_file in self.hooks_dir.iterdir():
            if not hook_file.is_file():
                continue

            # Skip hidden files
            if hook_file.name.startswith("."):
                continue

            try:
                hook = self._scan_hook(hook_file)
                if hook:
                    hooks.append(hook)
            except Exception as e:
                # Track error but continue
                error_hook = HookMetadata(
                    name=hook_file.name,
                    origin="unknown",
                    status="error",
                    last_modified=datetime.now(),
                    install_path=hook_file,
                    error_message=str(e),
                )
                hooks.append(error_hook)

        return hooks

    def _scan_hook(self, hook_file: Path) -> HookMetadata:
        """Scan a single hook file"""
        name = hook_file.name

        # Detect language from extension or shebang
        language = self._detect_language(hook_file)

        # Extract trigger from filename (e.g., "post_tool_use" from "post_tool_use.py")
        trigger = hook_file.stem

        # Get file size
        file_size = hook_file.stat().st_size

        # Get last modified time
        last_modified = datetime.fromtimestamp(hook_file.stat().st_mtime)

        # Detect origin
        origin = "in-house"
        if "tooling" in name.lower():
            origin = "official"  # Installed by tooling-index

        status = "active"

        return HookMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=hook_file,
            trigger=trigger,
            language=language,
            file_size=file_size,
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from extension or shebang"""
        # Check extension first
        ext = file_path.suffix
        if ext == ".py":
            return "python"
        elif ext == ".sh" or ext == ".bash":
            return "bash"
        elif ext == ".js":
            return "javascript"
        elif ext == "" or ext == ".out":
            # Check shebang for extensionless files
            try:
                with open(file_path, "rb") as f:
                    first_line = f.readline().decode("utf-8", errors="ignore")
                    if first_line.startswith("#!"):
                        if "python" in first_line:
                            return "python"
                        elif "bash" in first_line or "sh" in first_line:
                            return "bash"
                        elif "node" in first_line:
                            return "javascript"
                    # If no shebang, might be a compiled binary
                    return "cpp"  # Assume C++ for tooling-index hook
            except (OSError, UnicodeDecodeError):
                pass

        return "unknown"
