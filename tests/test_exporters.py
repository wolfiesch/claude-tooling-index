from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from claude_tooling_index.exporters import JSONExporter, MarkdownExporter
from claude_tooling_index.models import (
    BinaryMetadata,
    CommandMetadata,
    HookMetadata,
    MCPMetadata,
    PluginMetadata,
    ScanResult,
    SkillMetadata,
)


def test_json_exporter_includes_platform_and_summary(tmp_path: Path) -> None:
    skill = SkillMetadata(
        name="my-skill",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "my-skill",
        platform="codex",
        version="1.2.3",
        description="Example",
        file_count=2,
        total_lines=10,
        has_docs=True,
    )
    result = ScanResult(skills=[skill])

    exporter = JSONExporter(pretty=False)
    payload = json.loads(exporter.export_scan_result(result))

    assert payload["summary"]["total_components"] == 1
    assert payload["components"]["skills"][0]["platform"] == "codex"


def test_markdown_exporter_renders_platform_column(tmp_path: Path) -> None:
    skill = SkillMetadata(
        name="my-skill",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "my-skill",
        platform="claude",
        version="1.0.0",
        description="A skill",
        file_count=1,
        total_lines=1,
        has_docs=True,
    )
    result = ScanResult(skills=[skill])

    exporter = MarkdownExporter(include_disabled=True)
    md = exporter.export_scan_result(result)

    assert "| Name | Platform | Version |" in md
    assert "| my-skill | claude |" in md


def test_exporters_cover_all_component_types(tmp_path: Path) -> None:
    skill = SkillMetadata(
        name="skill",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "skill",
        platform="claude",
        version="1.0.0",
        description="Example skill",
        file_count=1,
        total_lines=1,
        has_docs=True,
        performance_notes=json.dumps({"op": {"time": "1ms", "speedup": "2x"}}),
        dependencies=["dep1"],
        dependency_sources=["requirements.txt"],
        frontmatter_extra={"metadata": {"short": "x"}},
        invocation_aliases=["/skill"],
        invocation_arguments="arg $1",
        invocation_instruction="Do: @$1",
        references={"files": ["@CLAUDE.md"], "skills": ["other"]},
        context_fork_hint="This forks context",
        when_to_use="When to use it",
        trigger_rules=["Rule A"],
        detected_tools={"mcp_tools": ["mcp__neon__run_sql"], "composio_tools": ["GMAIL_SEND_EMAIL"]},
        detected_toolkits=["neon", "gmail"],
        inputs=["recipient: x"],
        outputs=["result: y"],
        safety_notes="Redact secrets",
        capability_tags=["email", "database"],
        inputs_schema=[{"name": "recipient", "description": "x", "required": True, "default": ""}],
        outputs_schema=[{"name": "result", "description": "y", "required": False, "default": ""}],
        examples=["run_composio_tool(\"GMAIL_SEND_EMAIL\", {})"],
        prerequisites=["pip install x"],
        gotchas=["Beware rate limits"],
        required_env_vars=["API_KEY"],
        trigger_types=["manual"],
        context_behavior="unknown",
        side_effects=["email"],
        risk_level="medium",
        depends_on_skills=["other"],
        used_by_skills=["x"],
    )
    plugin = PluginMetadata(
        name="plugin",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "plugin",
        platform="codex",
        marketplace="custom",
        version="2.0.0",
        provides_commands=["c1"],
        provides_mcps=["m1"],
        commands_detail={"c1": "desc"},
        mcps_detail={"srv": {"command": "x", "transport": "stdio", "args_count": 0}},
    )
    command = CommandMetadata(
        name="cmd",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "cmd.md",
        platform="claude",
        description="Command",
        from_plugin="plugin",
    )
    hook = HookMetadata(
        name="hook.py",
        origin="official",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "hook.py",
        platform="claude",
        trigger="post_tool_use",
        trigger_event="post_tool_use",
        language="python",
        file_size=10,
    )
    mcp = MCPMetadata(
        name="mcp",
        origin="community",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "mcp",
        platform="codex",
        command="python3",
        args=["-m", "server"],
        env_vars={"API_KEY": "<redacted>"},
        transport="stdio",
        config_extra={"cwd": "/tmp", "token": "<redacted>"},
    )
    binary = BinaryMetadata(
        name="bin",
        origin="in-house",
        status="active",
        last_modified=datetime(2026, 1, 11, 0, 0, 0),
        install_path=tmp_path / "bin",
        platform="claude",
        language="bash",
        file_size=1,
        is_executable=True,
    )

    result = ScanResult(
        skills=[skill],
        plugins=[plugin],
        commands=[command],
        hooks=[hook],
        mcps=[mcp],
        binaries=[binary],
    )

    md = MarkdownExporter(include_disabled=True, include_toc=True).export_scan_result(result)
    assert "## Skills" in md
    assert "## Plugins" in md
    assert "## Commands" in md
    assert "## Hooks" in md
    assert "## MCPs" in md
    assert "## Binaries" in md

    payload = json.loads(JSONExporter(pretty=False).export_scan_result(result))
    exported_mcp = payload["components"]["mcps"][0]
    assert exported_mcp["command"] == "python3"
    assert exported_mcp["env_vars"]["API_KEY"] == "<redacted>"
    assert exported_mcp["config_extra"]["cwd"] == "/tmp"
    exported_plugin = payload["components"]["plugins"][0]
    assert exported_plugin["commands_detail"]["c1"] == "desc"
    assert exported_plugin["mcps_detail"]["srv"]["transport"] == "stdio"
    exported_hook = payload["components"]["hooks"][0]
    assert exported_hook["trigger_event"] == "post_tool_use"
    exported_skill = payload["components"]["skills"][0]
    assert exported_skill["invocation_aliases"] == ["/skill"]
    assert exported_skill["invocation_arguments"] == "arg $1"
    assert exported_skill["invocation_instruction"] == "Do: @$1"
    assert exported_skill["references"]["files"] == ["@CLAUDE.md"]
    assert exported_skill["context_fork_hint"] == "This forks context"
    assert exported_skill["when_to_use"] == "When to use it"
    assert exported_skill["trigger_rules"] == ["Rule A"]
    assert exported_skill["detected_toolkits"] == ["neon", "gmail"]
    assert exported_skill["detected_tools"]["mcp_tools"] == ["mcp__neon__run_sql"]
    assert exported_skill["inputs"] == ["recipient: x"]
    assert exported_skill["outputs"] == ["result: y"]
    assert exported_skill["safety_notes"] == "Redact secrets"
    assert exported_skill["capability_tags"] == ["email", "database"]
    assert exported_skill["required_env_vars"] == ["API_KEY"]
    assert exported_skill["risk_level"] == "medium"

    # Exercise export_components on mixed inputs (dataclass and dict).
    mixed = JSONExporter(pretty=False).export_components([skill, {"name": "x"}])
    mixed_payload = json.loads(mixed)
    assert mixed_payload["count"] == 2
