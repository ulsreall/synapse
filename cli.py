"""SYNAPSE CLI — Multi-Agent Code Review & Analysis Platform.

Usage:
    synapse analyze <path> [--agents AGENTS] [--recursive] [--output FORMAT]
    synapse dashboard [--port PORT] [--host HOST]
    synapse agents [--verbose]
    synapse stats [--days DAYS] [--agent AGENT]
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import click

# Agent registry — maps short names to module paths
AGENT_REGISTRY = {
    "security": ("synapse.agents.security_scanner", "SecurityScanner", 18_000),
    "quality": ("synapse.agents.code_quality", "CodeQuality", 15_000),
    "performance": ("synapse.agents.performance_analyzer", "PerformanceAnalyzer", 16_000),
    "architecture": ("synapse.agents.architecture_review", "ArchitectureReview", 20_000),
    "testgen": ("synapse.agents.test_generator", "TestGenerator", 22_000),
    "docs": ("synapse.agents.doc_generator", "DocGenerator", 18_000),
    "dependencies": ("synapse.agents.dependency_audit", "DependencyAudit", 12_000),
    "refactor": ("synapse.agents.refactor_advisor", "RefactorAdvisor", 16_000),
    "types": ("synapse.agents.type_checker", "TypeChecker", 14_000),
    "changelog": ("synapse.agents.changelog_generator", "ChangelogGenerator", 10_000),
}

TOTAL_PIPELINE_TOKENS = sum(v[2] for v in AGENT_REGISTRY.values())


def _load_agent(name: str, config: dict):
    """Dynamically load an agent class by registry name."""
    import importlib
    module_path, class_name, _ = AGENT_REGISTRY[name]
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(config)


def _collect_files(path: str, recursive: bool = False) -> list[Path]:
    """Collect source files from a path."""
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        pattern = "**/*" if recursive else "*"
        return sorted(
            f for f in p.glob(pattern)
            if f.is_file() and f.suffix in {".py", ".js", ".ts", ".java", ".go", ".rs"}
        )
    click.echo(f"Error: {path} is not a valid file or directory.", err=True)
    sys.exit(1)


async def _run_pipeline(files: list[Path], agent_names: list[str], config: dict) -> dict:
    """Run the analysis pipeline on a list of files."""
    all_results = {}
    total_tokens = 0

    for filepath in files:
        click.echo(f"\n{'='*60}")
        click.echo(f"  Analyzing: {filepath}")
        click.echo(f"{'='*60}")

        code = filepath.read_text(encoding="utf-8", errors="replace")
        context = {"file": str(filepath), "timestamp": time.time()}
        file_results = {}

        for agent_name in agent_names:
            agent = _load_agent(agent_name, config)
            label = agent_name.upper().ljust(14)
            click.echo(f"  ▶ {label} (~{agent.token_estimate:,} tokens)...", nl=False)

            try:
                result = await agent.analyze(code, context)
                findings_count = len(result.get("findings", []))
                tokens = result.get("tokens_used", agent.token_estimate)
                total_tokens += tokens
                click.echo(f" ✓ {findings_count} findings, {tokens:,} tokens")
                file_results[agent_name] = result
            except Exception as exc:
                click.echo(f" ✗ Error: {exc}")
                file_results[agent_name] = {"error": str(exc), "tokens_used": 0}

        all_results[str(filepath)] = file_results

    click.echo(f"\n{'='*60}")
    click.echo(f"  Pipeline complete. Total tokens consumed: {total_tokens:,}")
    click.echo(f"{'='*60}\n")

    return {"results": all_results, "total_tokens": total_tokens}


@click.group()
@click.version_option(version="0.1.0", prog_name="synapse")
def cli():
    """SYNAPSE — Multi-Agent Code Review & Analysis Platform."""
    pass


@cli.command()
@click.argument("path")
@click.option("--agents", "-a", default="all", help="Comma-separated agent names, or 'all'.")
@click.option("--recursive", "-r", is_flag=True, help="Recursively scan directories.")
@click.option("--output", "-o", default="text", type=click.Choice(["text", "json", "markdown"]), help="Output format.")
def analyze(path: str, agents: str, recursive: bool, output: str):
    """Analyze a file or directory through the SYNAPSE pipeline."""
    config = {
        "provider": os.environ.get("SYNAPSE_PROVIDER", "openai"),
        "api_key": os.environ.get("SYNAPSE_API_KEY", ""),
        "model": os.environ.get("SYNAPSE_MODEL", "gpt-4o"),
    }

    if agents == "all":
        agent_names = list(AGENT_REGISTRY.keys())
    else:
        agent_names = [a.strip() for a in agents.split(",")]
        invalid = [a for a in agent_names if a not in AGENT_REGISTRY]
        if invalid:
            click.echo(f"Error: Unknown agents: {', '.join(invalid)}", err=True)
            click.echo(f"Available: {', '.join(AGENT_REGISTRY.keys())}", err=True)
            sys.exit(1)

    files = _collect_files(path, recursive)
    if not files:
        click.echo("No source files found.", err=True)
        sys.exit(1)

    click.echo(f"SYNAPSE Pipeline — {len(files)} file(s), {len(agent_names)} agent(s)")
    click.echo(f"Estimated tokens per file: ~{sum(AGENT_REGISTRY[a][2] for a in agent_names):,}")

    results = asyncio.run(_run_pipeline(files, agent_names, config))

    if output == "json":
        import json
        click.echo(json.dumps(results, indent=2, default=str))


@cli.command()
@click.option("--port", "-p", default=8080, help="Port for the dashboard web server.")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to.")
def dashboard(port: int, host: str):
    """Launch the SYNAPSE web dashboard."""
    click.echo(f"Starting SYNAPSE dashboard on http://{host}:{port}")
    try:
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        click.echo("Dashboard running. Press Ctrl+C to stop.")
        server = HTTPServer((host, port), SimpleHTTPRequestHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nDashboard stopped.")
    except ImportError:
        click.echo("Dashboard dependencies not installed. Install with: pip install synapse-ai[dashboard]")


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed agent descriptions.")
def agents(verbose: bool):
    """List all available SYNAPSE analysis agents."""
    click.echo("SYNAPSE Agents")
    click.echo("=" * 55)

    descriptions = {
        "security": "OWASP Top 10, injection, XSS, SSRF detection",
        "quality": "Complexity, maintainability, code smell analysis",
        "performance": "Bottleneck, N+1 query, memory leak detection",
        "architecture": "SOLID principles, coupling, cohesion, design patterns",
        "testgen": "Unit test, integration test, edge case generation",
        "docs": "API documentation, README, inline comment generation",
        "dependencies": "CVE scanning, license compliance, outdated packages",
        "refactor": "DRY violations, extract method, simplify conditionals",
        "types": "Type inference, null safety, generic issues, annotations",
        "changelog": "Semantic versioning, breaking changes, migration guides",
    }

    total = 0
    for name, (_, class_name, token_est) in AGENT_REGISTRY.items():
        total += token_est
        desc = descriptions.get(name, "")
        click.echo(f"  {name:<16} {token_est:>6,} tokens   {desc if verbose else ''}")

    click.echo("=" * 55)
    click.echo(f"  {'TOTAL':<16} {total:>6,} tokens   (per file, all agents)")


@cli.command()
@click.option("--days", "-d", default=30, help="Number of days to report on.")
@click.option("--agent", "-a", default=None, help="Show stats for a specific agent.")
def stats(days: int, agent: str):
    """Show token consumption statistics."""
    click.echo("SYNAPSE Token Consumption Statistics")
    click.echo("=" * 50)

    if agent and agent in AGENT_REGISTRY:
        _, cls, tokens = AGENT_REGISTRY[agent]
        click.echo(f"  Agent:    {agent}")
        click.echo(f"  Class:    {cls}")
        click.echo(f"  Per file: {tokens:,} tokens")
        click.echo(f"  Per 100:  {tokens * 100:,} tokens")
        click.echo(f"  Per 1K:   {tokens * 1000:,} tokens")
    else:
        click.echo(f"  Pipeline total per file:  {TOTAL_PIPELINE_TOKENS:,} tokens")
        click.echo(f"  Pipeline total per 100:   {TOTAL_PIPELINE_TOKENS * 100:,} tokens")
        click.echo(f"  Pipeline total per 1K:    {TOTAL_PIPELINE_TOKENS * 1000:,} tokens")
        click.echo(f"  Daily estimate (1K files): {TOTAL_PIPELINE_TOKENS * 1000:,} tokens")
        click.echo()
        click.echo("  Per-agent breakdown:")
        for name, (_, _, tokens) in AGENT_REGISTRY.items():
            pct = (tokens / TOTAL_PIPELINE_TOKENS) * 100
            bar = "█" * int(pct / 2)
            click.echo(f"    {name:<16} {tokens:>6,}  {pct:5.1f}%  {bar}")

    click.echo("=" * 50)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
