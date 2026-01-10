#!/bin/bash
#
# Double-click this file to launch the Claude Code Tooling Index TUI
#

cd "$(dirname "$0")"

# Check if tooling-index is installed
if command -v tooling-index &> /dev/null; then
    tooling-index tui
else
    # Fallback: run directly via Python
    python3 -c "from claude_tooling_index.tui import ToolingIndexTUI; ToolingIndexTUI().run()"
fi
