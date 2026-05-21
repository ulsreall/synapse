"""
SYNAPSE Agents Package - 10 specialized analysis agents that form
the multi-agent code review pipeline.

Each agent exposes an `analyze(code, context)` async method returning
a dict with standardized keys: findings, vulnerabilities, metrics,
suggestions, summary, token_usage.
"""

from .security_scanner import SecurityScanner
from .code_quality import CodeQuality
from .performance_analyzer import PerformanceAnalyzer
from .architecture_review import ArchitectureReview
from .test_generator import TestGenerator
from .doc_generator import DocGenerator
from .dependency_audit import DependencyAudit
from .refactor_advisor import RefactorAdvisor
from .type_checker import TypeChecker
from .changelog_generator import ChangelogGenerator

__all__ = [
    "SecurityScanner",
    "CodeQuality",
    "PerformanceAnalyzer",
    "ArchitectureReview",
    "TestGenerator",
    "DocGenerator",
    "DependencyAudit",
    "RefactorAdvisor",
    "TypeChecker",
    "ChangelogGenerator",
]
