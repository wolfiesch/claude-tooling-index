"""Command scanner - extracts metadata from command `.md` files."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ..models import CommandMetadata


class CommandScanner:
    """Scan `~/.claude/commands/` for command metadata."""

    def __init__(self, commands_dir: Path):
        self.commands_dir = commands_dir

    def scan(self) -> List[CommandMetadata]:
        """Scan all commands in the commands directory."""
        commands = []

        if not self.commands_dir.exists():
            return commands

        commands.extend(self._scan_plugin_commands())

        for location in [self.commands_dir, self.commands_dir / ".disabled"]:
            if not location.exists():
                continue

            is_disabled = location.name == ".disabled"

            for command_file in location.glob("*.md"):
                try:
                    command = self._scan_command(command_file)
                    if command:
                        if is_disabled:
                            command.status = "disabled"
                        commands.append(command)
                except Exception as e:
                    # Track error but continue
                    error_command = CommandMetadata(
                        name=command_file.stem,
                        origin="unknown",
                        status="error",
                        last_modified=datetime.now(),
                        install_path=command_file,
                        error_message=str(e),
                    )
                    commands.append(error_command)

        return commands

    def _scan_command(self, command_file: Path) -> CommandMetadata:
        """Scan a single command file."""
        content = command_file.read_text()
        frontmatter = self._extract_frontmatter(content)

        name = command_file.stem  # filename without .md
        description = frontmatter.get("description", "")
        frontmatter_extra = self._extract_frontmatter_extra(frontmatter)
        invocation = self._extract_invocation_hints(content, default_name=name)
        references = self._extract_references(content)
        detected_tools, detected_toolkits = self._extract_tool_usage(content)
        io_safety = self._extract_inputs_outputs_safety(content)
        required_env_vars = self._extract_required_env_vars(content)
        prerequisites = self._extract_prerequisites(content)
        gotchas = self._extract_gotchas(content)
        examples = self._extract_examples(content)
        capability_tags = self._derive_capability_tags(
            content, toolkits=detected_toolkits, detected_tools=detected_tools
        )
        side_effects, risk_level = self._classify_side_effects_and_risk(
            content, detected_tools=detected_tools, toolkits=detected_toolkits
        )

        # Get last modified time
        last_modified = datetime.fromtimestamp(command_file.stat().st_mtime)

        # Commands in ~/.claude/commands/ are typically in-house
        origin = "in-house"
        status = "active"

        return CommandMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=command_file,
            description=description,
            from_plugin=None,  # TODO: Detect if from plugin
            frontmatter_extra=frontmatter_extra,
            invocation_aliases=invocation.get("aliases") or [],
            invocation_arguments=invocation.get("arguments") or "",
            invocation_instruction=invocation.get("instruction") or "",
            references=references,
            detected_tools=detected_tools,
            detected_toolkits=detected_toolkits,
            inputs=io_safety.get("inputs") or [],
            outputs=io_safety.get("outputs") or [],
            safety_notes=io_safety.get("safety_notes") or "",
            capability_tags=capability_tags,
            required_env_vars=required_env_vars,
            prerequisites=prerequisites,
            gotchas=gotchas,
            examples=examples,
            side_effects=side_effects,
            risk_level=risk_level,
        )

    def _extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from a command `.md` file."""
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _extract_frontmatter_extra(self, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """Extract non-standard YAML frontmatter fields for display/export."""
        if not isinstance(frontmatter, dict):
            return {}

        standard = {"description"}
        extra = {k: v for k, v in frontmatter.items() if k not in standard}
        return self._json_safe(extra)

    def _json_safe(self, value: Any) -> Any:
        """Convert a value to JSON-serializable primitives."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._json_safe(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        return str(value)

    def _scan_plugin_commands(self) -> List[CommandMetadata]:
        """Scan plugin cache for command definitions and expose as CommandMetadata."""
        commands: List[CommandMetadata] = []

        claude_home = Path.home() / ".claude"
        plugins_cache = claude_home / "plugins" / "cache"
        if not plugins_cache.exists():
            return commands

        plugin_json_paths = list(plugins_cache.glob("*/*/.claude-plugin/plugin.json")) + list(
            plugins_cache.glob("*/*/*/.claude-plugin/plugin.json")
        )

        for plugin_json in plugin_json_paths:
            try:
                data = json.loads(plugin_json.read_text())
            except Exception:
                continue

            plugin_name = data.get("name") or plugin_json.parent.parent.name
            if not isinstance(plugin_name, str) or not plugin_name.strip():
                continue
            plugin_name = plugin_name.strip()

            commands_cfg = data.get("commands")
            if not commands_cfg:
                continue

            details = self._extract_command_details_from_plugin_json(commands_cfg)
            if not details:
                continue

            last_modified = datetime.fromtimestamp(plugin_json.stat().st_mtime)
            for cmd_name, desc in details.items():
                # Avoid DB identity collisions with file-based commands.
                display_name = f"plugin:{plugin_name}:{cmd_name}"
                commands.append(
                    CommandMetadata(
                        name=display_name,
                        origin="plugin",
                        status="active",
                        last_modified=last_modified,
                        install_path=plugin_json,
                        description=desc or "",
                        from_plugin=plugin_name,
                        invocation_aliases=[f"/{cmd_name}"],
                    )
                )

        return commands

    def _extract_command_details_from_plugin_json(self, commands_cfg: Any) -> Dict[str, str]:
        details: Dict[str, str] = {}
        if isinstance(commands_cfg, dict):
            for name, cfg in commands_cfg.items():
                desc = ""
                if isinstance(cfg, dict):
                    maybe = cfg.get("description") or cfg.get("help") or ""
                    if isinstance(maybe, str):
                        desc = maybe.strip()
                details[str(name)] = desc
        elif isinstance(commands_cfg, list):
            for item in commands_cfg:
                if isinstance(item, str):
                    details[item] = ""
                elif isinstance(item, dict) and "name" in item:
                    desc = item.get("description") or item.get("help") or ""
                    details[str(item["name"])] = str(desc).strip() if desc else ""
        return details

    def _extract_invocation_hints(self, content: str, *, default_name: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"aliases": [], "arguments": "", "instruction": ""}
        head = "\n".join(content.splitlines()[:80])

        aliases = re.findall(r"/[A-Za-z0-9_-]+", head)
        if not aliases:
            aliases = [f"/{default_name}"]
        result["aliases"] = list(dict.fromkeys(aliases))

        for line in head.splitlines():
            normalized = line.replace("**", "")
            m = re.search(r"(?i)^\s*arguments?\s*:\s*(.+)$", normalized)
            if m:
                result["arguments"] = m.group(1).strip()
                break

        for line in content.splitlines():
            if re.search(r"@\$\d+\b", line):
                result["instruction"] = line.strip()
                break
        return result

    def _extract_references(self, content: str) -> Dict[str, List[str]]:
        file_refs: List[str] = []
        skill_refs: List[str] = []

        for m in re.finditer(r"@([A-Za-z0-9_./$-]+)", content):
            token = m.group(1)
            if token.startswith("modelcontextprotocol/"):
                continue
            if token.startswith("$"):
                file_refs.append(f"@{token}")
                continue
            if re.search(r"\.(md|txt|json|toml|ya?ml|py|sh)\b", token) or "/" in token:
                file_refs.append(f"@{token}")

        for m in re.finditer(r"\$([A-Za-z][A-Za-z0-9_-]+)", content):
            skill_refs.append(m.group(1))

        def dedupe(items: List[str]) -> List[str]:
            seen = set()
            out: List[str] = []
            for it in items:
                if it not in seen:
                    seen.add(it)
                    out.append(it)
            return out

        refs: Dict[str, List[str]] = {}
        file_refs = dedupe(file_refs)
        skill_refs = dedupe(skill_refs)
        if file_refs:
            refs["files"] = file_refs
        if skill_refs:
            refs["skills"] = skill_refs
        return refs

    def _extract_markdown_sections(self, content: str) -> List[Tuple[str, str]]:
        lines = content.splitlines()
        sections: List[Tuple[str, str]] = []
        current_heading: Optional[str] = None
        current_body: List[str] = []

        def flush() -> None:
            nonlocal current_heading, current_body
            if current_heading is not None:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = None
            current_body = []

        for line in lines:
            m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
            if m:
                flush()
                current_heading = m.group(2)
                continue
            if current_heading is not None:
                current_body.append(line)
        flush()
        return sections

    def _extract_code_blocks(self, content: str) -> List[str]:
        blocks: List[str] = []
        current: List[str] = []
        in_block = False
        for line in content.splitlines():
            if line.strip().startswith("```"):
                if in_block:
                    blocks.append("\n".join(current))
                    current = []
                    in_block = False
                else:
                    in_block = True
                continue
            if in_block:
                current.append(line)
        return blocks

    def _extract_bullets(self, body: str) -> List[str]:
        items: List[str] = []
        for line in body.splitlines():
            m = re.match(r"^\s*[-*]\s+(.+)$", line)
            if m:
                items.append(m.group(1).strip())
        return items

    def _trim_block(self, body: str, *, max_lines: int) -> str:
        lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
        return "\n".join(lines[:max_lines]).strip()

    def _extract_inputs_outputs_safety(self, content: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"inputs": [], "outputs": [], "safety_notes": ""}
        sections = self._extract_markdown_sections(content)

        def norm(h: str) -> str:
            return re.sub(r"[^a-z0-9 ]+", "", h.strip().lower())

        for heading, body in sections:
            key = norm(heading)
            if not result["inputs"] and key in {"inputs", "input", "parameters"}:
                result["inputs"] = self._extract_bullets(body)[:25]
            if not result["outputs"] and key in {"outputs", "output", "returns"}:
                result["outputs"] = self._extract_bullets(body)[:25]
            if not result["safety_notes"] and key in {"safety", "security", "privacy", "redaction"}:
                result["safety_notes"] = self._trim_block(body, max_lines=20)
        return result

    def _extract_tool_usage(self, content: str) -> Tuple[Dict[str, List[str]], List[str]]:
        mcp_tools: List[str] = []
        composio_tools: List[str] = []
        toolkits: List[str] = []
        blocks = self._extract_code_blocks(content)
        haystacks = blocks + [content]

        for text in haystacks:
            for m in re.finditer(r"\bmcp__([a-z0-9_-]+)__([a-z0-9_-]+)\b", text, re.I):
                full = f"mcp__{m.group(1)}__{m.group(2)}"
                mcp_tools.append(full)
                toolkits.append(m.group(1).lower())

            for m in re.finditer(r"run_composio_tool\(\s*['\"]([A-Z0-9_]+)['\"]", text):
                slug = m.group(1)
                composio_tools.append(slug)
                toolkits.append(slug.split("_", 1)[0].lower())

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
        toolkits = dedupe([t for t in toolkits if t])
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

    def _extract_prerequisites(self, content: str) -> List[str]:
        sections = self._extract_markdown_sections(content)
        lines: List[str] = []
        for heading, body in sections:
            if "install" in heading.lower() or "setup" in heading.lower():
                lines.extend(self._extract_bullets(body))
                lines.extend(self._extract_install_commands(body))
        for block in self._extract_code_blocks(content):
            lines.extend(self._extract_install_commands(block))
        return list(dict.fromkeys([item for item in lines if item]))[:25]

    def _extract_install_commands(self, text: str) -> List[str]:
        cmds: List[str] = []
        patterns = [
            r"^\s*(pip3?\s+install\s+.+)$",
            r"^\s*(brew\s+install\s+.+)$",
            r"^\s*(npm\s+(?:i|install)\s+.+)$",
            r"^\s*(pnpm\s+add\s+.+)$",
            r"^\s*(yarn\s+add\s+.+)$",
        ]
        for line in text.splitlines():
            for pat in patterns:
                m = re.match(pat, line.strip())
                if m:
                    cmds.append(m.group(1).strip())
        return cmds

    def _extract_gotchas(self, content: str) -> List[str]:
        sections = self._extract_markdown_sections(content)
        items: List[str] = []
        for heading, body in sections:
            if any(k in heading.lower() for k in ["pitfall", "known issue", "limitation", "gotcha"]):
                bullets = self._extract_bullets(body)
                items.extend(bullets or [self._trim_block(body, max_lines=12)])
        return list(dict.fromkeys([i for i in items if i]))[:25]

    def _extract_examples(self, content: str) -> List[str]:
        sections = self._extract_markdown_sections(content)
        examples: List[str] = []
        for heading, body in sections:
            if "example" in heading.lower():
                for block in self._extract_code_blocks(body):
                    t = block.strip()
                    if t:
                        examples.append(t[:800])
        if not examples:
            for block in self._extract_code_blocks(content)[:2]:
                t = block.strip()
                if t:
                    examples.append(t[:800])
        return list(dict.fromkeys(examples))[:5]

    def _derive_capability_tags(
        self, content: str, *, toolkits: List[str], detected_tools: Dict[str, List[str]]
    ) -> List[str]:
        tags: List[str] = []
        toolkit_to_tag = {
            "gmail": "email",
            "google-calendar": "calendar",
            "googlecalendar": "calendar",
            "slack": "slack",
            "github": "github",
            "neon": "database",
        }
        for tk in toolkits:
            tag = toolkit_to_tag.get(str(tk).lower())
            if tag:
                tags.append(tag)
        for slug in detected_tools.get("composio_tools") or []:
            prefix = slug.split("_", 1)[0].lower()
            if prefix == "gmail":
                tags.append("email")
            if prefix == "slack":
                tags.append("slack")
            if prefix == "github":
                tags.append("github")
        if re.search(r"\b(sql|postgres|sqlite|database)\b", content, re.I):
            tags.append("database")
        return list(dict.fromkeys(tags))

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
        lower = content.lower()
        if re.search(r"\b(delete|drop|truncate|reset|destroy)\b", lower):
            return list(dict.fromkeys(side_effects)), "high"
        if side_effects:
            return list(dict.fromkeys(side_effects)), "medium"
        return [], "low"
