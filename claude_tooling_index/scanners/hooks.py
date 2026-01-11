"""Hook scanner - extracts metadata from hook files."""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from ..models import HookMetadata


class HookScanner:
    """Scan `~/.claude/hooks/` for hook file metadata."""

    def __init__(self, hooks_dir: Path):
        self.hooks_dir = hooks_dir

    def scan(self) -> List[HookMetadata]:
        """Scan all hooks in the hooks directory."""
        hooks = []

        if not self.hooks_dir.exists():
            return hooks

        for location in [self.hooks_dir, self.hooks_dir / ".disabled"]:
            if not location.exists():
                continue

            is_disabled = location.name == ".disabled"

            for hook_file in location.iterdir():
                if not hook_file.is_file():
                    continue

                # Skip hidden files
                if hook_file.name.startswith("."):
                    continue

                try:
                    hook = self._scan_hook(hook_file)
                    if hook:
                        if is_disabled:
                            hook.status = "disabled"
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
        """Scan a single hook file."""
        name = hook_file.name

        # Detect language from extension or shebang
        language = self._detect_language(hook_file)

        # Extract trigger from filename (e.g., "post_tool_use" from "post_tool_use.py")
        trigger = hook_file.stem
        trigger_event = self._detect_trigger_event(trigger)

        # Get file size
        file_size = hook_file.stat().st_size

        # Get last modified time
        last_modified = datetime.fromtimestamp(hook_file.stat().st_mtime)

        shebang = self._read_shebang(hook_file)
        is_executable = (hook_file.stat().st_mode & 0o111) != 0

        content = ""
        try:
            content = hook_file.read_text(errors="ignore")
        except Exception:
            content = ""

        detected_tools, detected_toolkits = self._extract_tool_usage(content)
        required_env_vars = self._extract_required_env_vars(content)
        side_effects, risk_level = self._classify_side_effects_and_risk(
            content, detected_tools=detected_tools, toolkits=detected_toolkits
        )

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
            trigger_event=trigger_event,
            language=language,
            file_size=file_size,
            shebang=shebang,
            is_executable=is_executable,
            detected_tools=detected_tools,
            detected_toolkits=detected_toolkits,
            required_env_vars=required_env_vars,
            side_effects=side_effects,
            risk_level=risk_level,
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

    def _read_shebang(self, file_path: Path) -> str:
        try:
            with open(file_path, "rb") as f:
                first_line = f.readline().decode("utf-8", errors="ignore").strip()
            if first_line.startswith("#!"):
                return first_line
        except Exception:
            return ""
        return ""

    def _detect_trigger_event(self, stem: str) -> str:
        known = ["post_tool_use", "pre_tool_use", "session_start", "session_end"]
        for k in known:
            if stem == k or stem.startswith(k + "_"):
                return k
        return ""

    def _extract_tool_usage(self, content: str) -> Tuple[Dict[str, List[str]], List[str]]:
        mcp_tools: List[str] = []
        composio_tools: List[str] = []
        core_tools: List[str] = []
        toolkits: List[str] = []

        for m in re.finditer(r"\bmcp__([a-z0-9_-]+)__([a-z0-9_-]+)\b", content, re.I):
            full = f"mcp__{m.group(1)}__{m.group(2)}"
            mcp_tools.append(full)
            toolkits.append(m.group(1).lower())

        for m in re.finditer(r"run_composio_tool\(\s*['\"]([A-Z0-9_]+)['\"]", content):
            slug = m.group(1)
            composio_tools.append(slug)
            toolkits.append(slug.split("_", 1)[0].lower())

        for m in re.finditer(
            r"\b(read_file|write_file|apply_patch|exec_command|list_dir)\b", content
        ):
            core_tools.append(m.group(1))

        def dedupe(items: List[str]) -> List[str]:
            seen = set()
            out: List[str] = []
            for it in items:
                if it not in seen:
                    seen.add(it)
                    out.append(it)
            return out

        tools: Dict[str, List[str]] = {}
        mcp_tools = dedupe(mcp_tools)
        composio_tools = dedupe(composio_tools)
        core_tools = dedupe(core_tools)
        toolkits = dedupe([t for t in toolkits if t])
        if core_tools:
            tools["core_tools"] = core_tools
        if mcp_tools:
            tools["mcp_tools"] = mcp_tools
        if composio_tools:
            tools["composio_tools"] = composio_tools
        return tools, toolkits

    def _extract_required_env_vars(self, content: str) -> List[str]:
        names: List[str] = []
        for m in re.finditer(r"\$\{([A-Z0-9_]+)\}", content):
            names.append(m.group(1))
        for line in content.splitlines():
            m = re.match(r"^\s*export\s+([A-Z0-9_]+)\s*=", line)
            if m:
                names.append(m.group(1))
        return list(dict.fromkeys(names))[:50]

    def _classify_side_effects_and_risk(
        self, content: str, *, detected_tools: Dict[str, List[str]], toolkits: List[str]
    ) -> Tuple[List[str], str]:
        side_effects: List[str] = []
        if "gmail" in toolkits:
            side_effects.append("email")
        if "slack" in toolkits:
            side_effects.append("slack")
        if "github" in toolkits:
            side_effects.append("github")
        if "neon" in toolkits:
            side_effects.append("database")
        if detected_tools.get("core_tools"):
            side_effects.append("filesystem")

        lower = content.lower()
        destructive = bool(re.search(r"\b(drop|delete|truncate|reset|destroy)\b", lower))
        if destructive:
            return list(dict.fromkeys(side_effects)), "high"
        if side_effects:
            return list(dict.fromkeys(side_effects)), "medium"
        return [], "low"
