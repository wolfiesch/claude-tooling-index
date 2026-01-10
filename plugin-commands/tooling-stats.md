---
description: Show usage analytics and statistics for Claude Code tooling
---

# Tooling Analytics

Display usage statistics and analytics for your Claude Code setup.

## Available Metrics

- **Total Invocations**: How many times components have been used
- **Most Used Components**: Top 10 most frequently used skills and commands
- **Recent Installations**: Recently installed or updated components
- **Performance Metrics**: Average execution time per component

## Usage

Show stats for last 30 days (default):

```bash
cd ~/claude-tooling-index && python3 cli.py stats
```

Show stats for custom time period:

```bash
python3 cli.py stats --days 7    # Last week
python3 cli.py stats --days 90   # Last 3 months
```

## Output Example

```
📊 Usage Statistics (last 30 days)

============================================================

📈 Total Invocations: 156

🔥 Most Used Components:
  1. gmail-gateway (skill) - 45 times
  2. commit (command) - 32 times
  3. handoffcodex (command) - 28 times

📦 Recent Installations:
  - episodic-memory (plugin) - v1.0.0 at 2026-01-08
  - twitter-manager (skill) - v2.1.0 at 2026-01-05

⚡ Performance (avg execution time):
  - gmail-gateway: 320.5ms
  - twitter-research: 450.2ms
```

## Other Commands

List all components:

```bash
python3 cli.py list
python3 cli.py list --type skill --origin in-house
python3 cli.py list --json
```

Search components:

```bash
python3 cli.py search "gmail"
python3 cli.py search "performance" --type skill
```

Export to file:

```bash
python3 cli.py export --format markdown -o tooling.md
python3 cli.py export --format json -o tooling.json
```
