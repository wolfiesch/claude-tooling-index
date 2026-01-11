"""Markdown Exporter - Human-readable documentation for tooling index"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from ..models import (
    ScanResult,
    ComponentMetadata,
    SkillMetadata,
    PluginMetadata,
    CommandMetadata,
    HookMetadata,
    MCPMetadata,
    BinaryMetadata,
)


class MarkdownExporter:
    """Export scan results and components as Markdown documentation"""

    def __init__(
        self,
        include_analytics: bool = True,
        include_disabled: bool = True,
        include_toc: bool = True,
    ):
        self.include_analytics = include_analytics
        self.include_disabled = include_disabled
        self.include_toc = include_toc

    def export_scan_result(self, result: ScanResult) -> str:
        """Export full scan result to Markdown"""
        lines = []

        # Header
        platforms = sorted({getattr(c, "platform", "claude") for c in result.all_components}) if result.total_count else ["claude"]
        header = "Claude Code Tooling Index" if platforms == ["claude"] else "Tooling Index (Claude + Codex)"
        lines.append(f"# {header}")
        lines.append("")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Total Components:** {result.total_count}")
        lines.append("")
        lines.append("| Type | Count |")
        lines.append("|------|-------|")
        lines.append(f"| Skills | {len(result.skills)} |")
        lines.append(f"| Plugins | {len(result.plugins)} |")
        lines.append(f"| Commands | {len(result.commands)} |")
        lines.append(f"| Hooks | {len(result.hooks)} |")
        lines.append(f"| MCPs | {len(result.mcps)} |")
        lines.append(f"| Binaries | {len(result.binaries)} |")
        lines.append("")

        # Table of Contents
        if self.include_toc:
            lines.append("## Table of Contents")
            lines.append("")
            lines.append("- [Skills](#skills)")
            lines.append("- [Plugins](#plugins)")
            lines.append("- [Commands](#commands)")
            lines.append("- [Hooks](#hooks)")
            lines.append("- [MCPs](#mcps)")
            lines.append("- [Binaries](#binaries)")
            lines.append("")

        # Skills
        if result.skills:
            lines.append("## Skills")
            lines.append("")
            lines.extend(self._format_skills_table(result.skills))
            lines.append("")

            # Detailed skill info
            for skill in result.skills:
                if not self.include_disabled and skill.status == "disabled":
                    continue
                lines.extend(self._format_skill_detail(skill))

        # Plugins
        if result.plugins:
            lines.append("## Plugins")
            lines.append("")
            lines.extend(self._format_plugins_table(result.plugins))
            lines.append("")

        # Commands
        if result.commands:
            lines.append("## Commands")
            lines.append("")
            lines.extend(self._format_commands_table(result.commands))
            lines.append("")

        # Hooks
        if result.hooks:
            lines.append("## Hooks")
            lines.append("")
            lines.extend(self._format_hooks_table(result.hooks))
            lines.append("")

        # MCPs
        if result.mcps:
            lines.append("## MCPs")
            lines.append("")
            lines.extend(self._format_mcps_table(result.mcps))
            lines.append("")

        # Binaries
        if result.binaries:
            lines.append("## Binaries")
            lines.append("")
            lines.extend(self._format_binaries_table(result.binaries))
            lines.append("")

        # Errors
        if result.errors:
            lines.append("## Errors")
            lines.append("")
            for error in result.errors:
                lines.append(f"- {error}")
            lines.append("")

        return "\n".join(lines)

    def export_to_file(self, result: ScanResult, output_path: Path):
        """Export to a Markdown file"""
        md_str = self.export_scan_result(result)
        with open(output_path, "w") as f:
            f.write(md_str)

    def _format_skills_table(self, skills: List[SkillMetadata]) -> List[str]:
        """Format skills as a table"""
        lines = []
        lines.append("| Name | Platform | Version | Status | Files | Lines | Description |")
        lines.append("|------|----------|---------|--------|-------|-------|-------------|")

        for skill in sorted(skills, key=lambda s: s.name.lower()):
            version = skill.version or "-"
            status = self._status_badge(skill.status)
            platform = getattr(skill, "platform", "claude")
            desc = (skill.description[:50] + "...") if len(skill.description) > 50 else skill.description
            lines.append(
                f"| {skill.name} | {platform} | {version} | {status} | {skill.file_count} | {skill.total_lines} | {desc} |"
            )

        return lines

    def _format_skill_detail(self, skill: SkillMetadata) -> List[str]:
        """Format detailed skill information"""
        lines = []
        lines.append(f"### {skill.name}")
        lines.append("")

        if skill.description:
            lines.append(f"> {skill.description}")
            lines.append("")

        lines.append(f"- **Version:** {skill.version or 'N/A'}")
        lines.append(f"- **Platform:** {getattr(skill, 'platform', 'claude')}")
        lines.append(f"- **Status:** {skill.status}")
        lines.append(f"- **Origin:** {skill.origin}")
        lines.append(f"- **Files:** {skill.file_count}")
        lines.append(f"- **Lines:** {skill.total_lines}")
        lines.append(f"- **Path:** `{skill.install_path}`")

        if skill.performance_notes:
            lines.append("")
            lines.append("**Performance:**")
            try:
                perf = json.loads(skill.performance_notes)
                if isinstance(perf, dict):
                    for op, metrics in perf.items():
                        if isinstance(metrics, dict):
                            time_val = metrics.get("time", "N/A")
                            speedup = metrics.get("speedup", "")
                            lines.append(f"- {op}: {time_val} {speedup}")
                        else:
                            lines.append(f"- {op}: {metrics}")
            except (json.JSONDecodeError, TypeError):
                lines.append(f"- {skill.performance_notes}")

        lines.append("")
        return lines

    def _format_plugins_table(self, plugins: List[PluginMetadata]) -> List[str]:
        """Format plugins as a table"""
        lines = []
        lines.append("| Name | Platform | Version | Marketplace | Origin | Status |")
        lines.append("|------|----------|---------|-------------|--------|--------|")

        for plugin in sorted(plugins, key=lambda p: p.name.lower()):
            status = self._status_badge(plugin.status)
            platform = getattr(plugin, "platform", "claude")
            lines.append(
                f"| {plugin.name} | {platform} | {plugin.version} | {plugin.marketplace} | {plugin.origin} | {status} |"
            )

        return lines

    def _format_commands_table(self, commands: List[CommandMetadata]) -> List[str]:
        """Format commands as a table"""
        lines = []
        lines.append("| Command | Platform | Description | Origin | Status |")
        lines.append("|---------|----------|-------------|--------|--------|")

        for cmd in sorted(commands, key=lambda c: c.name.lower()):
            status = self._status_badge(cmd.status)
            platform = getattr(cmd, "platform", "claude")
            desc = (cmd.description[:60] + "...") if len(cmd.description) > 60 else cmd.description
            lines.append(f"| /{cmd.name} | {platform} | {desc} | {cmd.origin} | {status} |")

        return lines

    def _format_hooks_table(self, hooks: List[HookMetadata]) -> List[str]:
        """Format hooks as a table"""
        lines = []
        lines.append("| Name | Platform | Trigger | Language | Size | Status |")
        lines.append("|------|----------|---------|----------|------|--------|")

        for hook in sorted(hooks, key=lambda h: h.name.lower()):
            status = self._status_badge(hook.status)
            size = self._format_size(hook.file_size)
            platform = getattr(hook, "platform", "claude")
            lines.append(
                f"| {hook.name} | {platform} | {hook.trigger} | {hook.language} | {size} | {status} |"
            )

        return lines

    def _format_mcps_table(self, mcps: List[MCPMetadata]) -> List[str]:
        """Format MCPs as a table"""
        lines = []
        lines.append("| Name | Platform | Command | Transport | Origin | Status |")
        lines.append("|------|----------|---------|-----------|--------|--------|")

        for mcp in sorted(mcps, key=lambda m: m.name.lower()):
            status = self._status_badge(mcp.status)
            cmd = mcp.command[:30] + "..." if len(mcp.command) > 30 else mcp.command
            platform = getattr(mcp, "platform", "claude")
            lines.append(
                f"| {mcp.name} | {platform} | `{cmd}` | {mcp.transport} | {mcp.origin} | {status} |"
            )

        return lines

    def _format_binaries_table(self, binaries: List[BinaryMetadata]) -> List[str]:
        """Format binaries as a table"""
        lines = []
        lines.append("| Name | Platform | Language | Size | Executable | Status |")
        lines.append("|------|----------|----------|------|------------|--------|")

        for binary in sorted(binaries, key=lambda b: b.name.lower()):
            status = self._status_badge(binary.status)
            size = self._format_size(binary.file_size)
            exec_status = "Yes" if binary.is_executable else "No"
            platform = getattr(binary, "platform", "claude")
            lines.append(
                f"| {binary.name} | {platform} | {binary.language} | {size} | {exec_status} | {status} |"
            )

        return lines

    def _status_badge(self, status: str) -> str:
        """Format status as an emoji badge"""
        badges = {
            "active": "🟢 Active",
            "disabled": "⚪ Disabled",
            "error": "🔴 Error",
            "unknown": "🟡 Unknown",
        }
        return badges.get(status, status)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
