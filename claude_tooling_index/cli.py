"""CLI entry point for tooling-index"""

import click
from pathlib import Path
from claude_tooling_index.scanner import ToolingScanner


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Claude Code Tooling Index - Catalog and analyze your Claude setup"""
    pass


@cli.command()
@click.option("--parallel/--sequential", default=True, help="Run scanners in parallel")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--no-db", is_flag=True, help="Skip database update")
def scan(parallel, verbose, no_db):
    """Scan ~/.claude directory and display results"""
    try:
        scanner = ToolingScanner()
        click.echo("🔍 Scanning ~/.claude directory...")

        result = scanner.scan_all(parallel=parallel)

        # Update database
        if not no_db:
            from claude_tooling_index.analytics import AnalyticsTracker
            click.echo("💾 Updating database...")
            tracker = AnalyticsTracker()
            tracker.update_components(result)
            tracker.close()

        click.echo(f"\n✅ Scan complete!")
        click.echo(f"   Total components: {result.total_count}")
        click.echo(f"   Skills: {len(result.skills)}")
        click.echo(f"   Plugins: {len(result.plugins)}")
        click.echo(f"   Commands: {len(result.commands)}")
        click.echo(f"   Hooks: {len(result.hooks)}")
        click.echo(f"   MCPs: {len(result.mcps)}")
        click.echo(f"   Binaries: {len(result.binaries)}")

        if result.errors:
            click.echo(f"\n⚠️  Errors encountered:")
            for error in result.errors:
                click.echo(f"   - {error}")

        if verbose:
            click.echo(f"\n📋 Component Details:")
            click.echo(f"\nSkills ({len(result.skills)}):")
            for skill in result.skills:
                click.echo(f"  - {skill.name} [{skill.status}] ({skill.file_count} files, {skill.total_lines} lines)")

            click.echo(f"\nPlugins ({len(result.plugins)}):")
            for plugin in result.plugins:
                click.echo(f"  - {plugin.name} v{plugin.version} from {plugin.marketplace}")

            click.echo(f"\nCommands ({len(result.commands)}):")
            for command in result.commands:
                click.echo(f"  - /{command.name}: {command.description}")

            click.echo(f"\nHooks ({len(result.hooks)}):")
            for hook in result.hooks:
                click.echo(f"  - {hook.name} ({hook.language})")

            click.echo(f"\nMCPs ({len(result.mcps)}):")
            for mcp in result.mcps:
                click.echo(f"  - {mcp.name}: {mcp.command}")

            click.echo(f"\nBinaries ({len(result.binaries)}):")
            for binary in result.binaries:
                click.echo(f"  - {binary.name} ({binary.language})")

    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--days", default=30, help="Number of days to analyze")
def stats(days):
    """Show usage analytics and statistics"""
    try:
        from claude_tooling_index.analytics import AnalyticsTracker

        tracker = AnalyticsTracker()
        stats = tracker.get_usage_stats(days=days)

        click.echo(f"📊 Usage Statistics (last {days} days)")
        click.echo(f"\n{'='*60}")

        click.echo(f"\n📈 Total Invocations: {stats['total_invocations']}")

        if stats['most_used']:
            click.echo(f"\n🔥 Most Used Components:")
            for i, component in enumerate(stats['most_used'], 1):
                click.echo(f"  {i}. {component['name']} ({component['type']}) - {component['count']} times")
        else:
            click.echo(f"\n🔥 Most Used Components: No usage data yet")

        if stats['recent_installs']:
            click.echo(f"\n📦 Recent Installations:")
            for install in stats['recent_installs']:
                version = f"v{install['version']}" if install['version'] else "unknown version"
                click.echo(f"  - {install['name']} ({install['type']}) - {version} at {install['installed_at']}")
        else:
            click.echo(f"\n📦 Recent Installations: No recent installations")

        if stats['performance_avg']:
            click.echo(f"\n⚡ Performance (avg execution time):")
            for component, avg_ms in sorted(stats['performance_avg'].items(), key=lambda x: x[1], reverse=True):
                click.echo(f"  - {component}: {avg_ms:.1f}ms")
        else:
            click.echo(f"\n⚡ Performance: No performance data yet")

        tracker.close()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--type", help="Filter by component type")
@click.option("--origin", help="Filter by origin")
@click.option("--status", help="Filter by status")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list(type, origin, status, output_json):
    """List all components from database"""
    try:
        from claude_tooling_index.analytics import AnalyticsTracker
        import json

        tracker = AnalyticsTracker()
        components = tracker.get_components(type=type, origin=origin, status=status)

        if output_json:
            click.echo(json.dumps(components, indent=2, default=str))
        else:
            click.echo(f"📋 Components ({len(components)} found)")
            click.echo(f"\n{'Name':<30} {'Type':<10} {'Origin':<12} {'Status':<10}")
            click.echo("="*65)
            for component in components:
                name = component['name'][:28]
                click.echo(f"{name:<30} {component['type']:<10} {component['origin']:<12} {component['status']:<10}")

        tracker.close()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("query")
@click.option("--type", help="Filter by component type")
def search(query, type):
    """Search components by name or description"""
    try:
        from claude_tooling_index.analytics import AnalyticsTracker

        tracker = AnalyticsTracker()
        results = tracker.search_components(query)

        # Filter by type if specified
        if type:
            results = [r for r in results if r.get("type") == type]

        if not results:
            click.echo(f"🔍 No components found matching '{query}'")
        else:
            click.echo(f"🔍 Found {len(results)} components matching '{query}'")
            click.echo(f"\n{'Name':<30} {'Type':<10} {'Origin':<12} {'Status':<10}")
            click.echo("="*65)
            for component in results:
                name = component['name'][:28]
                click.echo(f"{name:<30} {component['type']:<10} {component['origin']:<12} {component['status']:<10}")

        tracker.close()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def tui():
    """Launch interactive TUI dashboard"""
    try:
        from claude_tooling_index.tui import ToolingIndexTUI

        app = ToolingIndexTUI()
        app.run()

    except ImportError as e:
        click.echo("❌ TUI requires 'textual' package. Install with: pip install textual", err=True)
        click.echo(f"   Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Error launching TUI: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--format", "output_format", type=click.Choice(["json", "markdown"]), default="markdown", help="Export format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--include-disabled/--no-disabled", default=True, help="Include disabled components")
def export(output_format, output, include_disabled):
    """Export tooling index to JSON or Markdown"""
    try:
        from claude_tooling_index.scanner import ToolingScanner
        from claude_tooling_index.exporters import JSONExporter, MarkdownExporter
        from pathlib import Path

        click.echo(f"📦 Exporting to {output_format}...")

        scanner = ToolingScanner()
        result = scanner.scan_all()

        if output_format == "json":
            exporter = JSONExporter()
            content = exporter.export_scan_result(result)
            default_filename = "tooling-index.json"
        else:
            exporter = MarkdownExporter(include_disabled=include_disabled)
            content = exporter.export_scan_result(result)
            default_filename = "tooling-index.md"

        if output:
            output_path = Path(output)
        else:
            output_path = Path.cwd() / default_filename

        with open(output_path, "w") as f:
            f.write(content)

        click.echo(f"✅ Exported to {output_path}")
        click.echo(f"   {result.total_count} components")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
