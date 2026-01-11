"""Skill scanner - extracts metadata from `SKILL.md` files."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ..models import SkillMetadata


class PerformanceMetricsExtractor:
    """Extract performance metrics from `SKILL.md` files."""

    def extract_metrics(self, skill_md_content: str) -> Optional[Dict]:
        """Extract performance metrics from `SKILL.md` content.

        Priority: Markdown tables > regex patterns.

        Args:
            skill_md_content: Raw `SKILL.md` contents.

        Returns:
            A dictionary of extracted metrics if found, otherwise `None`.
        """
        # Try table parsing first
        table_metrics = self._parse_tables(skill_md_content)
        if table_metrics:
            return table_metrics

        # Fallback to regex patterns
        return self._parse_text_patterns(skill_md_content)

    def _parse_tables(self, content: str) -> Optional[Dict]:
        """Parse markdown tables for performance data."""
        # Look for performance-related section headers
        perf_section = self._extract_section(
            content, ["## Performance", "### Performance", "## Benchmarks"]
        )
        if not perf_section:
            return None

        # Parse markdown table
        tables = self._extract_markdown_tables(perf_section)
        if not tables:
            return None

        metrics = {}
        for table in tables:
            # Expected headers: Operation, Time, Speedup, etc.
            for row in table["rows"]:
                operation = row.get("Operation") or row.get("operation")
                time = row.get("Gateway CLI") or row.get("Time") or row.get("time")
                speedup = row.get("Speedup") or row.get("speedup")

                if operation:
                    metrics[operation] = {"time": time, "speedup": speedup}

        return metrics if metrics else None

    def _parse_text_patterns(self, content: str) -> Optional[Dict]:
        """Fallback: extract metrics using regex patterns."""
        metrics = {}

        # Pattern 1: "5.6x faster"
        speedup_pattern = r"(\d+\.?\d*)[xX]\s*(faster|speedup)"
        for match in re.finditer(speedup_pattern, content):
            speedup = match.group(1)
            metrics["speedup"] = f"{speedup}x"

        # Pattern 2: "~300ms" or "300 ms"
        time_pattern = r"~?(\d+)\s*(ms|milliseconds)"
        for match in re.finditer(time_pattern, content):
            time_ms = match.group(1)
            metrics["execution_time"] = f"{time_ms}ms"

        # Pattern 3: "saves 800 tokens"
        token_pattern = r"saves?\s+(\d+)\s+tokens?"
        for match in re.finditer(token_pattern, content):
            tokens = match.group(1)
            metrics["token_savings"] = f"{tokens} tokens"

        return metrics if metrics else None

    def _extract_section(self, content: str, headers: List[str]) -> Optional[str]:
        """Extract content under the first matching section header."""
        for header in headers:
            pattern = rf"{re.escape(header)}.*?\n(.*?)(?=\n#{1,3}\s|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return None

    def _extract_markdown_tables(self, section: str) -> List[Dict]:
        """Parse markdown tables into structured data."""
        tables = []
        # Split by table boundaries (header row with pipes)
        table_pattern = r"\|.*?\|\n\|[-:\s|]+\|\n((?:\|.*?\|\n)+)"
        for match in re.finditer(table_pattern, section):
            table_text = match.group(0)
            tables.append(self._parse_single_table(table_text))
        return tables

    def _parse_single_table(self, table_text: str) -> Dict:
        """Parse a single markdown table."""
        lines = [line.strip() for line in table_text.split("\n") if line.strip()]

        # Extract headers
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split("|") if h.strip()]

        # Extract rows (skip separator line at index 1)
        rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) == len(headers):
                row_dict = dict(zip(headers, cells))
                rows.append(row_dict)

        return {"headers": headers, "rows": rows}


class SkillScanner:
    """Scan a skills directory for skill metadata."""

    def __init__(
        self, skills_dir: Path, platform: str = "claude", origin: str = "in-house"
    ):
        self.skills_dir = skills_dir
        self.platform = platform
        self.origin = origin
        self.perf_extractor = PerformanceMetricsExtractor()

    def scan(self) -> List[SkillMetadata]:
        """Scan all skills in the skills directory."""
        skills = []

        if not self.skills_dir.exists():
            return skills

        # Scan both active skills and disabled skills
        for location in [self.skills_dir, self.skills_dir / ".disabled"]:
            if not location.exists():
                continue

            is_disabled = location.name == ".disabled"

            for skill_path in location.iterdir():
                if not skill_path.is_dir():
                    continue

                # Skip hidden directories and common non-skill dirs
                if skill_path.name.startswith(".") and not is_disabled:
                    continue

                try:
                    skill = self._scan_skill(skill_path, is_disabled)
                    if skill:
                        skills.append(skill)
                except Exception as e:
                    # Track error but continue scanning
                    error_skill = SkillMetadata(
                        name=skill_path.name,
                        origin="unknown",
                        status="error",
                        last_modified=datetime.now(),
                        install_path=skill_path,
                        platform=self.platform,
                        error_message=str(e),
                    )
                    skills.append(error_skill)

        # Post-process: link skill reference graph (best-effort).
        self._link_skill_reference_graph(skills)
        return skills

    def _link_skill_reference_graph(self, skills: List[SkillMetadata]) -> None:
        """Populate depends_on_skills and used_by_skills for scanned skills."""
        by_lower = {s.name.lower(): s for s in skills if getattr(s, "name", None)}

        for skill in skills:
            refs = getattr(skill, "depends_on_skills", None) or []
            resolved: List[str] = []
            seen = set()
            for token in refs:
                if not token:
                    continue
                name = by_lower.get(str(token).lower())
                val = name.name if name else str(token)
                if val not in seen:
                    seen.add(val)
                    resolved.append(val)
            skill.depends_on_skills = resolved

        # Reverse edges for "used by".
        used_by: Dict[str, List[str]] = {}
        for skill in skills:
            for dep in getattr(skill, "depends_on_skills", None) or []:
                used_by.setdefault(dep, []).append(skill.name)

        for skill in skills:
            incoming = used_by.get(skill.name) or []
            # Dedup preserve order
            seen = set()
            deduped: List[str] = []
            for src in incoming:
                if src not in seen:
                    seen.add(src)
                    deduped.append(src)
            skill.used_by_skills = deduped

    def _scan_skill(
        self, skill_path: Path, is_disabled: bool = False
    ) -> Optional[SkillMetadata]:
        """Scan a single skill directory."""
        skill_md = skill_path / "SKILL.md"

        # Must have SKILL.md to be a valid skill
        if not skill_md.exists():
            return None

        # Parse SKILL.md
        content = skill_md.read_text()
        frontmatter = self._extract_frontmatter(content)

        # Extract metadata
        name = frontmatter.get("name", skill_path.name)
        description = frontmatter.get("description", "")
        version = frontmatter.get("version")
        frontmatter_extra = self._extract_frontmatter_extra(frontmatter)
        invocation = self._extract_invocation_hints(content)
        references, context_fork_hint = self._extract_references_and_context_hints(
            content
        )
        usage = self._extract_usage_sections(content)
        tools, toolkits = self._extract_tool_usage(content)
        io_safety = self._extract_inputs_outputs_safety(content)
        capability_tags = self._derive_capability_tags(
            content, toolkits=toolkits, detected_tools=tools
        )
        prerequisites = self._extract_prerequisites(content)
        gotchas = self._extract_gotchas(content)
        required_env_vars = self._extract_required_env_vars(content)
        examples = self._extract_examples(content)
        trigger_types = self._normalize_trigger_types(
            content, trigger_rules=usage.get("trigger_rules") or []
        )
        context_behavior = self._normalize_context_behavior(content)
        side_effects, risk_level = self._classify_side_effects_and_risk(
            content, detected_tools=tools, toolkits=toolkits
        )

        # Count files and lines
        file_count, total_lines = self._count_files_and_lines(skill_path)

        # Extract performance metrics
        perf_metrics = self.perf_extractor.extract_metrics(content)

        # Extract dependency info (best-effort)
        dependencies, dependency_sources = self._extract_dependencies(skill_path)

        # Get last modified time
        last_modified = datetime.fromtimestamp(skill_md.stat().st_mtime)

        # Detect origin (will be refined by OriginDetector later)
        origin = self.origin

        status = "disabled" if is_disabled else "active"

        return SkillMetadata(
            name=name,
            origin=origin,
            status=status,
            last_modified=last_modified,
            install_path=skill_path,
            platform=self.platform,
            version=version,
            description=description,
            file_count=file_count,
            total_lines=total_lines,
            has_docs=skill_md.exists(),
            performance_notes=json.dumps(perf_metrics) if perf_metrics else None,
            dependencies=dependencies,
            dependency_sources=dependency_sources,
            frontmatter_extra=frontmatter_extra,
            invocation_aliases=invocation.get("aliases") or [],
            invocation_arguments=invocation.get("arguments") or "",
            invocation_instruction=invocation.get("instruction") or "",
            references=references,
            context_fork_hint=context_fork_hint,
            when_to_use=usage.get("when_to_use") or "",
            trigger_rules=usage.get("trigger_rules") or [],
            detected_tools=tools,
            detected_toolkits=toolkits,
            inputs=io_safety.get("inputs") or [],
            inputs_schema=io_safety.get("inputs_schema") or [],
            outputs=io_safety.get("outputs") or [],
            outputs_schema=io_safety.get("outputs_schema") or [],
            safety_notes=io_safety.get("safety_notes") or "",
            capability_tags=capability_tags,
            examples=examples,
            prerequisites=prerequisites,
            gotchas=gotchas,
            required_env_vars=required_env_vars,
            trigger_types=trigger_types,
            context_behavior=context_behavior,
            side_effects=side_effects,
            risk_level=risk_level,
            depends_on_skills=list((references or {}).get("skills") or []),
        )

    def _extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from `SKILL.md`."""
        # Match YAML frontmatter between --- markers
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _extract_frontmatter_extra(self, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """Extract frontmatter keys beyond the standard SkillMetadata fields."""
        if not isinstance(frontmatter, dict):
            return {}

        standard = {"name", "description", "version"}
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

    def _extract_invocation_hints(self, content: str) -> Dict[str, Any]:
        """Extract invocation-related hints from the SKILL.md body.

        This is heuristic and best-effort (skills vary widely).
        """
        result: Dict[str, Any] = {"aliases": [], "arguments": "", "instruction": ""}

        # Focus on the top section of the file for "Alias"/"Arguments" style metadata.
        head = "\n".join(content.splitlines()[:80])

        alias_lines: List[str] = []
        for line in head.splitlines():
            normalized = line.replace("**", "")
            if re.search(r"(?i)^\s*aliases?\s*:\s*", normalized):
                alias_lines.append(line)
            if re.search(r"(?i)^\s*#\s*claude slash command\s*:\s*/", normalized):
                alias_lines.append(line)

            m = re.search(r"(?i)^\s*arguments?\s*:\s*(.+)$", normalized)
            if m and not result["arguments"]:
                result["arguments"] = m.group(1).strip()

        aliases: List[str] = []
        for line in alias_lines:
            aliases.extend(re.findall(r"/[A-Za-z0-9_-]+", line))
        # If no explicit alias lines, fall back to a single slash command in a top header.
        if not aliases:
            first_slash = re.findall(r"/[A-Za-z0-9_-]+", head)
            if first_slash:
                aliases.append(first_slash[0])

        # Deduplicate while preserving order.
        seen = set()
        deduped: List[str] = []
        for a in aliases:
            if a not in seen:
                seen.add(a)
                deduped.append(a)
        result["aliases"] = deduped

        # Heuristic instruction line:
        # Prefer an explicit file/ref arg like "@$1", otherwise fall back to "$1"
        # but avoid capturing the Arguments metadata line itself.
        for line in content.splitlines():
            if re.search(r"@\$\d+\b", line):
                candidate = line.strip().strip("-").strip()
                if candidate:
                    result["instruction"] = candidate
                    break

        if not result["instruction"]:
            for line in content.splitlines():
                normalized = line.replace("**", "").strip().lower()
                if normalized.startswith("arguments:"):
                    continue
                if re.search(r"\$\d+\b", line):
                    candidate = line.strip().strip("-").strip()
                    if candidate:
                        result["instruction"] = candidate
                        break

        return result

    def _extract_references_and_context_hints(
        self, content: str
    ) -> Tuple[Dict[str, List[str]], str]:
        """Extract lightweight references and context-fork hints from SKILL.md."""
        file_refs: List[str] = []
        skill_refs: List[str] = []
        context_hint = ""

        # File-like @refs (avoid npm scopes like @modelcontextprotocol/*).
        for m in re.finditer(r"@([A-Za-z0-9_./$-]+)", content):
            token = m.group(1)
            if token.startswith("modelcontextprotocol/"):
                continue
            if token.startswith("$"):
                file_refs.append(f"@{token}")
                continue
            if re.search(r"\.(md|txt|json|toml|ya?ml|py|sh)\b", token) or "/" in token:
                file_refs.append(f"@{token}")

        # $refs (exclude $1/$2 positional arg markers).
        for m in re.finditer(r"\$([A-Za-z][A-Za-z0-9_-]+)", content):
            token = m.group(1)
            skill_refs.append(token)

        # Context forking hint: store the first matching line as a hint (not truth).
        for line in content.splitlines():
            if re.search(r"(?i)\bfork(ing)?\b", line) and re.search(
                r"(?i)\bcontext\b", line
            ):
                context_hint = line.strip()
                break

        def _dedupe(items: List[str]) -> List[str]:
            seen_local = set()
            out: List[str] = []
            for it in items:
                if it not in seen_local:
                    seen_local.add(it)
                    out.append(it)
            return out

        refs: Dict[str, List[str]] = {}
        file_refs = _dedupe(file_refs)
        skill_refs = _dedupe(skill_refs)
        if file_refs:
            refs["files"] = file_refs
        if skill_refs:
            refs["skills"] = skill_refs

        return refs, context_hint

    def _extract_usage_sections(self, content: str) -> Dict[str, Any]:
        """Extract common 'when to use' / 'trigger' sections from a skill doc.

        This uses heading-based parsing when possible and falls back to keyword lines.
        """
        result: Dict[str, Any] = {"when_to_use": "", "trigger_rules": []}

        sections = self._extract_markdown_sections(content)
        target_headings = {
            "when to use": "when_to_use",
            "use when": "when_to_use",
            "when it runs": "when_to_use",
            "when to run": "when_to_use",
            "triggers": "trigger_rules",
            "trigger": "trigger_rules",
            "trigger rules": "trigger_rules",
            "run when": "trigger_rules",
        }

        def normalize_heading(h: str) -> str:
            return re.sub(r"[^a-z0-9 ]+", "", h.strip().lower())

        # Prefer explicit headings.
        for heading, body in sections:
            key = target_headings.get(normalize_heading(heading))
            if not key:
                continue
            if key == "when_to_use" and not result["when_to_use"]:
                result["when_to_use"] = self._trim_block(body, max_lines=12)
            if key == "trigger_rules" and not result["trigger_rules"]:
                rules = self._extract_bullets(body)
                result["trigger_rules"] = rules or [self._trim_block(body, max_lines=12)]

        # Fallback: keyword lines near the top.
        if not result["when_to_use"]:
            head = "\n".join(content.splitlines()[:120])
            for line in head.splitlines():
                if re.search(r"(?i)^\s*(use when|when to use)\s*[:\-]", line):
                    result["when_to_use"] = line.split(":", 1)[-1].strip() or line.strip()
                    break

        return result

    def _extract_inputs_outputs_safety(self, content: str) -> Dict[str, Any]:
        """Extract 'Inputs', 'Outputs', and 'Safety' sections from a skill doc."""
        result: Dict[str, Any] = {
            "inputs": [],
            "outputs": [],
            "inputs_schema": [],
            "outputs_schema": [],
            "safety_notes": "",
        }
        sections = self._extract_markdown_sections(content)

        def normalize_heading(h: str) -> str:
            return re.sub(r"[^a-z0-9 ]+", "", h.strip().lower())

        inputs_headings = {
            "inputs",
            "input",
            "parameters",
            "input schema",
            "inputs required",
        }
        outputs_headings = {"outputs", "output", "returns", "result"}
        safety_headings = {
            "safety",
            "security",
            "privacy",
            "redaction",
            "notes",
            "notes limitations",
        }

        for heading, body in sections:
            key = normalize_heading(heading)
            if not result["inputs"] and key in inputs_headings:
                inputs = self._extract_io_items(body)
                result["inputs"] = inputs
                result["inputs_schema"] = self._enrich_io_schema(inputs)
                continue
            if not result["outputs"] and key in outputs_headings:
                outputs = self._extract_io_items(body)
                result["outputs"] = outputs
                result["outputs_schema"] = self._enrich_io_schema(outputs)
                continue
            if not result["safety_notes"] and key in safety_headings:
                result["safety_notes"] = self._trim_block(body, max_lines=20)
                continue

        return result

    def _extract_io_items(self, body: str) -> List[str]:
        """Parse IO items as `name: description` bullets or plain bullets."""
        items: List[str] = []
        for line in body.splitlines():
            raw = line.strip()
            if not raw:
                continue
            m = re.match(r"^[-*]\s+(.+)$", raw)
            if not m:
                continue
            text = m.group(1).strip()
            # Normalize `name - desc` to `name: desc` where possible.
            if " - " in text and ":" not in text:
                left, right = text.split(" - ", 1)
                if left and right:
                    text = f"{left.strip()}: {right.strip()}"
            items.append(text)

        # Fallback: try table-ish lines like `name | desc`
        if not items:
            for line in body.splitlines():
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and parts[0].lower() != "input" and parts[0] != "---":
                    items.append(f"{parts[0]}: {parts[1]}")

        return items[:25]

    def _enrich_io_schema(self, items: List[str]) -> List[Dict[str, Any]]:
        """Convert IO strings into structured dicts where possible."""
        schema: List[Dict[str, Any]] = []
        for item in items:
            raw = item.strip()
            if not raw:
                continue

            name = raw
            desc = ""
            if ":" in raw:
                name, desc = raw.split(":", 1)
                name = name.strip()
                desc = desc.strip()

            required = False
            default_value = ""
            m_req = re.search(r"(?i)\b(required)\b", raw)
            if m_req:
                required = True

            m_def = re.search(r"(?i)\bdefault\s*[:=]\s*([^\s,;]+)", raw)
            if m_def:
                default_value = m_def.group(1).strip()

            schema.append(
                {
                    "name": name,
                    "description": desc,
                    "required": required,
                    "default": default_value,
                }
            )

        return schema[:25]

    def _derive_capability_tags(
        self,
        content: str,
        *,
        toolkits: List[str],
        detected_tools: Dict[str, List[str]],
    ) -> List[str]:
        """Derive high-level capability tags from detected tools/toolkits and text hints."""
        tags: List[str] = []

        toolkit_to_tag = {
            "gmail": "email",
            "google-calendar": "calendar",
            "googlecalendar": "calendar",
            "slack": "slack",
            "github": "github",
            "neon": "database",
            "playwright": "browser",
            "twitterapi-io": "twitter",
            "twitter": "twitter",
            "reminders-life-planner": "reminders",
        }
        for tk in toolkits:
            tag = toolkit_to_tag.get(str(tk).lower())
            if tag:
                tags.append(tag)

        for slug in (detected_tools.get("composio_tools") or []):
            prefix = slug.split("_", 1)[0].lower()
            if prefix == "gmail":
                tags.append("email")
            elif prefix in {"googlecalendar", "google-calendar"}:
                tags.append("calendar")
            elif prefix == "slack":
                tags.append("slack")
            elif prefix == "github":
                tags.append("github")

        for mcp in (detected_tools.get("mcp_tools") or []):
            if mcp.startswith("mcp__neon__"):
                tags.append("database")
            if mcp.startswith("mcp__gmail__"):
                tags.append("email")
            if mcp.startswith("mcp__google-calendar__"):
                tags.append("calendar")

        # Local tool hints in prose/code (best-effort).
        if re.search(r"\b(read_file|write_file|apply_patch|exec_command|list_dir)\b", content):
            tags.append("filesystem")
        if re.search(r"\b(sql|postgres|sqlite|database)\b", content, re.I):
            tags.append("database")

        # Deduplicate while preserving order.
        seen = set()
        out: List[str] = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def _extract_prerequisites(self, content: str) -> List[str]:
        """Extract install/setup prerequisites from headings and common commands."""
        sections = self._extract_markdown_sections(content)

        def normalize_heading(h: str) -> str:
            return re.sub(r"[^a-z0-9 ]+", "", h.strip().lower())

        prereq_headings = {
            "prerequisites",
            "setup",
            "installation",
            "install",
            "dependencies",
            "requirements",
        }

        lines: List[str] = []
        for heading, body in sections:
            if normalize_heading(heading) in prereq_headings:
                lines.extend(self._extract_bullets(body))
                lines.extend(self._extract_install_commands(body))

        # Also scan code blocks in whole content for install commands.
        for block in self._extract_code_blocks(content):
            lines.extend(self._extract_install_commands(block))

        # Deduplicate / clean.
        out: List[str] = []
        seen = set()
        for line in [raw.strip() for raw in lines if raw and raw.strip()]:
            if line not in seen:
                seen.add(line)
                out.append(line)
        return out[:25]

    def _extract_install_commands(self, text: str) -> List[str]:
        cmds: List[str] = []
        patterns = [
            r"^\s*(pip3?\s+install\s+.+)$",
            r"^\s*(uv\s+pip\s+install\s+.+)$",
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
        """Extract gotchas/failure modes from common headings."""
        sections = self._extract_markdown_sections(content)

        def normalize_heading(h: str) -> str:
            return re.sub(r"[^a-z0-9 ]+", "", h.strip().lower())

        gotcha_headings = {
            "pitfalls",
            "known issues",
            "limitations",
            "notes limitations",
            "notes",
        }

        items: List[str] = []
        for heading, body in sections:
            if normalize_heading(heading) in gotcha_headings:
                bullets = self._extract_bullets(body)
                items.extend(bullets or [self._trim_block(body, max_lines=12)])

        # Fallback: keyword bullets near the end.
        tail = "\n".join(content.splitlines()[-120:])
        for line in tail.splitlines():
            if re.search(r"(?i)^\s*[-*]\s+.*(gotcha|caveat|warning|beware)\b", line):
                m = re.match(r"^\s*[-*]\s+(.+)$", line)
                if m:
                    items.append(m.group(1).strip())

        # Dedup
        out: List[str] = []
        seen = set()
        for it in [i.strip() for i in items if i and i.strip()]:
            if it not in seen:
                seen.add(it)
                out.append(it)
        return out[:25]

    def _extract_required_env_vars(self, content: str) -> List[str]:
        """Extract referenced env var names (names only, never values)."""
        names: List[str] = []

        for m in re.finditer(r"\$\{([A-Z0-9_]+)\}", content):
            names.append(m.group(1))

        for line in content.splitlines():
            m = re.match(r"^\s*export\s+([A-Z0-9_]+)\s*=", line)
            if m:
                names.append(m.group(1))

        # Deduplicate while preserving order.
        seen = set()
        out: List[str] = []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out[:50]

    def _extract_examples(self, content: str) -> List[str]:
        """Extract example code blocks from 'Example(s)' sections."""
        sections = self._extract_markdown_sections(content)
        examples: List[str] = []

        def is_example_heading(h: str) -> bool:
            return "example" in h.strip().lower()

        for heading, body in sections:
            if not is_example_heading(heading):
                continue
            for block in self._extract_code_blocks(body):
                trimmed = block.strip()
                if trimmed:
                    examples.append(trimmed[:800])

        # Fallback: include first couple code blocks if none labeled.
        if not examples:
            for block in self._extract_code_blocks(content)[:2]:
                trimmed = block.strip()
                if trimmed:
                    examples.append(trimmed[:800])

        # Dedup
        out: List[str] = []
        seen = set()
        for ex in examples:
            if ex not in seen:
                seen.add(ex)
                out.append(ex)
        return out[:5]

    def _normalize_trigger_types(self, content: str, *, trigger_rules: List[str]) -> List[str]:
        """Normalize trigger types (manual/hook/scheduled/interactive)."""
        text = "\n".join(trigger_rules) + "\n" + content
        types: List[str] = []

        if re.search(r"(?i)\b(post_tool_use|pre_tool_use|session_start|session_end)\b", text):
            types.append("hook")
        if re.search(r"(?i)\b(cron|schedule|daily|weekly|every\s+\d+|at\s+\d{1,2}(:\d{2})?)\b", text):
            types.append("scheduled")
        if re.search(r"(?i)\b(confirm|ask|prompt)\b", text):
            types.append("interactive")

        # Default to manual if it has an alias or explicitly says manual.
        if re.search(r"(?i)\bmanual\b", text) or re.search(r"/[A-Za-z0-9_-]+", text):
            types.append("manual")

        if not types:
            types.append("manual")

        # Dedup
        seen = set()
        out: List[str] = []
        for t in types:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def _normalize_context_behavior(self, content: str) -> str:
        """Infer context behavior (fork/no_fork/unknown) from prose."""
        text = content.lower()
        if "context" in text and re.search(r"\b(no|dont|do not|without)\s+fork", text):
            return "no_fork"
        if re.search(r"\bfork(ed|ing)?\b", text) and "context" in text:
            return "fork"
        return "unknown"

    def _classify_side_effects_and_risk(
        self,
        content: str,
        *,
        detected_tools: Dict[str, List[str]],
        toolkits: List[str],
    ) -> Tuple[List[str], str]:
        """Classify side effects and rough risk level (heuristic)."""
        side_effects: List[str] = []
        lower = content.lower()

        # Side effects from toolkits/capabilities.
        if "gmail" in toolkits:
            side_effects.append("email")
        if "google-calendar" in toolkits or "googlecalendar" in toolkits:
            side_effects.append("calendar")
        if "slack" in toolkits:
            side_effects.append("slack")
        if "github" in toolkits:
            side_effects.append("github")
        if "neon" in toolkits:
            side_effects.append("database")

        # File/system operations mentioned.
        if re.search(r"\b(apply_patch|write_file|rm\s|mv\s|chmod\s|git\s+commit)\b", lower):
            side_effects.append("filesystem")

        # Network-ish tools.
        if any(tk in toolkits for tk in ["twitter", "twitterapi-io", "playwright"]):
            side_effects.append("network")

        # Determine risk from tool slugs and keywords.
        destructive = False
        for slug in (detected_tools.get("composio_tools") or []):
            if re.search(r"(DELETE|DROP|REMOVE|RESET|MIGRATE|DESTROY|TRUNCATE)", slug):
                destructive = True
        for mcp in (detected_tools.get("mcp_tools") or []):
            if re.search(r"(delete|drop|reset|migrate|complete_)", mcp, re.I):
                destructive = True
        if re.search(r"\b(drop|delete|truncate|reset|destroy)\b", lower):
            destructive = True

        # Dedup side_effects
        seen = set()
        se: List[str] = []
        for s in side_effects:
            if s not in seen:
                seen.add(s)
                se.append(s)

        if destructive:
            risk = "high"
        elif se:
            risk = "medium"
        else:
            risk = "low"

        return se, risk

    def _extract_tool_usage(self, content: str) -> Tuple[Dict[str, List[str]], List[str]]:
        """Detect common tool usage patterns from code blocks and inline text."""
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

            # run_composio_tool("GMAIL_SEND_EMAIL", {...})
            for m in re.finditer(
                r"run_composio_tool\(\s*['\"]([A-Z0-9_]+)['\"]", text
            ):
                slug = m.group(1)
                composio_tools.append(slug)
                toolkits.append(slug.split("_", 1)[0].lower())

            # run_composio_tool(tool_slug="GMAIL_SEND_EMAIL", ...)
            for m in re.finditer(
                r"run_composio_tool\(\s*[^)]*tool_slug\s*=\s*['\"]([A-Z0-9_]+)['\"]",
                text,
            ):
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

    def _extract_markdown_sections(self, content: str) -> List[Tuple[str, str]]:
        """Extract (heading, body) pairs for ##/### headings."""
        lines = content.splitlines()
        sections: List[Tuple[str, str]] = []
        current_heading: Optional[str] = None
        current_body: List[str] = []

        def flush() -> None:
            nonlocal current_heading, current_body
            if current_heading is not None:
                body = "\n".join(current_body).strip()
                sections.append((current_heading, body))
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
        """Extract fenced code blocks (```...```)."""
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
        bullets: List[str] = []
        for line in body.splitlines():
            m = re.match(r"^\s*[-*]\s+(.+)$", line)
            if m:
                bullets.append(m.group(1).strip())
        return bullets

    def _trim_block(self, body: str, *, max_lines: int) -> str:
        lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
        return "\n".join(lines[:max_lines]).strip()

    def _extract_dependencies(self, skill_path: Path) -> Tuple[List[str], List[str]]:
        """Extract dependencies from common dependency files in a skill directory."""
        dependencies: List[str] = []
        sources: List[str] = []

        def add_deps(new_deps: List[str], source: str) -> None:
            nonlocal dependencies, sources
            cleaned = [d.strip() for d in new_deps if d and d.strip()]
            if not cleaned:
                return
            dependencies.extend(cleaned)
            sources.append(source)

        requirements = skill_path / "requirements.txt"
        if requirements.exists():
            add_deps(self._parse_requirements_txt(requirements), "requirements.txt")

        pyproject = skill_path / "pyproject.toml"
        if pyproject.exists():
            deps = self._parse_pyproject_toml(pyproject)
            if deps:
                add_deps(deps, "pyproject.toml")

        package_json = skill_path / "package.json"
        if package_json.exists():
            deps = self._parse_package_json(package_json)
            if deps:
                add_deps(deps, "package.json")

        # Deduplicate while preserving order
        seen = set()
        deduped: List[str] = []
        for dep in dependencies:
            if dep in seen:
                continue
            seen.add(dep)
            deduped.append(dep)

        return deduped, sources

    def _parse_requirements_txt(self, path: Path) -> List[str]:
        deps: List[str] = []
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("-r ", "--requirement ")):
                continue
            deps.append(line)
        return deps

    def _parse_pyproject_toml(self, path: Path) -> List[str]:
        try:
            import tomllib  # py311+
        except ModuleNotFoundError:  # pragma: no cover
            import tomli as tomllib  # type: ignore

        try:
            data = tomllib.loads(path.read_text())
        except Exception:
            return []

        project = data.get("project")
        if not isinstance(project, dict):
            return []

        deps = project.get("dependencies") or []
        if not isinstance(deps, list):
            return []
        return [str(d).strip() for d in deps if str(d).strip()]

    def _parse_package_json(self, path: Path) -> List[str]:
        import json as _json

        try:
            data = _json.loads(path.read_text())
        except Exception:
            return []

        deps = data.get("dependencies") or {}
        if not isinstance(deps, dict):
            return []

        formatted: List[str] = []
        for name, version in deps.items():
            if name and version is not None:
                formatted.append(f"{name}@{version}")
        return formatted

    def _count_files_and_lines(self, skill_path: Path) -> tuple[int, int]:
        """Count files and total lines in a skill directory."""
        file_count = 0
        total_lines = 0

        exclude_patterns = [
            "__pycache__",
            ".pyc",
            "node_modules",
            ".git",
            "target/debug",
            "target/release",
        ]

        for file_path in skill_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip excluded patterns
            if any(pattern in str(file_path) for pattern in exclude_patterns):
                continue

            file_count += 1

            # Count lines for text files
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    total_lines += sum(1 for _ in f)
            except (UnicodeDecodeError, PermissionError):
                # Skip binary or unreadable files
                pass

        return file_count, total_lines
