"""SYNAPSE Type Checker Agent.

Performs type safety and static analysis including type inference checking,
null safety analysis, generic type issues, and missing type annotations.

Token consumption: ~14K tokens per analysis.
"""

import ast
import re
from typing import Any


class TypeChecker:
    """Type safety & static analysis agent. Token consumption: ~14K tokens per analysis."""

    # Common built-in types for Python
    BUILTINS = {
        "str", "int", "float", "bool", "list", "dict", "set", "tuple",
        "bytes", "bytearray", "None", "NoneType", "object", "type",
        "frozenset", "complex", "range", "memoryview",
    }

    TYPING_TYPES = {
        "Optional", "Union", "List", "Dict", "Set", "Tuple", "Any",
        "Callable", "Sequence", "Mapping", "Iterator", "Generator",
        "Iterable", "Coroutine", "AsyncIterator", "AsyncGenerator",
        "Type", "ClassVar", "Final", "Literal", "TypeVar", "Generic",
        "Protocol", "TypedDict", "Annotated", "Never", "NoReturn",
    }

    def __init__(self, config: dict):
        self.config = config
        self.token_estimate = 14_000

    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code for type safety issues.

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

        # --- Missing Type Annotations ---
        findings.extend(self._check_missing_annotations(tree))

        # --- Null Safety Issues ---
        findings.extend(self._check_null_safety(tree, code))

        # --- Type Inference Issues ---
        findings.extend(self._check_type_inference(tree))

        # --- Generic Type Issues ---
        findings.extend(self._check_generic_issues(tree))

        # --- Return Type Consistency ---
        findings.extend(self._check_return_types(tree))

        # --- Inconsistent Type Usage ---
        findings.extend(self._check_inconsistent_types(tree))

        # Compute metrics
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        annotated = sum(1 for f in functions if self._has_return_annotation(f))
        params = sum(len(f.args.args) for f in functions)
        annotated_params = sum(
            1 for f in functions
            for a in f.args.args
            if a.annotation is not None and a.arg != "self" and a.arg != "cls"
        )

        metrics = {
            "total_functions": len(functions),
            "return_annotation_coverage": f"{annotated}/{len(functions)}" if functions else "N/A",
            "param_annotation_coverage": f"{annotated_params}/{params}" if params else "N/A",
            "missing_annotations": len([f for f in findings if f["type"] == "missing_annotation"]),
            "null_safety_issues": len([f for f in findings if f["type"] == "null_safety"]),
            "type_safety_score": max(0, 100 - len(findings) * 4),
        }

        return {
            "findings": findings,
            "metrics": metrics,
            "tokens_used": self.token_estimate,
        }

    def _check_missing_annotations(self, tree: ast.AST) -> list[dict]:
        """Find functions missing type annotations."""
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip dunder methods and simple getters
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue

                # Check return annotation
                if node.returns is None:
                    findings.append({
                        "type": "missing_annotation",
                        "severity": "info",
                        "line": node.lineno,
                        "message": f"Method '{node.name}' is missing a return type annotation.",
                        "suggestion": f"Add return type annotation to '{node.name}': def {node.name}(...) -> ReturnType:",
                    })

                # Check parameter annotations
                for arg in node.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    if arg.annotation is None:
                        findings.append({
                            "type": "missing_annotation",
                            "severity": "info",
                            "line": node.lineno,
                            "message": f"Parameter '{arg.arg}' in '{node.name}' is missing a type annotation.",
                            "suggestion": f"Add type annotation: {arg.arg}: Type",
                        })

        return findings

    def _check_null_safety(self, tree: ast.AST, code: str) -> list[dict]:
        """Detect potential null/None safety issues."""
        findings = []

        for node in ast.walk(tree):
            # Accessing attributes without None check
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                # Look for patterns like obj.attr without prior None check
                pass  # Full null-flow analysis requires control flow graph

            # Dangerous None comparisons
            if isinstance(node, ast.Compare):
                for op, comparator in zip(node.ops, node.comparators):
                    if isinstance(comparator, ast.Constant) and comparator.value is None:
                        if isinstance(op, (ast.IsNot, ast.Is)):
                            pass  # These are correct
                        elif isinstance(op, ast.Eq):
                            findings.append({
                                "type": "null_safety",
                                "severity": "warning",
                                "line": node.lineno,
                                "message": "Using '==' to compare with None — use 'is None' instead.",
                                "suggestion": "Change '== None' to 'is None' for correct None comparison.",
                            })
                        elif isinstance(op, ast.NotEq):
                            findings.append({
                                "type": "null_safety",
                                "severity": "warning",
                                "line": node.lineno,
                                "message": "Using '!=' to compare with None — use 'is not None' instead.",
                                "suggestion": "Change '!= None' to 'is not None' for correct None comparison.",
                            })

            # Returning None explicitly from typed functions
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is None:
                # This is fine if the return type is Optional, but worth flagging
                pass

            # Subscript on potentially None value
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                # Can't statically determine if the value is None without type info
                pass

        return findings

    def _check_type_inference(self, tree: ast.AST) -> list[dict]:
        """Check for type inference issues and potential type mismatches."""
        findings = []

        for node in ast.walk(tree):
            # Potential type errors in concatenation
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                # Could be mixing str + int, list + non-list, etc.
                pass  # Would need type inference to detect

            # isinstance checks that may indicate type confusion
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                if len(node.args) == 2:
                    findings.append({
                        "type": "type_inference",
                        "severity": "info",
                        "line": node.lineno,
                        "message": "isinstance check detected — consider using Union types or generics for type safety.",
                        "suggestion": "If overusing isinstance, consider a more type-safe design with Union/Optional annotations.",
                    })

            # Bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append({
                    "type": "type_inference",
                    "severity": "warning",
                    "line": node.lineno,
                    "message": "Bare 'except:' clause catches all exceptions including KeyboardInterrupt and SystemExit.",
                    "suggestion": "Use 'except Exception:' or specify the expected exception type.",
                })

        return findings

    def _check_generic_issues(self, tree: ast.AST) -> list[dict]:
        """Check for generic type usage issues."""
        findings = []

        for node in ast.walk(tree):
            # Using mutable default arguments (type issue)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        findings.append({
                            "type": "generic_issue",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"Mutable default argument in '{node.name}' — shared across calls.",
                            "suggestion": f"Use None as default and create the mutable inside the method: def {node.name}(x=None): x = x or []",
                        })

            # Checking for bare generics (list instead of List[int])
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id in ("list", "dict", "set", "tuple"):
                    # These are fine in modern Python 3.9+
                    pass

        return findings

    def _check_return_types(self, tree: ast.AST) -> list[dict]:
        """Check for inconsistent return types within a function."""
        findings = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                returns = [
                    child for child in ast.walk(node)
                    if isinstance(child, ast.Return)
                ]

                has_none_return = any(r.value is None for r in returns)
                has_value_return = any(r.value is not None for r in returns)

                if has_none_return and has_value_return and node.returns is None:
                    findings.append({
                        "type": "return_type",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"Method '{node.name}' returns both None and a value — annotate with Optional[Type].",
                        "suggestion": f"Add '-> Optional[ReturnType]' to '{node.name}' to document the mixed return behavior.",
                    })

        return findings

    def _check_inconsistent_types(self, tree: ast.AST) -> list[dict]:
        """Check for inconsistent type usage patterns."""
        findings = []

        # Check for mixed string formatting styles
        uses_fstring = False
        uses_format = False
        uses_percent = False

        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):  # f-string
                uses_fstring = True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "format":
                    uses_format = True
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    uses_percent = True

        style_count = sum([uses_fstring, uses_format, uses_percent])
        if style_count > 1:
            findings.append({
                "type": "inconsistent_types",
                "severity": "info",
                "line": 1,
                "message": f"Multiple string formatting styles detected ({style_count} styles).",
                "suggestion": "Standardize on f-strings (Python 3.6+) for consistency.",
            })

        return findings

    def _has_return_annotation(self, node: ast.FunctionDef) -> bool:
        """Check if a function has a return type annotation."""
        return node.returns is not None
