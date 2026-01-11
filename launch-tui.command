#!/bin/bash
#
# Double-click this file to launch the Claude Code Tooling Index TUI
#

cd "$(dirname "$0")"

# Prefer running from this checkout (so local changes are picked up).
python3 -c "from claude_tooling_index.tui import ToolingIndexTUI; ToolingIndexTUI().run()" && exit 0

# Fallback: run the installed CLI (if available).
if command -v tooling-index &> /dev/null; then
    tooling-index tui
else
    echo "Error: couldn't run TUI (missing local package import and no tooling-index binary found)." >&2
    exit 1
fi
