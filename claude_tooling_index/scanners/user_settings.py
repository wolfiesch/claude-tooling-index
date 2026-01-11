"""User settings scanner - extracts metadata from `~/.claude.json`."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import ProjectMetric, SkillUsage, UserSettingsMetadata


class UserSettingsScanner:
    """Scan `~/.claude.json` for user settings and usage metrics."""

    def __init__(self, claude_json_path: Optional[Path] = None):
        self.claude_json_path = claude_json_path or (Path.home() / ".claude.json")

    def scan(self) -> Optional[UserSettingsMetadata]:
        """Scan `~/.claude.json` and extract user settings metadata."""
        if not self.claude_json_path.exists():
            return None

        try:
            with open(self.claude_json_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        return self._parse_settings(data)

    def _parse_settings(self, data: dict) -> UserSettingsMetadata:
        """Parse the `~/.claude.json` data into `UserSettingsMetadata`."""
        result = UserSettingsMetadata()

        # Basic activity metrics
        result.total_startups = data.get("numStartups", 0)
        result.memory_usage_count = data.get("memoryUsageCount", 0)
        result.prompt_queue_use_count = data.get("promptQueueUseCount", 0)

        # Parse first startup date
        first_start = data.get("firstStartTime")
        if first_start:
            try:
                result.first_startup_date = datetime.fromisoformat(
                    first_start.replace("Z", "+00:00")
                )
                result.account_age_days = (
                    datetime.now(result.first_startup_date.tzinfo)
                    - result.first_startup_date
                ).days
                if result.account_age_days > 0:
                    result.sessions_per_day = (
                        result.total_startups / result.account_age_days
                    )
            except (ValueError, TypeError):
                pass

        # Parse skill usage
        skill_usage_raw = data.get("skillUsage", {})
        for skill_name, usage_data in skill_usage_raw.items():
            if isinstance(usage_data, dict):
                usage_count = usage_data.get("usageCount", 0)
                last_used_ts = usage_data.get("lastUsedAt")
                last_used = None
                if last_used_ts:
                    try:
                        last_used = datetime.fromtimestamp(last_used_ts / 1000)
                    except (ValueError, TypeError, OSError):
                        pass

                result.skill_usage[skill_name] = SkillUsage(
                    name=skill_name,
                    usage_count=usage_count,
                    last_used_at=last_used,
                )

        # Sort top skills by usage count
        sorted_skills = sorted(
            result.skill_usage.values(),
            key=lambda s: s.usage_count,
            reverse=True,
        )
        result.top_skills = sorted_skills[:10]

        # Parse tip adoption
        tips_history = data.get("tipsHistory", {})
        for tip_id, count in tips_history.items():
            if isinstance(count, int):
                result.tip_adoption[tip_id] = count

        # Identify high adoption features (>90% of startups)
        threshold = result.total_startups * 0.9 if result.total_startups > 0 else 0
        result.high_adoption_features = [
            tip
            for tip, count in result.tip_adoption.items()
            if count >= threshold and threshold > 0
        ]

        # Parse project metrics
        projects_raw = data.get("projects", {})
        for project_path, project_data in projects_raw.items():
            if not isinstance(project_data, dict):
                continue

            metric = ProjectMetric(
                path=project_path,
                last_session_cost=project_data.get("lastCost"),
                last_session_duration_ms=project_data.get("lastDuration", 0),
                lines_added=project_data.get("lastLinesAdded", 0),
                lines_removed=project_data.get("lastLinesRemoved", 0),
                input_tokens=project_data.get("lastTotalInputTokens", 0),
                output_tokens=project_data.get("lastTotalOutputTokens", 0),
                cache_read_tokens=project_data.get("lastTotalCacheReadInputTokens", 0),
                api_latency_ms=project_data.get("lastAPIDuration", 0),
                onboarding_seen_count=project_data.get("projectOnboardingSeenCount", 0),
                has_trust_accepted=project_data.get("hasTrustDialogAccepted", False),
            )
            result.project_metrics[project_path] = metric

        result.total_projects = len(result.project_metrics)

        # Parse GitHub repos
        github_repos = data.get("githubRepoPaths", {})
        for repo_name, paths in github_repos.items():
            if isinstance(paths, list):
                result.github_repos[repo_name] = paths

        result.total_github_repos = len(result.github_repos)

        return result
