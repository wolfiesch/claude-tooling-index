#!/bin/bash
#
# INSTALL.sh - Auto-setup script for Claude Code Tooling Index
#
# This script:
# 1. Installs the Python package
# 2. Creates the database directory
# 3. Initializes the SQLite database
# 4. Runs an initial scan
# 5. Optionally builds and installs the C++ hook
#
set -e

echo "🔧 Installing Claude Code Tooling Index..."
echo ""

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for ~/.claude directory
CLAUDE_HOME="${HOME}/.claude"
if [ ! -d "$CLAUDE_HOME" ]; then
    echo "❌ Error: ~/.claude not found."
    echo "   Please install Claude Code first."
    exit 1
fi

echo "✓ Found Claude Code installation at $CLAUDE_HOME"

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3 not found."
    echo "   Please install Python 3.8 or later."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Found Python $PYTHON_VERSION"

# Install Python package
echo ""
echo "📦 Installing Python package..."
pip3 install -e . --user 2>/dev/null || pip install -e . --user

# Create data directory
echo ""
echo "📁 Creating data directory..."
mkdir -p "$CLAUDE_HOME/data"

# Initialize database
echo ""
echo "🗄️  Initializing database..."
$PYTHON_CMD -c "from claude_tooling_index.analytics import AnalyticsTracker; t = AnalyticsTracker(); t.close(); print('   Database created at ~/.claude/data/tooling_index.db')"

# Run initial scan
echo ""
echo "🔍 Running initial scan..."
$PYTHON_CMD cli.py scan

# Ask about C++ hook
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Optional: Install C++ Performance Hook"
echo ""
echo "The C++ hook automatically tracks skill and command invocations"
echo "with <1ms overhead (vs ~50ms for Python hooks)."
echo ""
echo "Requirements: CMake, C++ compiler, SQLite3"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Install C++ hook? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v cmake &> /dev/null; then
        echo ""
        echo "🔨 Building C++ hook..."
        cd hooks
        ./build_hook.sh
        cd ..
    else
        echo ""
        echo "⚠️  CMake not found. Skipping C++ hook installation."
        echo "   To install later: cd hooks && ./build_hook.sh"
    fi
else
    echo ""
    echo "ℹ️  Skipped C++ hook. To install later:"
    echo "   cd $SCRIPT_DIR/hooks && ./build_hook.sh"
fi

# Done
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Usage:"
echo "  tooling-index tui          # Launch interactive dashboard"
echo "  tooling-index scan         # Refresh component index"
echo "  tooling-index stats        # View usage analytics"
echo "  tooling-index list         # List all components"
echo "  tooling-index search EMAIL # Search components"
echo "  tooling-index export       # Export to markdown/json"
echo ""
echo "Or run directly:"
echo "  python3 $SCRIPT_DIR/cli.py tui"
echo ""
echo "From Claude Code, use the slash commands:"
echo "  /tooling-index   # Launch dashboard"
echo "  /tooling-scan    # Refresh index"
echo "  /tooling-stats   # View analytics"
echo ""
