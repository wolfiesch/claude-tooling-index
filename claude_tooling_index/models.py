"""Data models for Claude Code components
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ComponentMetadata:
    """Base class for all component types"""

    name: str
    origin: str  # "in-house" | "official" | "community" | "external"
    status: str  # "active" | "disabled" | "error"
    last_modified: datetime
    install_path: Path
    platform: str = "claude"  # "claude" | "codex"

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


# =============================================================================
# Phase 6: Extended Metadata Models
# =============================================================================


@dataclass
class SkillUsage:
    """Individual skill usage statistics from ~/.claude.json"""

    name: str
    usage_count: int
    last_used_at: Optional[datetime] = None


@dataclass
class ProjectMetric:
    """Per-project productivity and cost metrics from ~/.claude.json"""

    path: str
    last_session_cost: Optional[float] = None
    last_session_duration_ms: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    api_latency_ms: int = 0
    onboarding_seen_count: int = 0
    has_trust_accepted: bool = False


@dataclass
class UserSettingsMetadata:
    """User settings and usage metrics from ~/.claude.json"""

    total_startups: int = 0
    first_startup_date: Optional[datetime] = None
    account_age_days: int = 0
    sessions_per_day: float = 0.0
    memory_usage_count: int = 0
    prompt_queue_use_count: int = 0

    # Skill usage
    skill_usage: Dict[str, SkillUsage] = field(default_factory=dict)
    top_skills: List[SkillUsage] = field(default_factory=list)

    # Tip/feature adoption
    tip_adoption: Dict[str, int] = field(default_factory=dict)
    high_adoption_features: List[str] = field(default_factory=list)

    # Project metrics
    project_metrics: Dict[str, ProjectMetric] = field(default_factory=dict)
    total_projects: int = 0

    # GitHub repos
    github_repos: Dict[str, List[str]] = field(default_factory=dict)
    total_github_repos: int = 0


@dataclass
class EventMetrics:
    """Event queue analytics from ~/.claude/data/event_queue.jsonl"""

    total_events: int = 0
    tool_frequency: Dict[str, int] = field(default_factory=dict)
    top_tools: List[tuple] = field(default_factory=list)  # [(tool_name, count), ...]
    session_count: int = 0
    event_types: Dict[str, int] = field(default_factory=dict)
    permission_distribution: Dict[str, float] = field(default_factory=dict)
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None


@dataclass
class InsightMetrics:
    """Insights analytics from ~/.claude/data/insights.db"""

    total_insights: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_project: Dict[str, int] = field(default_factory=dict)
    processed_sessions: int = 0
    recent_warnings: List[str] = field(default_factory=list)
    recent_patterns: List[str] = field(default_factory=list)
    recent_tradeoffs: List[str] = field(default_factory=list)


@dataclass
class SessionMetrics:
    """Session analytics from ~/.claude/data/sessions/"""

    total_sessions: int = 0
    prompts_per_session: float = 0.0
    project_distribution: Dict[str, int] = field(default_factory=dict)
    activity_by_day: Dict[str, int] = field(default_factory=dict)
    top_projects: List[tuple] = field(default_factory=list)  # [(project, count), ...]


@dataclass
class TaskMetrics:
    """Task/todo analytics from ~/.claude/todos/"""

    total_tasks: int = 0
    completed: int = 0
    pending: int = 0
    in_progress: int = 0
    completion_rate: float = 0.0


@dataclass
class TranscriptMetrics:
    """Token economics and tool usage from transcript files"""

    total_transcripts: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    tool_usage: Dict[str, int] = field(default_factory=dict)
    model_usage: Dict[str, int] = field(default_factory=dict)
    top_tools: List[tuple] = field(default_factory=list)  # [(tool, count), ...]


@dataclass
class GrowthMetrics:
    """L1-L5 progression metrics from agentic-growth framework"""

    current_level: str = "L1"
    total_edges: int = 0
    total_patterns: int = 0
    edges_by_category: Dict[str, int] = field(default_factory=dict)
    patterns_by_category: Dict[str, int] = field(default_factory=dict)
    projects_with_edges: int = 0


@dataclass
class ExtendedScanResult:
    """Extended scan result including Phase 6 metadata"""

    # Core scan result
    core: ScanResult = field(default_factory=ScanResult)

    # Phase 6 extended metadata (T0)
    user_settings: Optional[UserSettingsMetadata] = None
    event_metrics: Optional[EventMetrics] = None
    insight_metrics: Optional[InsightMetrics] = None
    # Phase 6 T1
    session_metrics: Optional[SessionMetrics] = None
    task_metrics: Optional[TaskMetrics] = None
    # Phase 6 T2
    transcript_metrics: Optional[TranscriptMetrics] = None
    growth_metrics: Optional[GrowthMetrics] = None

    @property
    def total_count(self) -> int:
        """Total component count from core scan"""
        return self.core.total_count
