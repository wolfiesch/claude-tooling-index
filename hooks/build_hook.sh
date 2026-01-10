#!/bin/bash
#
# Build script for the C++ hook binary
# Compiles post_tool_use_tooling.cpp and installs to ~/.claude/hooks/
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 Building tooling-index hook..."

# Check for required tools
if ! command -v cmake &> /dev/null; then
    echo "❌ CMake not found. Please install CMake first."
    echo "   macOS: brew install cmake"
    echo "   Ubuntu: sudo apt install cmake"
    exit 1
fi

# Check for SQLite3
if ! pkg-config --exists sqlite3 2>/dev/null; then
    # Try to find it anyway (macOS has it by default)
    if ! [ -f /usr/lib/libsqlite3.dylib ] && ! [ -f /usr/lib/x86_64-linux-gnu/libsqlite3.so ]; then
        echo "⚠️  SQLite3 development files not found via pkg-config."
        echo "   Attempting build anyway (macOS usually has SQLite3 built-in)..."
    fi
fi

# Create build directory
mkdir -p build
cd build

# Configure with CMake
echo "📦 Configuring..."
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
echo "🔨 Compiling..."
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)

# Create hooks directory if needed
mkdir -p "$HOME/.claude/hooks"

# Install
echo "📥 Installing..."
cp post_tool_use_tooling "$HOME/.claude/hooks/"
chmod +x "$HOME/.claude/hooks/post_tool_use_tooling"

echo ""
echo "✅ Hook installed to ~/.claude/hooks/post_tool_use_tooling"
echo ""
echo "The hook will automatically track skill and command invocations"
echo "when you use Claude Code. To verify:"
echo "  ls -la ~/.claude/hooks/post_tool_use_tooling"
echo ""
echo "To uninstall, simply delete the file:"
echo "  rm ~/.claude/hooks/post_tool_use_tooling"
