"""JSON Exporter - Structured API export for tooling index"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

from ..models import ComponentMetadata, ScanResult


class JSONExporter:
    """Export scan results and components as structured JSON"""

    def __init__(self, include_analytics: bool = True, pretty: bool = True):
        self.include_analytics = include_analytics
        self.pretty = pretty

    def export_scan_result(self, result: ScanResult) -> str:
        """Export full scan result to JSON"""
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
        """Export a list of components to JSON"""
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
        """Export to a JSON file"""
        if isinstance(result, ScanResult):
            json_str = self.export_scan_result(result)
        else:
            json_str = self.export_components(result)

        with open(output_path, "w") as f:
            f.write(json_str)

    def _serialize_component(self, component: ComponentMetadata) -> Dict[str, Any]:
        """Serialize a component to a dictionary"""
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

        if hasattr(component, "marketplace") and component.marketplace:
            data["marketplace"] = component.marketplace

        if hasattr(component, "provides_commands") and component.provides_commands:
            data["provides_commands"] = component.provides_commands

        if hasattr(component, "provides_mcps") and component.provides_mcps:
            data["provides_mcps"] = component.provides_mcps

        if hasattr(component, "trigger") and component.trigger:
            data["trigger"] = component.trigger

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

        if component.error_message:
            data["error"] = component.error_message

        return data

    def _to_json(self, data: Dict[str, Any]) -> str:
        """Convert to JSON string"""
        if self.pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)
