"""Claude Code Tooling Index
==========================
Catalog and analyze Claude Code components with usage analytics and TUI dashboard.
"""

__version__ = "1.0.0"
__author__ = "Wolfgang Schoenberger"

from .analytics import AnalyticsTracker
from .database import ToolingDatabase
from .models import (
    BinaryMetadata,
    CommandMetadata,
    ComponentMetadata,
    HookMetadata,
    InvocationRecord,
    MCPMetadata,
    PluginMetadata,
    ScanResult,
    SkillMetadata,
)
from .scanner import ToolingScanner

__all__ = [
    "ToolingScanner",
    "AnalyticsTracker",
    "ToolingDatabase",
    "ComponentMetadata",
    "SkillMetadata",
    "PluginMetadata",
    "CommandMetadata",
    "HookMetadata",
    "MCPMetadata",
    "BinaryMetadata",
    "ScanResult",
    "InvocationRecord",
]
