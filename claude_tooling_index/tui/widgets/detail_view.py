"""Detail view widget - shows component details."""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Static


class DetailView(VerticalScroll):
    """Panel showing detailed component information."""

    DEFAULT_CSS = """
    DetailView {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_component: Optional[Any] = None

    def compose(self):
        yield Static(id="detail-content")

    def show_component(self, component: Any) -> None:
        """Display details for the given component."""
        self.current_component = component
        content = self._build_content(component)
        self.query_one("#detail-content", Static).update(content)

    def clear(self, message: Optional[str] = None) -> None:
        """Clear the detail view."""
        self.current_component = None
        welcome = Text()
        welcome.append("◉ ", style="#DA7756")
        welcome.append(
            message or "Select a component to view details", style="dim italic"
        )
        self.query_one("#detail-content", Static).update(welcome)

    def _build_content(self, component: Any) -> Panel:
        """Build rich content for the component."""
        content = []

        # Name and type header
        comp_type = getattr(component, "type", "unknown")
        status = getattr(component, "status", "unknown")
        status_emojis = {
            "active": "🟢",
            "disabled": "⚪",
            "error": "🔴",
            "unknown": "🟡",
        }
        status_emoji = status_emojis.get(status, "❓")

        # Claude orange color
        claude_orange = "#DA7756"

        header = Text()
        header.append(f"{component.name}", style=f"bold {claude_orange}")
        header.append(f" [{comp_type}] ", style="dim")
        header.append(f"{status_emoji} {status}")
        content.append(header)
        content.append("")

        # Description
        description = getattr(component, "description", None)
        if description:
            content.append(Text(description, style="italic"))
            content.append("")

        # Basic info table
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("Key", style="bold")
        info_table.add_column("Value")

        # Add basic fields
        version = getattr(component, "version", None)
        if version:
            info_table.add_row("Version:", version)

        platform = getattr(component, "platform", None)
        if platform:
            info_table.add_row("Platform:", platform)

        origin = getattr(component, "origin", None)
        if origin:
            info_table.add_row("Origin:", origin)

        install_path = getattr(component, "install_path", None)
        if install_path:
            info_table.add_row("Path:", str(install_path))

        last_modified = getattr(component, "last_modified", None)
        if last_modified:
            info_table.add_row("Modified:", last_modified.strftime("%Y-%m-%d %H:%M"))

        # Type-specific fields
        if comp_type == "skill":
            file_count = getattr(component, "file_count", 0)
            total_lines = getattr(component, "total_lines", 0)
            info_table.add_row("Files:", str(file_count))
            info_table.add_row("Lines:", str(total_lines))

            has_docs = getattr(component, "has_docs", False)
            info_table.add_row("Documentation:", "Yes" if has_docs else "No")

            dependency_sources = getattr(component, "dependency_sources", None)
            if dependency_sources:
                info_table.add_row("Dep Sources:", ", ".join(dependency_sources))

            risk_level = getattr(component, "risk_level", None)
            if risk_level:
                info_table.add_row("Risk:", risk_level)

        elif comp_type == "plugin":
            marketplace = getattr(component, "marketplace", None)
            if marketplace:
                info_table.add_row("Marketplace:", marketplace)

            author = getattr(component, "author", None)
            if author:
                info_table.add_row("Author:", author)

            homepage = getattr(component, "homepage", None)
            if homepage:
                info_table.add_row("Homepage:", homepage)

            repository = getattr(component, "repository", None)
            if repository:
                info_table.add_row("Repository:", repository)

            license_value = getattr(component, "license", None)
            if license_value:
                info_table.add_row("License:", license_value)

            installed_at = getattr(component, "installed_at", None)
            if installed_at:
                info_table.add_row("Installed:", installed_at.strftime("%Y-%m-%d"))

            provides_commands = getattr(component, "provides_commands", None) or []
            provides_mcps = getattr(component, "provides_mcps", None) or []
            if provides_commands:
                info_table.add_row("Commands:", str(len(provides_commands)))
            if provides_mcps:
                info_table.add_row("MCPs:", str(len(provides_mcps)))

        elif comp_type == "command":
            from_plugin = getattr(component, "from_plugin", None)
            if from_plugin:
                info_table.add_row("From Plugin:", str(from_plugin))

            risk_level = getattr(component, "risk_level", None)
            if risk_level:
                info_table.add_row("Risk:", risk_level)

        elif comp_type == "hook":
            trigger = getattr(component, "trigger", None)
            if trigger:
                info_table.add_row("Trigger:", trigger)

            trigger_event = getattr(component, "trigger_event", None)
            if trigger_event:
                info_table.add_row("Trigger Event:", trigger_event)

            language = getattr(component, "language", None)
            if language:
                info_table.add_row("Language:", language)

            file_size = getattr(component, "file_size", 0)
            info_table.add_row("Size:", self._format_size(file_size))

            shebang = getattr(component, "shebang", None)
            if shebang:
                info_table.add_row("Shebang:", shebang)

            is_executable = getattr(component, "is_executable", False)
            info_table.add_row("Executable:", "Yes" if is_executable else "No")

            risk_level = getattr(component, "risk_level", None)
            if risk_level:
                info_table.add_row("Risk:", risk_level)

        elif comp_type == "mcp":
            source = getattr(component, "source", None)
            if source:
                info_table.add_row("Source:", source)

            source_detail = getattr(component, "source_detail", None)
            if source_detail:
                info_table.add_row("Source Detail:", source_detail)

            git_remote = getattr(component, "git_remote", None)
            if git_remote:
                info_table.add_row("Git Remote:", git_remote)

            command = getattr(component, "command", None)
            if command:
                info_table.add_row("Command:", command)

                # Best-effort health check: is the command resolvable on PATH?
                resolved = None
                try:
                    if isinstance(command, str) and command and not command.startswith("http"):
                        if command.startswith(("/", "~", "./", "../")):
                            resolved = str(Path(command).expanduser())
                        else:
                            resolved = shutil.which(command)
                except Exception:
                    resolved = None

                if resolved:
                    try:
                        p = Path(resolved).expanduser()
                        info_table.add_row("Cmd Path:", str(p))
                        info_table.add_row("Cmd Exists:", "Yes" if p.exists() else "No")
                        info_table.add_row(
                            "Cmd Exec:",
                            "Yes" if (p.exists() and p.is_file() and os.access(p, os.X_OK)) else "No",
                        )
                    except Exception:
                        info_table.add_row("Cmd Path:", str(resolved))

            args = getattr(component, "args", None)
            if args:
                info_table.add_row("Args:", " ".join([str(a) for a in args]))

            transport = getattr(component, "transport", None)
            if transport:
                info_table.add_row("Transport:", transport)

        elif comp_type == "binary":
            language = getattr(component, "language", None)
            if language:
                info_table.add_row("Language:", language)

            file_size = getattr(component, "file_size", 0)
            info_table.add_row("Size:", self._format_size(file_size))

            is_executable = getattr(component, "is_executable", False)
            info_table.add_row("Executable:", "Yes" if is_executable else "No")

        content.append(info_table)

        # Usage stats (from local DB, if the TUI has an analytics tracker).
        usage = self._get_component_usage(component)
        if isinstance(usage, dict):
            claude_orange = "#DA7756"
            content.append("")
            content.append(Text("Usage (30d)", style=f"bold underline {claude_orange}"))
            if not usage.get("found"):
                content.append(Text("  • No DB record for this component yet.", style="dim"))
            elif int(usage.get("total_invocations") or 0) <= 0:
                content.append(Text("  • No invocations recorded.", style="dim"))
            else:
                total = int(usage.get("total_invocations") or 0)
                sessions = int(usage.get("sessions") or 0)
                success_rate = usage.get("success_rate")
                avg_ms = usage.get("avg_duration_ms")
                p95_ms = usage.get("p95_duration_ms")
                last_invoked = usage.get("last_invoked")

                usage_table = Table(show_header=False, box=None, padding=(0, 1))
                usage_table.add_column("Key", style="bold")
                usage_table.add_column("Value")
                usage_table.add_row("Invocations:", str(total))
                if sessions:
                    usage_table.add_row("Sessions:", str(sessions))
                if isinstance(success_rate, (float, int)):
                    usage_table.add_row("Success:", f"{success_rate * 100:.0f}%")
                if avg_ms is not None:
                    try:
                        usage_table.add_row("Avg:", f"{float(avg_ms):.0f}ms")
                    except Exception:
                        usage_table.add_row("Avg:", str(avg_ms))
                if p95_ms is not None:
                    usage_table.add_row("P95:", f"{p95_ms}ms")
                if last_invoked:
                    usage_table.add_row("Last:", str(last_invoked))
                content.append(usage_table)

                recent_errors = usage.get("recent_errors") or []
                if isinstance(recent_errors, list) and recent_errors:
                    content.append(Text("  • Recent errors:", style="dim"))
                    for err in recent_errors[:3]:
                        if isinstance(err, dict):
                            ts = err.get("timestamp") or ""
                            msg = err.get("error_message") or ""
                            content.append(Text(f"    - {ts}: {msg}", style="dim"))

        # Frontmatter extras (skills, commands)
        if comp_type in {"skill", "command"}:
            extra = getattr(component, "frontmatter_extra", None)
            if extra:
                content.append("")
                content.append(Text("Frontmatter", style=f"bold underline {claude_orange}"))

                extra_table = Table(show_header=False, box=None, padding=(0, 1))
                extra_table.add_column("Key", style="bold")
                extra_table.add_column("Value")

                def _fmt(v: Any) -> str:
                    if v is None:
                        return ""
                    if isinstance(v, (str, int, float, bool)):
                        return str(v)
                    try:
                        return json.dumps(v, ensure_ascii=False)
                    except Exception:
                        return str(v)

                for key in sorted(extra.keys()):
                    extra_table.add_row(str(key), _fmt(extra[key]))

                content.append(extra_table)

        # Performance notes
        perf_notes = getattr(component, "performance_notes", None)
        if perf_notes:
            content.append("")
            content.append(Text("Performance", style=f"bold underline {claude_orange}"))
            try:
                perf_data = json.loads(perf_notes)
                if isinstance(perf_data, dict):
                    perf_table = Table(show_header=True, box=None, padding=(0, 1))
                    perf_table.add_column("Operation")
                    perf_table.add_column("Time")
                    perf_table.add_column("Speedup")

                    for op, metrics in perf_data.items():
                        if isinstance(metrics, dict):
                            time_val = metrics.get("time", "-")
                            speedup = metrics.get("speedup", "-")
                            perf_table.add_row(op, str(time_val), str(speedup))
                        else:
                            perf_table.add_row(op, str(metrics), "-")

                    content.append(perf_table)
                else:
                    content.append(Text(str(perf_data)))
            except (json.JSONDecodeError, TypeError):
                content.append(Text(perf_notes))

        # Dependencies
        dependencies = getattr(component, "dependencies", None)
        if dependencies and len(dependencies) > 0:
            content.append("")
            content.append(
                Text("Dependencies", style=f"bold underline {claude_orange}")
            )
            for dep in dependencies:
                content.append(Text(f"  • {dep}"))

        # Skill invocation + references (heuristic)
        if comp_type == "skill":
            aliases = getattr(component, "invocation_aliases", None) or []
            args = getattr(component, "invocation_arguments", None) or ""
            instruction = getattr(component, "invocation_instruction", None) or ""
            refs = getattr(component, "references", None) or {}
            context_hint = getattr(component, "context_fork_hint", None) or ""
            when_to_use = getattr(component, "when_to_use", None) or ""
            trigger_rules = getattr(component, "trigger_rules", None) or []
            detected_tools = getattr(component, "detected_tools", None) or {}
            detected_toolkits = getattr(component, "detected_toolkits", None) or []
            inputs = getattr(component, "inputs", None) or []
            outputs = getattr(component, "outputs", None) or []
            safety_notes = getattr(component, "safety_notes", None) or ""
            capability_tags = getattr(component, "capability_tags", None) or []
            side_effects = getattr(component, "side_effects", None) or []
            required_env_vars = getattr(component, "required_env_vars", None) or []
            prerequisites = getattr(component, "prerequisites", None) or []
            gotchas = getattr(component, "gotchas", None) or []
            examples = getattr(component, "examples", None) or []
            trigger_types = getattr(component, "trigger_types", None) or []
            context_behavior = getattr(component, "context_behavior", None) or ""
            depends_on = getattr(component, "depends_on_skills", None) or []
            used_by = getattr(component, "used_by_skills", None) or []

            if aliases or args or instruction:
                content.append("")
                content.append(Text("Invocation", style=f"bold underline {claude_orange}"))
                if aliases:
                    content.append(Text(f"  • Aliases: {', '.join(aliases)}"))
                if args:
                    content.append(Text(f"  • Arguments: {args}"))
                if instruction:
                    content.append(Text(f"  • Instruction: {instruction}"))

            if isinstance(refs, dict) and (refs.get("files") or refs.get("skills")):
                content.append("")
                content.append(Text("References", style=f"bold underline {claude_orange}"))
                for fref in refs.get("files") or []:
                    ok = self._reference_file_exists(component, fref)
                    mark = "✓" if ok else "✗"
                    style = None if ok else "dim"
                    content.append(Text(f"  • {mark} {fref}", style=style))
                for sref in refs.get("skills") or []:
                    status = self._reference_skill_status(component, sref)
                    mark = "✓" if status else "✗"
                    suffix = f" ({status})" if status else ""
                    style = None if status else "dim"
                    content.append(Text(f"  • {mark} ${sref}{suffix}", style=style))

            if context_hint:
                content.append("")
                content.append(Text("Context Hint", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {context_hint}", style="dim"))

            if when_to_use:
                content.append("")
                content.append(Text("When To Use", style=f"bold underline {claude_orange}"))
                for line in when_to_use.splitlines():
                    content.append(Text(f"  • {line.strip()}"))

            if trigger_rules:
                content.append("")
                content.append(Text("Trigger Rules", style=f"bold underline {claude_orange}"))
                for rule in trigger_rules:
                    content.append(Text(f"  • {rule}"))

            if detected_toolkits:
                content.append("")
                content.append(Text("Toolkits", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(detected_toolkits)}"))

            if isinstance(detected_tools, dict) and detected_tools:
                content.append("")
                content.append(Text("Tools", style=f"bold underline {claude_orange}"))
                for key in ["mcp_tools", "composio_tools"]:
                    items = detected_tools.get(key) or []
                    if not items:
                        continue
                    label = "MCP" if key == "mcp_tools" else "Composio"
                    content.append(Text(f"  • {label}: {len(items)}", style="dim"))
                    for t in items[:15]:
                        content.append(Text(f"    - {t}"))

            if capability_tags:
                content.append("")
                content.append(Text("Capabilities", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(capability_tags)}"))

            if side_effects:
                content.append("")
                content.append(Text("Side Effects", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(side_effects)}"))

            if trigger_types:
                content.append("")
                content.append(Text("Trigger Types", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(trigger_types)}"))

            if context_behavior and context_behavior != "unknown":
                content.append("")
                content.append(Text("Context Behavior", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {context_behavior}", style="dim"))

            if depends_on:
                content.append("")
                content.append(Text("Depends On", style=f"bold underline {claude_orange}"))
                for name in depends_on[:25]:
                    content.append(Text(f"  • {name}"))

            if used_by:
                content.append("")
                content.append(Text("Used By", style=f"bold underline {claude_orange}"))
                for name in used_by[:25]:
                    content.append(Text(f"  • {name}"))

            if required_env_vars:
                content.append("")
                content.append(Text("Required Env", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(required_env_vars)}"))

            if prerequisites:
                content.append("")
                content.append(Text("Prerequisites", style=f"bold underline {claude_orange}"))
                for item in prerequisites[:15]:
                    content.append(Text(f"  • {item}"))

            if gotchas:
                content.append("")
                content.append(Text("Gotchas", style=f"bold underline {claude_orange}"))
                for item in gotchas[:15]:
                    content.append(Text(f"  • {item}", style="dim"))

            if examples:
                content.append("")
                content.append(Text("Examples", style=f"bold underline {claude_orange}"))
                for ex in examples[:2]:
                    content.append(Text(ex, style="dim"))
                    content.append(Text(""))

        # Command rich metadata
        if comp_type == "command":
            aliases = getattr(component, "invocation_aliases", None) or []
            args = getattr(component, "invocation_arguments", None) or ""
            instruction = getattr(component, "invocation_instruction", None) or ""
            refs = getattr(component, "references", None) or {}
            detected_tools = getattr(component, "detected_tools", None) or {}
            detected_toolkits = getattr(component, "detected_toolkits", None) or []
            capability_tags = getattr(component, "capability_tags", None) or []
            inputs = getattr(component, "inputs", None) or []
            outputs = getattr(component, "outputs", None) or []
            safety_notes = getattr(component, "safety_notes", None) or ""
            required_env_vars = getattr(component, "required_env_vars", None) or []
            prerequisites = getattr(component, "prerequisites", None) or []
            gotchas = getattr(component, "gotchas", None) or []
            examples = getattr(component, "examples", None) or []
            side_effects = getattr(component, "side_effects", None) or []

            if aliases or args or instruction:
                content.append("")
                content.append(Text("Invocation", style=f"bold underline {claude_orange}"))
                if aliases:
                    content.append(Text(f"  • Aliases: {', '.join(aliases)}"))
                if args:
                    content.append(Text(f"  • Arguments: {args}"))
                if instruction:
                    content.append(Text(f"  • Instruction: {instruction}"))

            if isinstance(refs, dict) and (refs.get("files") or refs.get("skills")):
                content.append("")
                content.append(Text("References", style=f"bold underline {claude_orange}"))
                for fref in refs.get("files") or []:
                    ok = self._reference_file_exists(component, fref)
                    mark = "✓" if ok else "✗"
                    style = None if ok else "dim"
                    content.append(Text(f"  • {mark} {fref}", style=style))
                for sref in refs.get("skills") or []:
                    status = self._reference_skill_status(component, sref)
                    mark = "✓" if status else "✗"
                    suffix = f" ({status})" if status else ""
                    style = None if status else "dim"
                    content.append(Text(f"  • {mark} ${sref}{suffix}", style=style))

            if capability_tags:
                content.append("")
                content.append(Text("Capabilities", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(capability_tags)}"))

            if side_effects:
                content.append("")
                content.append(Text("Side Effects", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(side_effects)}"))

            if detected_toolkits:
                content.append("")
                content.append(Text("Toolkits", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(detected_toolkits)}"))

            if isinstance(detected_tools, dict) and detected_tools:
                content.append("")
                content.append(Text("Tools", style=f"bold underline {claude_orange}"))
                for key in ["mcp_tools", "composio_tools"]:
                    items = detected_tools.get(key) or []
                    if not items:
                        continue
                    label = "MCP" if key == "mcp_tools" else "Composio"
                    content.append(Text(f"  • {label}: {len(items)}", style="dim"))
                    for t in items[:10]:
                        content.append(Text(f"    - {t}"))

            if required_env_vars:
                content.append("")
                content.append(Text("Required Env", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(required_env_vars)}"))

            if prerequisites:
                content.append("")
                content.append(Text("Prerequisites", style=f"bold underline {claude_orange}"))
                for item in prerequisites[:10]:
                    content.append(Text(f"  • {item}"))

            if gotchas:
                content.append("")
                content.append(Text("Gotchas", style=f"bold underline {claude_orange}"))
                for item in gotchas[:10]:
                    content.append(Text(f"  • {item}", style="dim"))

            if inputs:
                content.append("")
                content.append(Text("Inputs", style=f"bold underline {claude_orange}"))
                for item in inputs[:10]:
                    content.append(Text(f"  • {item}"))

            if outputs:
                content.append("")
                content.append(Text("Outputs", style=f"bold underline {claude_orange}"))
                for item in outputs[:10]:
                    content.append(Text(f"  • {item}"))

            if safety_notes:
                content.append("")
                content.append(Text("Safety", style=f"bold underline {claude_orange}"))
                for line in safety_notes.splitlines():
                    content.append(Text(f"  • {line.strip()}", style="dim"))

            if examples:
                content.append("")
                content.append(Text("Examples", style=f"bold underline {claude_orange}"))
                for ex in examples[:2]:
                    content.append(Text(ex, style="dim"))
                    content.append(Text(""))

            if inputs:
                content.append("")
                content.append(Text("Inputs", style=f"bold underline {claude_orange}"))
                for item in inputs[:15]:
                    content.append(Text(f"  • {item}"))

            if outputs:
                content.append("")
                content.append(Text("Outputs", style=f"bold underline {claude_orange}"))
                for item in outputs[:15]:
                    content.append(Text(f"  • {item}"))

            if safety_notes:
                content.append("")
                content.append(Text("Safety", style=f"bold underline {claude_orange}"))
                for line in safety_notes.splitlines():
                    content.append(Text(f"  • {line.strip()}", style="dim"))

        # Plugin provides
        if comp_type == "plugin":
            provides_commands = getattr(component, "provides_commands", None) or []
            provides_mcps = getattr(component, "provides_mcps", None) or []
            commands_detail = getattr(component, "commands_detail", None) or {}
            mcps_detail = getattr(component, "mcps_detail", None) or {}
            if provides_commands:
                content.append("")
                content.append(
                    Text("Provides Commands", style=f"bold underline {claude_orange}")
                )
                for cmd in provides_commands:
                    desc = ""
                    if isinstance(commands_detail, dict):
                        maybe = commands_detail.get(cmd)
                        if isinstance(maybe, str) and maybe.strip():
                            desc = maybe.strip()
                    suffix = f" — {desc}" if desc else ""
                    content.append(Text(f"  • {cmd}{suffix}"))

            if provides_mcps:
                content.append("")
                content.append(
                    Text("Provides MCPs", style=f"bold underline {claude_orange}")
                )
                for mcp_name in provides_mcps:
                    detail = None
                    if isinstance(mcps_detail, dict) and ":" in mcp_name:
                        short = mcp_name.split(":")[-1]
                        detail = mcps_detail.get(short)
                    if isinstance(detail, dict):
                        transport = detail.get("transport") or ""
                        env_keys = detail.get("env_keys") or []
                        extra = []
                        if transport:
                            extra.append(str(transport))
                        if isinstance(env_keys, list) and env_keys:
                            extra.append(f"env:{len(env_keys)}")
                        suffix = f" ({', '.join(extra)})" if extra else ""
                        content.append(Text(f"  • {mcp_name}{suffix}"))
                    else:
                        content.append(Text(f"  • {mcp_name}"))

        # MCP environment variables (already redacted in scanners)
        if comp_type == "mcp":
            config_extra = getattr(component, "config_extra", None)
            if isinstance(config_extra, dict) and config_extra:
                content.append("")
                content.append(Text("Config", style=f"bold underline {claude_orange}"))
                extra_table = Table(show_header=True, box=None, padding=(0, 1))
                extra_table.add_column("Key", style="bold")
                extra_table.add_column("Value")
                for key in sorted(config_extra.keys()):
                    val = config_extra.get(key)
                    if isinstance(val, (dict, list)):
                        try:
                            rendered = json.dumps(val, ensure_ascii=False)
                        except Exception:
                            rendered = str(val)
                    else:
                        rendered = str(val)
                    extra_table.add_row(str(key), rendered)
                content.append(extra_table)

            env_vars = getattr(component, "env_vars", None)
            if env_vars:
                content.append("")
                content.append(Text("Environment", style=f"bold underline {claude_orange}"))
                env_table = Table(show_header=True, box=None, padding=(0, 1))
                env_table.add_column("Key", style="bold")
                env_table.add_column("Value")
                for key in sorted(env_vars.keys()):
                    env_table.add_row(str(key), str(env_vars.get(key, "")))
                content.append(env_table)

        # Hook rich metadata
        if comp_type == "hook":
            detected_tools = getattr(component, "detected_tools", None) or {}
            detected_toolkits = getattr(component, "detected_toolkits", None) or []
            required_env_vars = getattr(component, "required_env_vars", None) or []
            side_effects = getattr(component, "side_effects", None) or []

            if side_effects:
                content.append("")
                content.append(Text("Side Effects", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(side_effects)}"))

            if detected_toolkits:
                content.append("")
                content.append(Text("Toolkits", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(detected_toolkits)}"))

            if isinstance(detected_tools, dict) and detected_tools:
                content.append("")
                content.append(Text("Tools", style=f"bold underline {claude_orange}"))
                for key in ["core_tools", "mcp_tools", "composio_tools"]:
                    items = detected_tools.get(key) or []
                    if not items:
                        continue
                    label = key.replace("_", " ").title()
                    content.append(Text(f"  • {label}: {len(items)}", style="dim"))
                    for t in items[:10]:
                        content.append(Text(f"    - {t}"))

            if required_env_vars:
                content.append("")
                content.append(Text("Required Env", style=f"bold underline {claude_orange}"))
                content.append(Text(f"  • {', '.join(required_env_vars)}"))

        # Error message
        error_msg = getattr(component, "error_message", None)
        if error_msg:
            content.append("")
            content.append(Text("Error", style="bold red"))
            content.append(Text(error_msg, style="red"))

        # Build panel
        from rich.console import Group

        return Panel(
            Group(*content),
            title=f"[bold {claude_orange}]{component.name}[/bold {claude_orange}]",
            border_style=claude_orange,
            subtitle=f"[dim]{comp_type}[/dim]",
        )

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    def _get_component_usage(self, component: Any) -> Optional[dict]:
        """Best-effort: query the local analytics DB for per-component usage."""
        try:
            app = self.app  # May raise when not mounted (e.g., unit tests).
        except Exception:
            return None

        tracker = getattr(app, "analytics_tracker", None)
        if not tracker:
            return None

        try:
            platform = getattr(component, "platform", "claude")
            name = getattr(component, "name", "")
            comp_type = getattr(component, "type", "unknown")
            if not name or not comp_type:
                return None
            return tracker.get_component_usage(
                platform=platform,
                name=name,
                component_type=comp_type,
                days=30,
            )
        except Exception:
            return None

    def _reference_file_exists(self, component: Any, ref: object) -> bool:
        """Best-effort existence check for `@file` references."""
        if not isinstance(ref, str):
            return False
        token = ref.strip()
        if token.startswith("@"):
            token = token[1:]
        if not token or token.startswith("$"):
            return False

        # Absolute-ish or explicitly relative refs.
        if token.startswith(("/", "~", "./", "../")):
            try:
                return Path(token).expanduser().exists()
            except Exception:
                return False

        install_path = getattr(component, "install_path", None)
        if not install_path:
            return False

        try:
            base = Path(str(install_path)).expanduser()
            base_dir = base.parent if base.suffix else base
            candidates = [
                base_dir / token,
                base_dir / token.lstrip("./"),
                base_dir.parent / token,
            ]
            return any(p.exists() for p in candidates)
        except Exception:
            return False

    def _reference_skill_status(self, component: Any, ref: object) -> str:
        """Return the platform where a `$skill` reference resolves, if known."""
        if not isinstance(ref, str) or not ref.strip():
            return ""
        wanted = ref.strip().lower()

        try:
            app = self.app
        except Exception:
            return ""

        scan = getattr(app, "scan_result", None)
        if not scan:
            return ""

        skills = getattr(scan, "skills", None) or []
        target_platform = getattr(component, "platform", "claude")

        # Prefer same-platform resolution.
        for skill in skills:
            if getattr(skill, "platform", "claude") != target_platform:
                continue
            if getattr(skill, "name", "").lower() == wanted:
                return str(target_platform)

        # Fall back to any platform.
        for skill in skills:
            if getattr(skill, "name", "").lower() == wanted:
                return str(getattr(skill, "platform", "claude"))

        return ""

        tracker = getattr(app, "analytics_tracker", None)
        if not tracker:
            return None

        try:
            platform = getattr(component, "platform", "claude")
            name = getattr(component, "name", "")
            comp_type = getattr(component, "type", "unknown")
            if not name or not comp_type:
                return None
            return tracker.get_component_usage(
                platform=platform,
                name=name,
                component_type=comp_type,
                days=30,
            )
        except Exception:
            return None
