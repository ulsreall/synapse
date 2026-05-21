"""SYNAPSE Refactor Advisor Agent.

Analyzes code for refactoring opportunities including DRY violations,
extract method candidates, conditional simplification, and naming improvements.

Token consumption: ~16K tokens per analysis.
"""

import ast
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any


class RefactorAdvisor:
    """Refactoring suggestions agent. Token consumption: ~16K tokens per analysis."""

    def __init__(self, config: dict):
        self.config = config
        self.token_estimate = 16_000

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code for refactoring opportunities.

        Args:
            code: Source code to analyze.
            context: Additional context (file path, project info, etc.).

        Returns:
            dict with findings, metrics, and token usage.
        """
        findings = []
        metrics = {}

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {
                "findings": [{"type": "syntax_error", "severity": "error", "message": str(exc)}],
                "metrics": {},
                "tokens_used": 500,
            }

        # --- DRY Violation Detection ---
        findings.extend(self._detect_dry_violations(tree, code))

        # --- Extract Method Candidates ---
        findings.extend(self._detect_long_methods(tree))

        # --- Conditional Simplification ---
        findings.extend(self._detect_complex_conditionals(tree))

        # --- Naming Improvements ---
        findings.extend(self._check_naming_conventions(tree))

        # --- Dead Code Detection ---
        findings.extend(self._detect_dead_code(tree))

        # --- Magic Numbers ---
        findings.extend(self._detect_magic_numbers(tree))

        # Compute metrics
        methods = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

        metrics = {
            "total_methods": len(methods),
            "total_classes": len(classes),
            "avg_method_length": self._avg_method_length(methods),
            "max_complexity": max((self._cyclomatic_complexity(m) for m in methods), default=0),
            "dry_violations": len([f for f in findings if f["type"] == "dry_violation"]),
            "extract_method_candidates": len([f for f in findings if f["type"] == "extract_method"]),
            "naming_issues": len([f for f in findings if f["type"] == "naming"]),
            "refactor_score": max(0, 100 - len(findings) * 5),
        }

        return {
            "findings": findings,
            "metrics": metrics,
            "tokens_used": self.token_estimate,
        }

    def _detect_dry_violations(self, tree: ast.AST, code: str) -> list[dict]:
        """Find duplicate or near-duplicate code blocks."""
        findings = []
        methods = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        # Compare method bodies for similarity
        bodies: dict[str, str] = {}
        for method in methods:
            body_lines = ast.get_source_segment(code, method)
            if body_lines:
                bodies[method.name] = body_lines

        checked = set()
        for name1, body1 in bodies.items():
            for name2, body2 in bodies.items():
                if name1 == name2 or (name1, name2) in checked:
                    continue
                checked.add((name1, name2))
                checked.add((name2, name1))

                ratio = SequenceMatcher(None, body1, body2).ratio()
                if ratio > 0.7:
                    findings.append({
                        "type": "dry_violation",
                        "severity": "warning",
                        "message": f"Methods '{name1}' and '{name2}' are {ratio:.0%} similar — consider extracting shared logic.",
                        "suggestion": f"Create a shared helper method for the common logic between '{name1}' and '{name2}'.",
                        "methods": [name1, name2],
                        "similarity": round(ratio, 2),
                    })

        return findings

    def _detect_long_methods(self, tree: ast.AST) -> list[dict]:
        """Find methods that are too long and should be split."""
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
                if length > 30:
                    findings.append({
                        "type": "extract_method",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"Method '{node.name}' is {length} lines long (threshold: 30).",
                        "suggestion": f"Extract logical blocks from '{node.name}' into smaller helper methods.",
                        "method": node.name,
                        "line_count": length,
                    })
                elif length > 20:
                    findings.append({
                        "type": "extract_method",
                        "severity": "info",
                        "line": node.lineno,
                        "message": f"Method '{node.name}' is {length} lines — consider splitting.",
                        "suggestion": f"'{node.name}' is getting long. Look for discrete steps to extract.",
                        "method": node.name,
                        "line_count": length,
                    })

        return findings

    def _detect_complex_conditionals(self, tree: ast.AST) -> list[dict]:
        """Find overly complex conditional expressions."""
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.BoolOp):
                depth = self._bool_depth(node)
                if depth >= 3:
                    findings.append({
                        "type": "simplify_conditional",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"Boolean expression has depth {depth} — consider simplifying.",
                        "suggestion": "Extract complex conditions into well-named boolean variables or helper methods.",
                    })
            if isinstance(node, ast.If):
                nested = sum(1 for _ in ast.walk(node) if isinstance(_, ast.If))
                if nested > 4:
                    findings.append({
                        "type": "simplify_conditional",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"Deeply nested if-statement ({nested} levels) — consider guard clauses or early returns.",
                        "suggestion": "Use early returns to flatten the conditional structure.",
                    })

        return findings

    def _check_naming_conventions(self, tree: ast.AST) -> list[dict]:
        """Check for poor variable and method names."""
        findings = []
        single_char_pattern = re.compile(r"^[a-z]$")

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and single_char_pattern.match(node.id):
                # Allow common loop vars
                if node.id not in ("i", "j", "k", "x", "y", "z", "_"):
                    findings.append({
                        "type": "naming",
                        "severity": "info",
                        "line": getattr(node, "lineno", 0),
                        "message": f"Single-character variable name '{node.id}' — use a descriptive name.",
                        "suggestion": f"Rename '{node.id}' to something meaningful (e.g., based on what it represents).",
                    })

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if len(name) == 1 and name != "_":
                    findings.append({
                        "type": "naming",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"Single-character method name '{name}' — use a descriptive name.",
                        "suggestion": f"Rename '{name}' to describe its purpose.",
                    })
                if name.startswith("_") and not name.startswith("__") and not any(
                    isinstance(p, ast.FunctionDef) for p in ast.walk(tree)
                ):
                    pass  # Skip private method checks for now

        return findings

    def _detect_dead_code(self, tree: ast.AST) -> list[dict]:
        """Detect potentially unused imports and variables."""
        findings = []
        imports = {}
        used_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imports[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = node.lineno
            elif isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        for name, lineno in imports.items():
            if name not in used_names and name != "*":
                findings.append({
                    "type": "dead_code",
                    "severity": "info",
                    "line": lineno,
                    "message": f"Import '{name}' appears to be unused.",
                    "suggestion": f"Remove unused import '{name}' to keep the codebase clean.",
                })

        return findings

    def _detect_magic_numbers(self, tree: ast.AST) -> list[dict]:
        """Find magic numbers that should be named constants."""
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if abs(node.value) > 1 and node.value not in (0, 1, 2, 10, 100, 1000):
                    # Skip lines that are clearly assignments to constants
                    findings.append({
                        "type": "magic_number",
                        "severity": "info",
                        "line": getattr(node, "lineno", 0),
                        "message": f"Magic number {node.value} — consider using a named constant.",
                        "suggestion": f"Extract {node.value} into a named constant for readability.",
                    })

        return findings

    def _cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function/method."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
        return complexity

    def _bool_depth(self, node: ast.BoolOp, depth: int = 1) -> int:
        """Calculate the nesting depth of boolean operations."""
        max_depth = depth
        for value in node.values:
            if isinstance(value, ast.BoolOp):
                max_depth = max(max_depth, self._bool_depth(value, depth + 1))
        return max_depth

    def _avg_method_length(self, methods: list) -> float:
        """Calculate average method length in lines."""
        if not methods:
            return 0.0
        lengths = [getattr(m, "end_lineno", m.lineno) - m.lineno + 1 for m in methods]
        return sum(lengths) / len(lengths)
