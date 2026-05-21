"""
SYNAPSE Pipeline Orchestrator - Routes code through the 10-agent pipeline,
tracks per-agent token usage, aggregates results into an AnalysisResult.
"""

from __future__ import annotations

import asyncio
import importlib
import time
from typing import Dict, List, Optional, Type

from .config import AgentConfig, SynapseConfig
from .models import AgentReport, AgentType, AnalysisResult, TokenUsage
from .token_tracker import TokenTracker

# Map agent config names to their module paths
AGENT_MODULES: Dict[str, str] = {
    "security_scanner":     "agents.security_scanner",
    "code_quality":         "agents.code_quality",
    "performance_analyzer": "agents.performance_analyzer",
    "architecture_review":  "agents.architecture_review",
    "test_generator":       "agents.test_generator",
    "doc_generator":        "agents.doc_generator",
    "dependency_audit":     "agents.dependency_audit",
    "refactor_advisor":     "agents.refactor_advisor",
    "type_checker":         "agents.type_checker",
    "changelog_generator":  "agents.changelog_generator",
}

AGENT_TYPE_MAP: Dict[str, AgentType] = {
    "security_scanner":     AgentType.SECURITY_SCANNER,
    "code_quality":         AgentType.CODE_QUALITY,
    "performance_analyzer": AgentType.PERFORMANCE_ANALYZER,
    "architecture_review":  AgentType.ARCHITECTURE_REVIEW,
    "test_generator":       AgentType.TEST_GENERATOR,
    "doc_generator":        AgentType.DOC_GENERATOR,
    "dependency_audit":     AgentType.DEPENDENCY_AUDIT,
    "refactor_advisor":     AgentType.REFACTOR_ADVISOR,
    "type_checker":         AgentType.TYPE_CHECKER,
    "changelog_generator":  AgentType.CHANGELOG_GENERATOR,
}


