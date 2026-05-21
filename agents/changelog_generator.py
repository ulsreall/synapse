"""SYNAPSE Changelog Generator Agent.

Generates semantic versioning changelogs, identifies breaking changes,
and produces migration guides from code diffs and commit history.

Token consumption: ~10K tokens per analysis.
"""

import ast
import re
from collections import defaultdict
from typing import Any


class ChangelogGenerator:
    """Changelog & release notes agent. Token consumption: ~10K tokens per analysis."""

    # Patterns that indicate breaking changes
    BREAKING_PATTERNS = [
        r"def\s+(\w+)\(.*\)\s*->\s*(?!None)",  # Return type changed
        r"raise\s+",                               # New exceptions
        r"del\s+attr",                             # Removed attributes
    ]

    # Conventional commit types
    COMMIT_TYPES = {
        "feat": "Features",
        "fix": "Bug Fixes",
        "docs": "Documentation",
        "style": "Style",
        "refactor": "Refactoring",
        "perf": "Performance",
        "test": "Tests",
        "chore": "Maintenance",
        "ci": "CI/CD",
        "build": "Build",
        "revert": "Reverts",
    }

    def __init__(self, config: dict):
        self.config = config
        self.token_estimate = 10_000

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code to generate changelog entries and identify changes.

        Args:
            code: Source code (or diff) to analyze.
            context: Additional context including git history, version info, etc.

        Returns:
            dict with findings, metrics, and token usage.
        """
        findings = []
        metrics = {}

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            # Might be a diff, try parsing as diff
            return await self._analyze_diff(code, context)

        # --- Detect New Public API Surface ---
        findings.extend(self._detect_new_api(tree))

        # --- Detect Breaking Changes ---
        findings.extend(self._detect_breaking_changes(tree))

        # --- Detect Deprecations ---
        findings.extend(self._detect_deprecations(tree))

        # --- Generate Changelog Sections ---
        changelog = self._generate_changelog(tree, findings, context)

        # --- Migration Guide ---
        migration = self._generate_migration_guide(findings)

        metrics = {
            "total_findings": len(findings),
            "breaking_changes": len([f for f in findings if f.get("breaking")]),
            "new_features": len([f for f in findings if f["type"] == "new_api"]),
            "deprecations": len([f for f in findings if f["type"] == "deprecation"]),
            "suggested_version_bump": self._suggest_version_bump(findings),
            "changelog": changelog,
            "migration_guide": migration,
        }

        return {
            "findings": findings,
            "metrics": metrics,
            "tokens_used": self.token_estimate,
        }

    async def _analyze_diff(self, diff: str, context: dict) -> dict:
        """Analyze a git diff for changelog generation."""
        findings = []
        added_lines = []
        removed_lines = []

        for line in diff.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:])

        # Check for removed public functions/classes
        for line in removed_lines:
            match = re.match(r"def\s+(\w+)\(", line)
            if match and not match.group(1).startswith("_"):
                findings.append({
                    "type": "breaking_change",
                    "severity": "critical",
                    "message": f"Public function '{match.group(1)}' was removed.",
                    "breaking": True,
                    "suggestion": "Add deprecation notice before removing. Update major version.",
                })

            match = re.match(r"class\s+(\w+)", line)
            if match:
                findings.append({
                    "type": "breaking_change",
                    "severity": "critical",
                    "message": f"Class '{match.group(1)}' was removed.",
                    "breaking": True,
                    "suggestion": "Provide migration path and deprecation period.",
                })

        # Check for new public functions/classes
        for line in added_lines:
            match = re.match(r"def\s+(\w+)\(", line)
            if match and not match.group(1).startswith("_"):
                findings.append({
                    "type": "new_api",
                    "severity": "info",
                    "message": f"New public function '{match.group(1)}' added.",
                    "breaking": False,
                })

        changelog = self._generate_changelog_from_diff(findings)
        metrics = {
            "total_findings": len(findings),
            "breaking_changes": len([f for f in findings if f.get("breaking")]),
            "suggested_version_bump": self._suggest_version_bump(findings),
            "changelog": changelog,
        }

        return {
            "findings": findings,
            "metrics": metrics,
            "tokens_used": self.token_estimate,
        }

    def _detect_new_api(self, tree: ast.AST) -> list[dict]:
        """Detect new public API surface (functions, classes, methods)."""
        findings = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                public_methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not n.name.startswith("_")
                ]
                findings.append({
                    "type": "new_api",
                    "severity": "info",
                    "line": node.lineno,
                    "message": f"Public class '{node.name}' with {len(public_methods)} public methods.",
                    "breaking": False,
                    "api_name": node.name,
                    "api_type": "class",
                })

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                findings.append({
                    "type": "new_api",
                    "severity": "info",
                    "line": node.lineno,
                    "message": f"Public function '{node.name}'.",
                    "breaking": False,
                    "api_name": node.name,
                    "api_type": "function",
                })

        return findings

    def _detect_breaking_changes(self, tree: ast.AST) -> list[dict]:
        """Detect potential breaking changes in the code."""
        findings = []

        for node in ast.walk(tree):
            # DeprecationWarning raises
            if isinstance(node, ast.Raise):
                if isinstance(node.exc, ast.Call):
                    func = node.exc.func
                    if isinstance(func, ast.Name) and func.id in ("DeprecationWarning", "PendingDeprecationWarning"):
                        findings.append({
                            "type": "deprecation_warning",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": "DeprecationWarning raised — indicates planned breaking change.",
                            "breaking": True,
                        })

            # @deprecated decorator usage
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    dec_name = ""
                    if isinstance(decorator, ast.Name):
                        dec_name = decorator.id
                    elif isinstance(decorator, ast.Attribute):
                        dec_name = decorator.attr
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            dec_name = decorator.func.id
                        elif isinstance(decorator.func, ast.Attribute):
                            dec_name = decorator.func.attr

                    if "deprecated" in dec_name.lower():
                        findings.append({
                            "type": "deprecation",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"Method '{node.name}' is marked as deprecated.",
                            "breaking": False,
                            "api_name": node.name,
                        })

        return findings

    def _detect_deprecations(self, tree: ast.AST) -> list[dict]:
        """Detect deprecated code patterns and TODO/FIXME markers."""
        findings = []

        for node in ast.walk(tree):
            # Check string constants for deprecation notices
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value.lower()
                if "deprecated" in text:
                    findings.append({
                        "type": "deprecation",
                        "severity": "info",
                        "line": getattr(node, "lineno", 0),
                        "message": f"Deprecation notice found: '{node.value[:80]}...'" if len(node.value) > 80 else f"Deprecation notice: '{node.value}'",
                        "breaking": False,
                    })

        return findings

    def _generate_changelog(self, tree: ast.AST, findings: list[dict], context: dict) -> str:
        """Generate a changelog entry from analysis results."""
        version = context.get("version", "Unreleased")
        sections = defaultdict(list)

        for finding in findings:
            if finding["type"] == "new_api":
                sections["Features"].append(f"- Added `{finding.get('api_name', 'API')}`")
            elif finding["type"] == "breaking_change":
                sections["Breaking Changes"].append(f"- ⚠️ {finding['message']}")
            elif finding["type"] == "deprecation":
                sections["Deprecations"].append(f"- {finding['message']}")
            elif finding["type"] == "deprecation_warning":
                sections["Deprecations"].append(f"- {finding['message']}")

        lines = [f"## [{version}]", ""]

        # Order: Breaking first, then features, then deprecations
        order = ["Breaking Changes", "Features", "Deprecations"]
        for section_name in order:
            if section_name in sections:
                lines.append(f"### {section_name}")
                lines.extend(sections[section_name])
                lines.append("")

        # Any remaining sections
        for section_name, items in sections.items():
            if section_name not in order:
                lines.append(f"### {section_name}")
                lines.extend(items)
                lines.append("")

        return "\n".join(lines)

    def _generate_changelog_from_diff(self, findings: list[dict]) -> str:
        """Generate changelog from diff analysis."""
        sections = defaultdict(list)

        for finding in findings:
            if finding["type"] == "new_api":
                sections["Features"].append(f"- Added `{finding.get('api_name', 'new API')}`")
            elif finding["type"] == "breaking_change":
                sections["Breaking Changes"].append(f"- ⚠️ {finding['message']}")

        lines = ["## [Unreleased]", ""]
        for section, items in sections.items():
            lines.append(f"### {section}")
            lines.extend(items)
            lines.append("")

        return "\n".join(lines) if len(lines) > 2 else "## [Unreleased]\n\nNo notable changes."

    def _generate_migration_guide(self, findings: list[dict]) -> str:
        """Generate a migration guide for breaking changes."""
        breaking = [f for f in findings if f.get("breaking")]
        if not breaking:
            return ""

        lines = ["### Migration Guide", ""]
        for i, finding in enumerate(breaking, 1):
            lines.append(f"{i}. **{finding['message']}**")
            if finding.get("suggestion"):
                lines.append(f"   - {finding['suggestion']}")
            lines.append("")

        return "\n".join(lines)

    def _suggest_version_bump(self, findings: list[dict]) -> str:
        """Suggest semantic version bump based on findings."""
        has_breaking = any(f.get("breaking") for f in findings)
        has_new_api = any(f["type"] == "new_api" for f in findings)

        if has_breaking:
            return "major"
        elif has_new_api:
            return "minor"
        else:
            return "patch"
