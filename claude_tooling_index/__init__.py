"""
Claude Code Tooling Index
==========================
Catalog and analyze Claude Code components with usage analytics and TUI dashboard.
"""

__version__ = "1.0.0"
__author__ = "Wolfgang Schoenberger"

from .scanner import ToolingScanner
from .analytics import AnalyticsTracker
from .database import ToolingDatabase
from .models import (
    ComponentMetadata,
    SkillMetadata,
    PluginMetadata,
    CommandMetadata,
    HookMetadata,
    MCPMetadata,
    BinaryMetadata,
    ScanResult,
    InvocationRecord,
)

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
