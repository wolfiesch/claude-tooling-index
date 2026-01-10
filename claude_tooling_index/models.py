"""
Data models for Claude Code components
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class ComponentMetadata:
    """Base class for all component types"""

    name: str
    origin: str  # "in-house" | "official" | "community" | "external"
    status: str  # "active" | "disabled" | "error"
    last_modified: datetime
    install_path: Path

    # Type will be set by subclasses in __post_init__
    type: str = ""  # "skill" | "plugin" | "command" | "hook" | "mcp" | "binary"

    # Optional error information
    error_message: Optional[str] = None


@dataclass
class SkillMetadata(ComponentMetadata):
    """Metadata for a skill"""

    version: Optional[str] = None
    description: str = ""
    file_count: int = 0
    total_lines: int = 0
    has_docs: bool = False
    performance_notes: Optional[str] = None  # JSON string of parsed metrics
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.type = "skill"


@dataclass
class PluginMetadata(ComponentMetadata):
    """Metadata for a plugin"""

    marketplace: str = ""
    version: str = ""
    installed_at: Optional[datetime] = None
    git_commit_sha: str = ""
    provides_commands: List[str] = field(default_factory=list)
    provides_mcps: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.type = "plugin"


@dataclass
class CommandMetadata(ComponentMetadata):
    """Metadata for a command"""

    description: str = ""
    from_plugin: Optional[str] = None  # Plugin name if provided by plugin

    def __post_init__(self):
        self.type = "command"


@dataclass
class HookMetadata(ComponentMetadata):
    """Metadata for a hook"""

    trigger: str = ""  # e.g., "post_tool_use", "session_start"
    language: str = ""  # "python", "cpp", "bash", etc.
    file_size: int = 0

    def __post_init__(self):
        self.type = "hook"


@dataclass
class MCPMetadata(ComponentMetadata):
    """Metadata for an MCP server"""

    command: str = ""
    args: List[str] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # "stdio" | "sse"
    git_remote: Optional[str] = None

    def __post_init__(self):
        self.type = "mcp"


@dataclass
class BinaryMetadata(ComponentMetadata):
    """Metadata for a binary"""

    language: str = ""  # Detected from shebang or file analysis
    file_size: int = 0
    is_executable: bool = False

    def __post_init__(self):
        self.type = "binary"


@dataclass
class ScanResult:
    """Result of scanning all components"""

    skills: List[SkillMetadata] = field(default_factory=list)
    plugins: List[PluginMetadata] = field(default_factory=list)
    commands: List[CommandMetadata] = field(default_factory=list)
    hooks: List[HookMetadata] = field(default_factory=list)
    mcps: List[MCPMetadata] = field(default_factory=list)
    binaries: List[BinaryMetadata] = field(default_factory=list)

    scan_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """Total number of components scanned"""
        return (
            len(self.skills) +
            len(self.plugins) +
            len(self.commands) +
            len(self.hooks) +
            len(self.mcps) +
            len(self.binaries)
        )

    @property
    def all_components(self) -> List[ComponentMetadata]:
        """Get all components as a flat list"""
        return (
            self.skills +
            self.plugins +
            self.commands +
            self.hooks +
            self.mcps +
            self.binaries
        )


@dataclass
class InvocationRecord:
    """Record of a component invocation"""

    timestamp: str
    session_id: str
    component: str  # Format: "type:name"
    duration_ms: Optional[int] = None
    success: bool = True
