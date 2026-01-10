---
description: Scan ~/.claude directory and refresh the tooling index
---

# Refresh Tooling Index

Scan your ~/.claude directory to update the component index and database.

## What Gets Scanned

1. **Skills** (`~/.claude/skills/`) - SKILL.md parsing, performance metrics
2. **Plugins** (`~/.claude/plugins/`) - installed_plugins.json parsing
3. **Commands** (`~/.claude/commands/`) - Frontmatter extraction
4. **Hooks** (`~/.claude/hooks/`) - Language detection, trigger identification
5. **MCPs** (`~/.claude/mcp.json`) - MCP server configuration
6. **Binaries** (`~/.claude/bin/`) - Shebang/language detection

## Usage

Basic scan with database update:

```bash
cd ~/claude-tooling-index && python3 cli.py scan
```

Verbose output showing all components:

```bash
python3 cli.py scan --verbose
```

Scan without updating database:

```bash
python3 cli.py scan --no-db
```

## Output

```
🔍 Scanning ~/.claude directory...
💾 Updating database...

✅ Scan complete!
   Total components: 89
   Skills: 23
   Plugins: 17
   Commands: 23
   Hooks: 15
   MCPs: 0
   Binaries: 11
```
