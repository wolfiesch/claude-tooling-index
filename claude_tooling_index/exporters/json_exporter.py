"""JSON exporter for the tooling index.

This exporter produces a structured JSON representation of scan results and
component lists.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

from ..models import ComponentMetadata, ScanResult


class JSONExporter:
    """Export scan results and components as structured JSON."""

    def __init__(self, include_analytics: bool = True, pretty: bool = True):
        self.include_analytics = include_analytics
        self.pretty = pretty

    def export_scan_result(self, result: ScanResult) -> str:
        """Export a full scan result to JSON.

        Args:
            result: Scan result to export.

        Returns:
            A JSON document as a string.
        """
        data = {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_components": result.total_count,
                "skills": len(result.skills),
                "plugins": len(result.plugins),
                "commands": len(result.commands),
                "hooks": len(result.hooks),
                "mcps": len(result.mcps),
                "binaries": len(result.binaries),
            },
            "components": {
                "skills": [self._serialize_component(s) for s in result.skills],
                "plugins": [self._serialize_component(p) for p in result.plugins],
                "commands": [self._serialize_component(c) for c in result.commands],
                "hooks": [self._serialize_component(h) for h in result.hooks],
                "mcps": [self._serialize_component(m) for m in result.mcps],
                "binaries": [self._serialize_component(b) for b in result.binaries],
            },
            "errors": result.errors,
        }

        return self._to_json(data)

    def export_components(
        self, components: List[Union[ComponentMetadata, Dict[str, Any]]]
    ) -> str:
        """Export a list of components to JSON.

        Args:
            components: Components (or already-serialized dicts) to export.

        Returns:
            A JSON document as a string.
        """
        data = {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "count": len(components),
            "components": [
                self._serialize_component(c) if hasattr(c, "name") else c
                for c in components
            ],
        }

        return self._to_json(data)

    def export_to_file(
        self,
        result: Union[ScanResult, List[ComponentMetadata]],
        output_path: Path,
    ):
        """Export scan data to a JSON file.

        Args:
            result: Either a scan result or a list of components.
            output_path: Destination file path.
        """
        if isinstance(result, ScanResult):
            json_str = self.export_scan_result(result)
        else:
            json_str = self.export_components(result)

        with open(output_path, "w") as f:
            f.write(json_str)

    def _serialize_component(self, component: ComponentMetadata) -> Dict[str, Any]:
        """Serialize a component to a dictionary."""
        data = {
            "name": component.name,
            "platform": getattr(component, "platform", "claude"),
            "type": component.type,
            "origin": component.origin,
            "status": component.status,
            "last_modified": component.last_modified.isoformat(),
            "install_path": str(component.install_path),
        }

        # Add type-specific fields
        if hasattr(component, "version") and component.version:
            data["version"] = component.version

        if hasattr(component, "description") and component.description:
            data["description"] = component.description

        if hasattr(component, "file_count"):
            data["file_count"] = component.file_count

        if hasattr(component, "total_lines"):
            data["total_lines"] = component.total_lines

        if hasattr(component, "has_docs"):
            data["has_docs"] = component.has_docs

        if hasattr(component, "performance_notes") and component.performance_notes:
            # Parse JSON string to include as nested object
            try:
                data["performance"] = json.loads(component.performance_notes)
            except (json.JSONDecodeError, TypeError):
                data["performance_notes"] = component.performance_notes

        if hasattr(component, "dependencies") and component.dependencies:
            data["dependencies"] = component.dependencies

        if hasattr(component, "dependency_sources") and component.dependency_sources:
            data["dependency_sources"] = component.dependency_sources

        if hasattr(component, "frontmatter_extra") and component.frontmatter_extra:
            data["frontmatter_extra"] = component.frontmatter_extra

        if hasattr(component, "invocation_aliases") and component.invocation_aliases:
            data["invocation_aliases"] = component.invocation_aliases

        if (
            hasattr(component, "invocation_arguments")
            and getattr(component, "invocation_arguments", "")
        ):
            data["invocation_arguments"] = component.invocation_arguments

        if (
            hasattr(component, "invocation_instruction")
            and getattr(component, "invocation_instruction", "")
        ):
            data["invocation_instruction"] = component.invocation_instruction

        if hasattr(component, "references") and component.references:
            data["references"] = component.references

        if hasattr(component, "context_fork_hint") and component.context_fork_hint:
            data["context_fork_hint"] = component.context_fork_hint

        if hasattr(component, "when_to_use") and component.when_to_use:
            data["when_to_use"] = component.when_to_use

        if hasattr(component, "trigger_rules") and component.trigger_rules:
            data["trigger_rules"] = component.trigger_rules

        if hasattr(component, "detected_tools") and component.detected_tools:
            data["detected_tools"] = component.detected_tools

        if hasattr(component, "detected_toolkits") and component.detected_toolkits:
            data["detected_toolkits"] = component.detected_toolkits

        if hasattr(component, "inputs") and component.inputs:
            data["inputs"] = component.inputs

        if hasattr(component, "outputs") and component.outputs:
            data["outputs"] = component.outputs

        if hasattr(component, "safety_notes") and component.safety_notes:
            data["safety_notes"] = component.safety_notes

        if hasattr(component, "capability_tags") and component.capability_tags:
            data["capability_tags"] = component.capability_tags

        if hasattr(component, "inputs_schema") and component.inputs_schema:
            data["inputs_schema"] = component.inputs_schema

        if hasattr(component, "outputs_schema") and component.outputs_schema:
            data["outputs_schema"] = component.outputs_schema

        if hasattr(component, "examples") and component.examples:
            data["examples"] = component.examples

        if hasattr(component, "prerequisites") and component.prerequisites:
            data["prerequisites"] = component.prerequisites

        if hasattr(component, "gotchas") and component.gotchas:
            data["gotchas"] = component.gotchas

        if hasattr(component, "required_env_vars") and component.required_env_vars:
            data["required_env_vars"] = component.required_env_vars

        if hasattr(component, "trigger_types") and component.trigger_types:
            data["trigger_types"] = component.trigger_types

        if hasattr(component, "context_behavior") and component.context_behavior:
            data["context_behavior"] = component.context_behavior

        if hasattr(component, "side_effects") and component.side_effects:
            data["side_effects"] = component.side_effects

        if hasattr(component, "risk_level") and component.risk_level:
            data["risk_level"] = component.risk_level

        if hasattr(component, "depends_on_skills") and component.depends_on_skills:
            data["depends_on_skills"] = component.depends_on_skills

        if hasattr(component, "used_by_skills") and component.used_by_skills:
            data["used_by_skills"] = component.used_by_skills

        if hasattr(component, "llm_summary") and component.llm_summary:
            data["llm_summary"] = component.llm_summary

        if hasattr(component, "llm_tags") and component.llm_tags:
            data["llm_tags"] = component.llm_tags

        if hasattr(component, "marketplace") and component.marketplace:
            data["marketplace"] = component.marketplace

        if hasattr(component, "author") and component.author:
            data["author"] = component.author

        if hasattr(component, "homepage") and component.homepage:
            data["homepage"] = component.homepage

        if hasattr(component, "repository") and component.repository:
            data["repository"] = component.repository

        if hasattr(component, "license") and component.license:
            data["license"] = component.license

        if hasattr(component, "provides_commands") and component.provides_commands:
            data["provides_commands"] = component.provides_commands

        if hasattr(component, "provides_mcps") and component.provides_mcps:
            data["provides_mcps"] = component.provides_mcps

        if hasattr(component, "trigger") and component.trigger:
            data["trigger"] = component.trigger
        if hasattr(component, "trigger_event") and component.trigger_event:
            data["trigger_event"] = component.trigger_event

        if hasattr(component, "language") and component.language:
            data["language"] = component.language

        if hasattr(component, "file_size"):
            data["file_size"] = component.file_size

        if hasattr(component, "is_executable"):
            data["is_executable"] = component.is_executable

        if hasattr(component, "command") and component.command:
            data["command"] = component.command

        if hasattr(component, "args") and component.args:
            data["args"] = component.args

        if hasattr(component, "env_vars") and component.env_vars:
            data["env_vars"] = component.env_vars

        if hasattr(component, "transport") and component.transport:
            data["transport"] = component.transport

        if hasattr(component, "source") and component.source:
            data["source"] = component.source

        if hasattr(component, "source_detail") and component.source_detail:
            data["source_detail"] = component.source_detail

        if hasattr(component, "git_remote") and component.git_remote:
            data["git_remote"] = component.git_remote

        if hasattr(component, "config_extra") and component.config_extra:
            data["config_extra"] = component.config_extra

        if hasattr(component, "shebang") and component.shebang:
            data["shebang"] = component.shebang

        if hasattr(component, "commands_detail") and component.commands_detail:
            data["commands_detail"] = component.commands_detail

        if hasattr(component, "mcps_detail") and component.mcps_detail:
            data["mcps_detail"] = component.mcps_detail

        if component.error_message:
            data["error"] = component.error_message

        return data

    def _to_json(self, data: Dict[str, Any]) -> str:
        """Convert a Python object to a JSON string."""
        if self.pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)
