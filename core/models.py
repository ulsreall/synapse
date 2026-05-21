"""
SYNAPSE Data Models - Typed dataclasses for analysis results, agent reports,
code metrics, vulnerabilities, and token usage tracking.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AgentType(Enum):
    SECURITY_SCANNER = "security_scanner"
    CODE_QUALITY = "code_quality"
    PERFORMANCE_ANALYZER = "performance_analyzer"
    ARCHITECTURE_REVIEW = "architecture_review"
    TEST_GENERATOR = "test_generator"
    DOC_GENERATOR = "doc_generator"
    DEPENDENCY_AUDIT = "dependency_audit"
    REFACTOR_ADVISOR = "refactor_advisor"
    TYPE_CHECKER = "type_checker"
    CHANGELOG_GENERATOR = "changelog_generator"


@dataclass
class Vulnerability:
    """A single security vulnerability finding."""
    vuln_id: str = field(default_factory=lambda: f"VULN-{uuid.uuid4().hex[:8].upper()}")
    title: str = ""
    description: str = ""
    severity: Severity = Severity.MEDIUM
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: str = ""
    remediation: str = ""
    confidence: float = 0.8  # 0.0 - 1.0

    def to_dict(self) -> dict:
        return {
            "vuln_id": self.vuln_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "cwe_id": self.cwe_id,
            "owasp_category": self.owasp_category,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "remediation": self.remediation,
            "confidence": self.confidence,
        }


@dataclass
class CodeMetrics:
    """Quantitative code quality metrics."""
    cyclomatic_complexity: float = 0.0
    cognitive_complexity: float = 0.0
    maintainability_index: float = 100.0
    lines_of_code: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    comment_ratio: float = 0.0
    function_count: int = 0
    class_count: int = 0
    max_function_length: int = 0
    avg_function_length: float = 0.0
    max_nesting_depth: int = 0
    duplicate_line_count: int = 0
    code_smells: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "cognitive_complexity": self.cognitive_complexity,
            "maintainability_index": self.maintainability_index,
            "lines_of_code": self.lines_of_code,
            "blank_lines": self.blank_lines,
            "comment_lines": self.comment_lines,
            "comment_ratio": round(self.comment_ratio, 3),
            "function_count": self.function_count,
            "class_count": self.class_count,
            "max_function_length": self.max_function_length,
            "avg_function_length": round(self.avg_function_length, 1),
            "max_nesting_depth": self.max_nesting_depth,
            "duplicate_line_count": self.duplicate_line_count,
            "code_smells": self.code_smells,
        }


@dataclass
class TokenUsage:
    """Token consumption for a single operation."""
    agent_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "model": self.model,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentReport:
    """Result from a single agent analysis."""
    agent_name: str = ""
    agent_type: Optional[AgentType] = None
    status: str = "pending"  # pending, running, completed, failed
    findings: List[Dict[str, Any]] = field(default_factory=list)
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    metrics: Optional[CodeMetrics] = None
    suggestions: List[str] = field(default_factory=list)
    summary: str = ""
    token_usage: Optional[TokenUsage] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(
            1 for f in self.findings
            if f.get("severity") in ("critical", Severity.CRITICAL)
        )

    def to_dict(self) -> dict:
        result = {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type.value if self.agent_type else None,
            "status": self.status,
            "finding_count": self.finding_count,
            "critical_count": self.critical_count,
            "findings": self.findings,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "suggestions": self.suggestions,
            "summary": self.summary,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "error": self.error,
            "timestamp": self.timestamp,
        }
        if self.metrics:
            result["metrics"] = self.metrics.to_dict()
        if self.token_usage:
            result["token_usage"] = self.token_usage.to_dict()
        return result


@dataclass
class AnalysisResult:
    """Aggregate result from the full agent pipeline."""
    analysis_id: str = field(default_factory=lambda: f"AN-{uuid.uuid4().hex[:12].upper()}")
    status: str = "pending"
    file_path: Optional[str] = None
    language: Optional[str] = None
    agent_reports: List[AgentReport] = field(default_factory=list)
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    overall_score: float = 100.0  # 0-100 health score
    total_token_usage: Optional[TokenUsage] = None
    total_execution_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def aggregate_findings(self) -> None:
        """Recompute aggregated finding counts from agent reports."""
        self.total_findings = 0
        self.critical_findings = 0
        self.high_findings = 0
        self.medium_findings = 0
        self.low_findings = 0
        for report in self.agent_reports:
            for f in report.findings:
                sev = f.get("severity", "info")
                if isinstance(sev, Severity):
                    sev = sev.value
                sev = str(sev).lower()
                self.total_findings += 1
                if sev == "critical":
                    self.critical_findings += 1
                elif sev == "high":
                    self.high_findings += 1
                elif sev == "medium":
                    self.medium_findings += 1
                elif sev == "low":
                    self.low_findings += 1
        # Compute overall score: start at 100, deduct per finding
        self.overall_score = max(0.0, 100.0
            - self.critical_findings * 15
            - self.high_findings * 8
            - self.medium_findings * 3
            - self.low_findings * 1
        )

    def to_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "status": self.status,
            "file_path": self.file_path,
            "language": self.language,
            "total_findings": self.total_findings,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "medium_findings": self.medium_findings,
            "low_findings": self.low_findings,
            "overall_score": round(self.overall_score, 1),
            "total_execution_time_ms": round(self.total_execution_time_ms, 2),
            "agent_reports": [r.to_dict() for r in self.agent_reports],
            "total_token_usage": self.total_token_usage.to_dict() if self.total_token_usage else None,
            "timestamp": self.timestamp,
        }
