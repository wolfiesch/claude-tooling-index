from __future__ import annotations

from pathlib import Path

from claude_tooling_index.scanners.skills import SkillScanner


def test_skill_scanner_extracts_rich_metadata_and_links_graph(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    skill_a = skills_dir / "skill-a"
    skill_a.mkdir()
    (skill_a / "SKILL.md").write_text(
        """---
name: skill-a
description: A
---

## Inputs
- recipient_email: Who to email (required)
- api_key: From ${API_KEY}

## Outputs
- sent_email: Confirmation

## Safety
- Redact ${API_KEY}

## When to use
- Use when you need to email someone.

## Trigger rules
- Run daily at 9:00

## Example
```bash
pip install -U tooling-index
export API_KEY=secret
```

```python
run_composio_tool("GMAIL_SEND_EMAIL", {"to": "x"})
```

Depends on $skill-b.
"""
    )

    skill_b = skills_dir / "skill-b"
    skill_b.mkdir()
    (skill_b / "SKILL.md").write_text(
        """---
name: skill-b
description: B
---

## Pitfalls
- Beware rate limits
"""
    )

    scanned = SkillScanner(skills_dir).scan()
    by_name = {s.name: s for s in scanned}

    a = by_name["skill-a"]
    b = by_name["skill-b"]

    assert a.inputs_schema[0]["name"] == "recipient_email"
    assert a.inputs_schema[0]["required"] is True
    assert "API_KEY" in a.required_env_vars
    assert "scheduled" in a.trigger_types
    assert a.risk_level in {"medium", "high"}
    assert "email" in a.side_effects
    assert "email" in a.capability_tags

    assert "Beware rate limits" in b.gotchas
    assert "skill-b" in a.depends_on_skills
    assert "skill-a" in b.used_by_skills