class PipelineOrchestrator:
    """
    Core orchestrator that:
      1. Loads enabled agent classes dynamically
      2. Routes code + context through each agent (sequentially or in parallel)
      3. Collects AgentReports with token usage
      4. Aggregates into a final AnalysisResult
    """

    def __init__(self, config: Optional[SynapseConfig] = None):
        self.config = config or SynapseConfig()
        self.token_tracker = TokenTracker(
            daily_limit=self.config.daily_token_limit,
            cost_per_1k_input=self.config.cost_per_1k("input"),
            cost_per_1k_output=self.config.cost_per_1k("output"),
        )
        self._agent_instances: Dict[str, object] = {}

    # ── Agent Loading ──────────────────────────────────────────

    def _load_agent(self, name: str):
        """Dynamically import and instantiate an agent class."""
        if name in self._agent_instances:
            return self._agent_instances[name]

        module_path = AGENT_MODULES.get(name)
        if not module_path:
            raise ValueError(f"Unknown agent: {name}")

        mod = importlib.import_module(module_path)

        # Convention: each module exports a class with PascalCase name
        class_name = "".join(w.capitalize() for w in name.split("_"))
        # e.g. "security_scanner" -> "SecurityScanner"
        agent_cls = getattr(mod, class_name, None)
        if agent_cls is None:
            # Fallback: look for any class ending with "Agent"
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and attr_name.endswith("Agent"):
                    agent_cls = attr
                    break
        if agent_cls is None:
            raise ImportError(f"Cannot find agent class in {module_path}")

        agent_cfg = self.config.get_agent_config(name)
        instance = agent_cls(agent_cfg)
        self._agent_instances[name] = instance
        return instance

    def _load_all_agents(self) -> Dict[str, object]:
        """Load all enabled agents."""
        agents = {}
        for ac in self.config.enabled_agents:
            try:
                agents[ac.name] = self._load_agent(ac.name)
            except (ImportError, ValueError) as exc:
                print(f"[SYNAPSE] Warning: could not load agent '{ac.name}': {exc}")
        return agents

    # ── Pipeline Execution ─────────────────────────────────────

    async def analyze(self, code: str, context: Optional[Dict] = None) -> AnalysisResult:
        """
        Run the full agent pipeline on the given code.

        Args:
            code: source code string to analyze
            context: optional metadata (file_path, language, repo_url, etc.)

        Returns:
            AnalysisResult with all agent reports aggregated
        """
        context = context or {}
        result = AnalysisResult(
            file_path=context.get("file_path"),
            language=context.get("language"),
            status="running",
        )

        agents = self._load_all_agents()

        if self.config.parallel_agents:
            reports = await self._run_parallel(agents, code, context)
        else:
            reports = await self._run_sequential(agents, code, context)

        result.agent_reports = reports
        result.aggregate_findings()

        # Sum up token usage
        total_prompt = sum(r.token_usage.prompt_tokens for r in reports if r.token_usage)
        total_completion = sum(r.token_usage.completion_tokens for r in reports if r.token_usage)
        total_tok = total_prompt + total_completion
        total_cost = sum(r.token_usage.estimated_cost_usd for r in reports if r.token_usage)
        total_time = sum(r.execution_time_ms for r in reports)

        result.total_token_usage = TokenUsage(
            agent_name="pipeline_total",
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_tok,
            estimated_cost_usd=total_cost,
            model=self.config.model,
        )
        result.total_execution_time_ms = total_time
        result.status = "completed"
        return result

    async def _run_sequential(self, agents: Dict[str, object], code: str,
                              context: Dict) -> List[AgentReport]:
        """Run agents one after another in configured order."""
        reports: List[AgentReport] = []
        for ac in self.config.enabled_agents:
            agent = agents.get(ac.name)
            if agent is None:
                continue
            report = await self._run_single_agent(agent, ac, code, context, reports)
            reports.append(report)
        return reports

    async def _run_parallel(self, agents: Dict[str, object], code: str,
                            context: Dict) -> List[AgentReport]:
        """Run all agents concurrently."""
        tasks = []
        ordered_configs = []
        for ac in self.config.enabled_agents:
            agent = agents.get(ac.name)
            if agent is None:
                continue
            tasks.append(self._run_single_agent(agent, ac, code, context, []))
            ordered_configs.append(ac)
        return await asyncio.gather(*tasks)

    async def _run_single_agent(self, agent, ac: AgentConfig, code: str,
                                context: Dict, prior_reports: List[AgentReport]) -> AgentReport:
        """Execute a single agent with timeout and error handling."""
        report = AgentReport(
            agent_name=ac.name,
            agent_type=AGENT_TYPE_MAP.get(ac.name),
            status="running",
        )
        # Pass prior reports in context for agents that depend on upstream
        enriched_ctx = {**context, "prior_reports": [r.to_dict() for r in prior_reports]}

        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                agent.analyze(code, enriched_ctx),
                timeout=ac.timeout_seconds,
            )
            elapsed = (time.perf_counter() - start) * 1000
            report = self._build_report(ac, result, elapsed)
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            report.status = "timeout"
            report.error = f"Agent '{ac.name}' timed out after {ac.timeout_seconds}s"
            report.execution_time_ms = elapsed
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            report.status = "failed"
            report.error = f"{type(exc).__name__}: {exc}"
            report.execution_time_ms = elapsed

        # Record token usage
        if report.token_usage:
            self.token_tracker.record(report.token_usage)

        return report

    def _build_report(self, ac: AgentConfig, result: dict, elapsed_ms: float) -> AgentReport:
        """Convert raw agent output dict into an AgentReport."""
        from .models import Vulnerability, Severity, CodeMetrics

        vulns = []
        for v in result.get("vulnerabilities", []):
            sev = v.get("severity", "medium")
            if isinstance(sev, str):
                sev = Severity(sev) if sev in [e.value for e in Severity] else Severity.MEDIUM
            vulns.append(Vulnerability(
                title=v.get("title", ""),
                description=v.get("description", ""),
                severity=sev,
                cwe_id=v.get("cwe_id"),
                owasp_category=v.get("owasp_category"),
                file_path=v.get("file_path"),
                line_number=v.get("line_number"),
                code_snippet=v.get("code_snippet", ""),
                remediation=v.get("remediation", ""),
                confidence=v.get("confidence", 0.8),
            ))

        metrics = None
        m = result.get("metrics")
        if m and isinstance(m, dict):
            metrics = CodeMetrics(
                cyclomatic_complexity=m.get("cyclomatic_complexity", 0),
                cognitive_complexity=m.get("cognitive_complexity", 0),
                maintainability_index=m.get("maintainability_index", 100),
                lines_of_code=m.get("lines_of_code", 0),
                blank_lines=m.get("blank_lines", 0),
                comment_lines=m.get("comment_lines", 0),
                comment_ratio=m.get("comment_ratio", 0),
                function_count=m.get("function_count", 0),
                class_count=m.get("class_count", 0),
                max_function_length=m.get("max_function_length", 0),
                avg_function_length=m.get("avg_function_length", 0),
                max_nesting_depth=m.get("max_nesting_depth", 0),
                duplicate_line_count=m.get("duplicate_line_count", 0),
                code_smells=m.get("code_smells", []),
            )

        tok = result.get("token_usage", {})
        token_usage = TokenUsage(
            agent_name=ac.name,
            prompt_tokens=tok.get("prompt_tokens", 0),
            completion_tokens=tok.get("completion_tokens", 0),
            total_tokens=tok.get("total_tokens", 0),
            model=self.config.model,
        )

        return AgentReport(
            agent_name=ac.name,
            agent_type=AGENT_TYPE_MAP.get(ac.name),
            status="completed",
            findings=result.get("findings", []),
            vulnerabilities=vulns,
            metrics=metrics,
            suggestions=result.get("suggestions", []),
            summary=result.get("summary", ""),
            token_usage=token_usage,
            execution_time_ms=elapsed_ms,
        )

    # ── Convenience ────────────────────────────────────────────

    def get_token_summary(self) -> Dict:
        return self.token_tracker.total_stats()

    def get_agent_breakdown(self) -> Dict:
        return self.token_tracker.agent_summary()
